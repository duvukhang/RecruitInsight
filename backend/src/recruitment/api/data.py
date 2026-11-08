from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import date
from typing import Literal
from recruitment.api.auth import admin, current_user
from recruitment.adapters.mongo import database
from recruitment.adapters.jobs import MongoJobs
from recruitment.application.datasets import DatasetService,report_match
from recruitment.domain.common import AppError, now
from recruitment.application.pipeline import PipelineService

router = APIRouter(prefix='/api/v1', tags=['Data'])


@router.get('/sources')
def sources(user=Depends(admin)):
    from bigdata.sources import SOURCES, ADAPTER_VERSION
    return {'data': [{'id': key, **value, 'adapter_version': ADAPTER_VERSION} for key, value in SOURCES.items()]}


def require(collection, identifier):
    value = database()[collection].find_one({'_id': identifier})
    if not value:
        raise AppError('NOT_FOUND', 'Không tìm thấy dữ liệu.', 404)
    return value


def page_result(collection, query, page, size):
    cursor = database()[collection].find(query).sort([('created_at', -1), ('_id', 1)]).skip((page-1)*size).limit(size)
    return {'data': list(cursor), 'meta': {'page': page, 'page_size': size, 'total': database()[collection].count_documents(query)}}


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    source_type: Literal['upload', 'offline', 'api', 'synthetic'] | None = None
    collected_at: date | None = None
    observation_from: date | None = None
    observation_to: date | None = None
    license_permission: str | None = Field(None, max_length=1000)
    dataset_origin: Literal['synthetic', 'public_unverified', 'real', 'mixed', 'unknown'] | None = None
    permission_status: Literal['NEEDS_REVIEW', 'DECLARED_PERMISSION', 'SYNTHETIC_FIXTURE'] | None = None
    permission_evidence: str | None = Field(None, max_length=1000)
    adapter_version: str | None = Field(None, max_length=100)
    source_revision: str | None = Field(None, max_length=100)
    source_dataset_url: str | None = Field(None, max_length=500)
    input_sha256: str | None = Field(None, pattern=r'^[a-f0-9]{64}$')
    row_count: int | None = Field(None, ge=0)
    observation_year_from: int | None = Field(None, ge=1900, le=2099)
    observation_year_to: int | None = Field(None, ge=1900, le=2099)

    @model_validator(mode='after')
    def ordered_period(self):
        if self.observation_from and self.observation_to and self.observation_from > self.observation_to:
            raise ValueError('Observation period must be ordered')
        if self.observation_year_from and self.observation_year_to and self.observation_year_from > self.observation_year_to:
            raise ValueError('Observation years must be ordered')
        return self


@router.post('/datasets/upload', status_code=202)
async def upload(file: UploadFile = File(), source: str = Form(min_length=1, max_length=100),
                 is_demo: bool = Form(True), idempotency_key: str = Header(default=''),
                 source_metadata: str = Form('{}', max_length=8000,
                     description='Optional JSON: source_type, collected_at, observation_from, observation_to (YYYY-MM-DD), license_permission.'), user=Depends(admin)):
    try:
        metadata = SourceMetadata.model_validate_json(source_metadata).model_dump(mode='json', exclude_none=True)
    except ValueError:
        raise AppError('VALIDATION_ERROR', 'Metadata nguồn không hợp lệ: kiểm tra JSON, ngày và quyền sử dụng.', 422)
    return {'data': await DatasetService(database()).upload(file, source, is_demo, idempotency_key, user['_id'], metadata)}


@router.get('/datasets')
def datasets(page: int = Query(1, ge=1, le=400), page_size: int = Query(25, ge=1, le=100), user=Depends(current_user)):
    result = page_result('datasets', {} if user['role']=='ADMIN' else {'status':'PUBLISHED'}, page, page_size)
    active = database().system_settings.find_one({'_id': 'active_dataset'}, {'value': 1})
    result['meta']['active_dataset_version'] = active['value'] if active else None
    for item in result['data']:
        item.pop('file_ref', None); item.pop('raw_file_ref', None)
    return result


class ChunkManifest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    bytes: int = Field(gt=0, le=50 * 1024 * 1024)
    row_count: int = Field(gt=0, le=500000)


class StagedRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source: str = Field(min_length=1, max_length=100)
    is_demo: bool = True
    source_metadata: SourceMetadata
    chunks: list[ChunkManifest] = Field(min_length=1, max_length=128)


class StagedCreated(BaseModel):
    dataset_version: str
    chunk_count: int


class StagedResponse(BaseModel):
    data: StagedCreated


class ChunkReceived(BaseModel):
    index: int
    sha256: str
    bytes: int


class ChunkResponse(BaseModel):
    data: ChunkReceived


class IngestionQueued(BaseModel):
    dataset_version: str
    ingestion_id: str
    job_id: str
    status_url: str


class IngestionResponse(BaseModel):
    data: IngestionQueued


@router.post('/datasets/staged', status_code=201, response_model=StagedResponse)
def create_staged(body: StagedRequest, idempotency_key: str = Header(default=''), user=Depends(admin)):
    from recruitment.application.staged_import import StagedImport
    return {'data': StagedImport(database()).create(body, user['_id'], idempotency_key)}


@router.put('/datasets/staged/{version}/chunks/{index}', response_model=ChunkResponse)
async def staged_chunk(version: str, index: int, file: UploadFile = File(), user=Depends(admin)):
    from recruitment.application.staged_import import StagedImport
    return {'data': await StagedImport(database()).chunk(version, index, file)}


@router.post('/datasets/staged/{version}/complete', status_code=202, response_model=IngestionResponse)
def staged_complete(version: str, user=Depends(admin)):
    from recruitment.application.staged_import import StagedImport
    return {'data': StagedImport(database()).seal(version)}


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
def jobs(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
         dataset_version: str | None = Query(None, max_length=128), job_type: Literal['ETL', 'INGESTION', 'TRAINING'] | None = None, user=Depends(admin)):
    match={}
    if dataset_version:match['payload.dataset_version']=dataset_version
    if job_type:match['job_type']=job_type
    return page_result('etl_jobs', match, page, page_size)


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
