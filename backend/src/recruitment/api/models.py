from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,ConfigDict,Field
from recruitment.adapters.mongo import database
from recruitment.adapters.jobs import MongoJobs
from recruitment.api.auth import admin,current_user,analyst
from recruitment.api.data import require,page_result
from recruitment.application.datasets import published
from recruitment.domain.common import AppError,now
from machine_learning.serving import load,predict
from typing import Annotated
from recruitment.application.pipeline import PipelineService
from recruitment.application.models import ModelService

router=APIRouter(prefix='/api/v1',tags=['Machine Learning'])


class TrainRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_version:str


class SalaryFeatures(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,str_strip_whitespace=True)
    job_title:str=Field(min_length=1,max_length=200)
    industry:str=Field(min_length=1,max_length=100)
    province:str=Field(min_length=1,max_length=100)
    experience_years:float=Field(ge=0,le=60)
    seniority_level:str=Field(default='Unknown',max_length=100)
    education_level:str=Field(default='Unknown',max_length=100)
    employment_type:str=Field(default='Unknown',max_length=100)
    remote_type:str=Field(default='Unknown',max_length=100)
    required_skills:list[Annotated[str,Field(min_length=1,max_length=100)]]=Field(default_factory=list,max_length=50)


@router.post('/models/train',status_code=202)
def submit(body:TrainRequest,user=Depends(admin)):
    job=PipelineService(database(),MongoJobs(database())).submit_training(body.dataset_version,user['_id'])
    return {'data':{'job_id':job['_id'],'status_url':'/api/v1/etl/jobs/'+job['_id']}}


@router.get('/models')
def models(page:int=Query(1,ge=1,le=400),page_size:int=Query(25,ge=1,le=100),dataset_version:str|None=None,user=Depends(analyst)):
    result=page_result('model_registry',{'dataset_version':dataset_version} if dataset_version else {},page,page_size)
    active=database().system_settings.find_one({'_id':'active_model'})
    for model in result['data']:
        model.pop('artifact_uri',None);model['is_active']=bool(active and active['value']==model['_id'])
    return result


@router.get('/models/{identifier}/metrics')
def model_metrics(identifier:str,user=Depends(analyst)):
    return {'data':require('ml_experiments',identifier)}


@router.post('/models/{identifier}/activate')
def activate(identifier:str,user=Depends(admin)):
    ModelService(database()).activate(identifier,user['_id'])
    return {'data':{'active_model_version':identifier}}


@router.post('/predictions/salary',status_code=201)
def prediction(body:SalaryFeatures,user=Depends(analyst)):
    if user['role']=='VIEWER':raise AppError('FORBIDDEN','Cần quyền analyst hoặc admin.',403)
    return {'data':predict(database(),body.model_dump(),user['_id'])}


@router.get('/predictions/history')
def history(page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),user=Depends(analyst)):
    return page_result('salary_predictions',{'user_id':user['_id']},page,page_size)


@router.get('/predictions/{identifier}')
def detail(identifier:str,user=Depends(analyst)):
    record=database().salary_predictions.find_one({'_id':identifier,'user_id':user['_id']})
    if not record:raise AppError('NOT_FOUND','Không tìm thấy dự đoán.',404)
    return {'data':record}


@router.get('/models/{identifier}')
def model_detail(identifier:str,user=Depends(analyst)):
    model=require('model_registry',identifier);model.pop('artifact_uri',None)
    return {'data':model}


class Rollback(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target_model_version:str


@router.post('/models/{identifier}/rollback')
def rollback(identifier:str,body:Rollback,user=Depends(admin)):
    pointer=database().system_settings.find_one({'_id':'active_model'})
    if not pointer or pointer['value']!=identifier:raise AppError('REVISION_CONFLICT','Active model đã đổi.',409)
    return activate(body.target_model_version,user)
