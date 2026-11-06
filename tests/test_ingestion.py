import io
import json
import pytest
from starlette.datastructures import UploadFile
from recruitment.adapters.mongo import database
from recruitment.application.datasets import DatasetService
from recruitment.domain.common import uid, AppError
from recruitment.infrastructure.init_db import migrate
from bigdata.ingestion import ingest
from pathlib import Path
import asyncio


@pytest.mark.parametrize('suffix,content,count',[
    ('.csv','job_title,company_name\nEngineer,ACME\nAnalyst,ACME\n',2),
    ('.json',json.dumps([{'job_title':'Engineer'}]),1),
    ('.jsonl','{"job_title":"Engineer"}\nbroken-json\n',2),
])
def test_raw_retention_and_idempotency(suffix, content, count):
    db=database();assert db.name.endswith('_test');migrate(db)
    service=DatasetService(db);actor=uid();key=uid()
    async def upload(text):
        return await service.upload(UploadFile(io.BytesIO(text.encode()),filename='input'+suffix),'TEST',True,key,actor)
    first=asyncio.run(upload(content))
    second=asyncio.run(upload(content))
    assert first['job_id']==second['job_id']
    version=first['dataset_version']
    dataset=db.datasets.find_one({'_id':version})
    try:
        with pytest.raises(AppError) as error:
            asyncio.run(upload(content+' '))
        assert error.value.status==409
        with pytest.raises(AppError) as error:
            asyncio.run(service.upload(UploadFile(io.BytesIO(content.encode()),filename='input'+suffix),
                'TEST',True,key,actor,{'license_permission':'different permission'}))
        assert error.value.code=='IDEMPOTENCY_CONFLICT'
        job=db.etl_jobs.find_one({'_id':first['job_id']});job['attempt_id']=uid()
        ingest(db,job,lambda:None)
        ingest(db,job,lambda:None)
        assert db.raw_jobs.count_documents({'dataset_version':version})==count
        if suffix=='.jsonl':
            assert db.raw_jobs.find_one({'dataset_version':version,'record_number':2})['raw_payload']['_parse_error']
        assert db.datasets.find_one({'_id':version})['status']=='RAW_READY'
    finally:
        for name in ['raw_jobs','ingestion_runs']:
            db[name].delete_many({'dataset_version':version})
        db.datasets.delete_one({'_id':version});db.etl_jobs.delete_one({'_id':first['job_id']})
        Path(dataset['file_ref']).unlink(missing_ok=True)
        Path(dataset['file_ref']).with_suffix('.raw.jsonl').unlink(missing_ok=True)
