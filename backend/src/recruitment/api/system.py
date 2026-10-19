from datetime import timedelta
from fastapi import APIRouter, Depends
from recruitment.api.auth import admin
from recruitment.adapters.mongo import database
from recruitment.domain.common import now
from pydantic import BaseModel,ConfigDict,Field
from datetime import date
from recruitment.domain.common import AppError

router = APIRouter(prefix='/api/v1/system', tags=['System'], dependencies=[Depends(admin)])


@router.get('/status')
def status():
    db = database()
    db.command('ping')
    workers = list(db.worker_heartbeats.find({'updated_at': {'$gt': now() - timedelta(seconds=45)}}))
    return {'data': {'mongodb': 'ready', 'workers': [
        {'id': w['_id'], 'kind': w['kind'], 'updated_at': w['updated_at']} for w in workers],
        'database': db.name, 'checked_at': now()}}


class Rate(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    rate:float=Field(gt=0,le=1e9)
    source:str=Field(min_length=3,max_length=500)
    date:date


class Normalization(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    rates:dict[str,Rate]=Field(default_factory=dict,max_length=10)
    hours_per_month:float|None=Field(None,gt=0,le=744)
    days_per_month:float|None=Field(None,gt=0,le=31)
    validity_min:float=Field(.9,ge=0,le=1)


@router.get('/settings')
def get_settings():
    config=database().system_settings.find_one({'_id':'normalization'})
    return {'data':config['value'] if config else Normalization().model_dump(mode='json')}


@router.patch('/settings')
def set_settings(body:Normalization,user=Depends(admin)):
    value=body.model_dump(mode='json')
    database().system_settings.update_one({'_id':'normalization'},{'$set':{'value':value,'updated_at':now()},'$inc':{'revision':1}},upsert=True)
    database().audit_logs.insert_one({'action':'NORMALIZATION_CONFIG_UPDATE','actor_id':user['_id'],'created_at':now()})
    return {'data':value}
