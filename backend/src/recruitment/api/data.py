from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from recruitment.api.auth import admin, current_user
from recruitment.adapters.mongo import database
from recruitment.adapters.jobs import MongoJobs
from recruitment.application.datasets import DatasetService,report_match
from recruitment.domain.common import AppError, now
from recruitment.application.pipeline import PipelineService

router = APIRouter(prefix='/api/v1', tags=['Data'])


def require(collection, identifier):
    value = database()[collection].find_one({'_id': identifier})
    if not value:
        raise AppError('NOT_FOUND', 'Không tìm thấy dữ liệu.', 404)
    return value


def page_result(collection, query, page, size):
    cursor = database()[collection].find(query).sort([('created_at', -1), ('_id', 1)]).skip((page-1)*size).limit(size)
    return {'data': list(cursor), 'meta': {'page': page, 'page_size': size, 'total': database()[collection].count_documents(query)}}


@router.post('/datasets/upload', status_code=202)
async def upload(file: UploadFile = File(), source: str = Form(min_length=1, max_length=100),
                 is_demo: bool = Form(True), idempotency_key: str = Header(default=''), user=Depends(admin)):
    return {'data': await DatasetService(database()).upload(file, source, is_demo, idempotency_key, user['_id'])}


@router.get('/datasets')
def datasets(page: int = Query(1, ge=1, le=400), page_size: int = Query(25, ge=1, le=100), user=Depends(current_user)):
    result = page_result('datasets', {} if user['role']=='ADMIN' else {'status':'PUBLISHED'}, page, page_size)
    for item in result['data']:
        item.pop('file_ref', None); item.pop('raw_file_ref', None)
    return result


@router.get('/datasets/{version}')
def dataset_detail(version: str, user=Depends(current_user)):
    record = require('datasets', version)
    if user['role']!='ADMIN' and record['status']!='PUBLISHED':raise AppError('NOT_FOUND','Không tìm thấy dataset.',404)
    record.pop('file_ref', None); record.pop('raw_file_ref', None)
    return {'data': record}


@router.get('/datasets/{version}/quality')
def quality(version: str, user=Depends(admin)):
    report = database().data_quality_reports.find_one(report_match(database(),version))
    return {'data': report}


@router.get('/datasets/{version}/invalid')
def invalid(version: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), user=Depends(admin)):
    return page_result('invalid_jobs', report_match(database(),version), page, page_size)


@router.get('/datasets/{version}/duplicates')
def duplicates(version: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), user=Depends(admin)):
    return page_result('duplicate_jobs', report_match(database(),version), page, page_size)


class ETLRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_version: str


@router.post('/etl/jobs', status_code=202)
def submit_etl(body: ETLRequest, user=Depends(admin)):
    job=PipelineService(database(),MongoJobs(database())).submit_etl(body.dataset_version,user['_id'])
    return {'data': {'job_id': job['_id'], 'status_url': '/api/v1/etl/jobs/' + job['_id']}}


@router.get('/etl/jobs')
def jobs(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), user=Depends(admin)):
    return page_result('etl_jobs', {}, page, page_size)


@router.get('/etl/jobs/{identifier}')
def job_detail(identifier: str, user=Depends(admin)):
    return {'data': require('etl_jobs', identifier)}


@router.post('/etl/jobs/{identifier}/retry', status_code=202)
def retry(identifier: str, user=Depends(admin)):
    PipelineService(database(),MongoJobs(database())).retry(identifier)
    return {'data': {'job_id': identifier}}


@router.post('/etl/jobs/{identifier}/cancel', status_code=202)
def cancel(identifier: str, user=Depends(admin)):
    target=PipelineService(database(),MongoJobs(database())).cancel(identifier)
    return {'data': {'job_id': identifier, 'status': target}}


@router.post('/datasets/{version}/activate')
def activate_dataset(version:str,user=Depends(admin)):
    dataset=require('datasets',version)
    if dataset['status']!='PUBLISHED':raise AppError('INVALID_STATE','Chỉ active version đã công bố.',409)
    pointer=database().system_settings.find_one({'_id':'active_dataset'})
    if pointer:
        result=database().system_settings.update_one({'_id':'active_dataset','revision':pointer['revision']},
            {'$set':{'value':version,'updated_at':now()},'$inc':{'revision':1}})
        if not result.modified_count:raise AppError('REVISION_CONFLICT','Version active vừa thay đổi.',409)
    else:
        database().system_settings.insert_one({'_id':'active_dataset','value':version,'revision':1})
    database().audit_logs.insert_one({'action':'DATASET_ACTIVATE','resource_id':version,'actor_id':user['_id'],'created_at':now()})
    return {'data':{'active_dataset_version':version}}
