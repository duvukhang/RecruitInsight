import re
from datetime import date
from fastapi import APIRouter, Depends, Query
from recruitment.api.auth import current_user
from recruitment.adapters.mongo import database
from recruitment.application.analytics import AnalyticsService
from recruitment.application.datasets import published
from recruitment.domain.common import AppError
from typing import Literal

router=APIRouter(prefix='/api/v1',tags=['Analytics'],dependencies=[Depends(current_user)])


def filters(dataset_version: str | None=None, province: str | None=Query(None,max_length=100),
            industry: str | None=Query(None,max_length=100), posted_from: date | None=None, posted_to: date | None=None):
    if posted_from and posted_to and posted_from>posted_to:
        raise AppError('VALIDATION_ERROR','Ngày bắt đầu phải trước ngày kết thúc.',422)
    return AnalyticsService(database(),dataset_version,province,industry,
                            posted_from.isoformat() if posted_from else None,posted_to.isoformat() if posted_to else None)


@router.get('/analytics/{metric}')
def analytics(metric: str, service=Depends(filters)):
    if metric not in ['overview','salary-distribution','salary-by-industry','salary-by-location','job-trends','job-years','top-skills','experience','companies']:
        raise AppError('NOT_FOUND','Không có loại thống kê này.',404)
    return service.metric(metric)


@router.get('/jobs/filters/options')
def options(dataset_version: str | None=None):
    dataset,match=published(database(),dataset_version)
    snapshot=database().analytics_snapshots.find_one(match)['data']
    return {'data':{'provinces':[r['province'] for r in snapshot['locations']],
                    'industries':[r['industry'] for r in snapshot['industries']]},'meta':{'dataset_version':dataset['_id']}}


@router.get('/jobs')
def jobs(service=Depends(filters),page:int=Query(1,ge=1,le=400),page_size:int=Query(25,ge=1,le=100),q:str=Query('',max_length=200),
         sort:Literal['posted_at','salary_mid_vnd','experience_years','job_title']='posted_at',order:Literal['asc','desc']='desc',
         salary_min:float|None=Query(None,ge=0,le=1e12,allow_inf_nan=False),salary_max:float|None=Query(None,ge=0,le=1e12,allow_inf_nan=False),
         experience_min:float|None=Query(None,ge=0,le=60,allow_inf_nan=False),experience_max:float|None=Query(None,ge=0,le=60,allow_inf_nan=False),
         employment_type:str|None=Query(None,max_length=100),posted_year:int|None=Query(None,ge=1900,le=2099),
         cursor:str|None=Query(None,max_length=8192)):
    match=dict(service.match)
    if q:match['$or']=[{field:{'$regex':re.escape(q),'$options':'i'}} for field in ['job_title','company_name']]
    for field,lower,upper in [('salary_mid_vnd',salary_min,salary_max),('experience_years',experience_min,experience_max)]:
        if lower is not None and upper is not None and lower>upper:
            raise AppError('VALIDATION_ERROR','Khoảng lọc bị đảo.',422)
        if lower is not None or upper is not None:
            match[field]={'$ne':None}
            if lower is not None:match[field]['$gte']=lower
            if upper is not None:match[field]['$lte']=upper
    if employment_type:match['employment_type']=employment_type
    if posted_year is not None:match['posted_year']=posted_year
    collection=database().cleaned_jobs
    direction=1 if order=='asc' else -1
    if cursor is not None:
        from recruitment.application.pagination import query_hash, cursor_condition, encode_cursor
        if page != 1:raise AppError('VALIDATION_ERROR','Không kết hợp cursor với page khác 1.',422)
        digest=query_hash(match,sort,order,page_size)
        scoped={'$and':[match,cursor_condition(cursor,sort,order,digest)]} if cursor else match
        items=list(collection.find(scoped,{'job_description':0}).sort([(sort,direction),('_id',direction)]).limit(page_size+1).max_time_ms(5000))
        has_more=len(items)>page_size;items=items[:page_size]
        next_cursor=encode_cursor(items[-1],sort,digest) if has_more else None
    else:
        items=list(collection.find(match,{'job_description':0}).sort([(sort,direction),('_id',1)]).skip((page-1)*page_size).limit(page_size).max_time_ms(5000))
        next_cursor=None
    return {'data':items,'meta':{**service.metadata(),'job_filters':match,'page':page,'page_size':page_size,
        'pagination_mode':'cursor' if cursor is not None else 'offset','next_cursor':next_cursor,
        'total':collection.count_documents(match,maxTimeMS=5000)}}


@router.get('/jobs/{identifier}')
def job(identifier: str,service=Depends(filters)):
    record=database().cleaned_jobs.find_one({**service.match,'_id':identifier})
    if not record:raise AppError('NOT_FOUND','Không tìm thấy tin tuyển dụng.',404)
    return {'data':record,'meta':service.metadata()}
