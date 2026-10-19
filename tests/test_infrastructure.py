from fastapi.testclient import TestClient
from recruitment.main import app
from recruitment.adapters.mongo import database
from recruitment.infrastructure.init_db import migrate
from recruitment.domain.common import uid
import pytest
from pymongo.errors import DuplicateKeyError,WriteError


def test_liveness():
    response = TestClient(app).get('/api/v1/health/live')
    assert response.json() == {"status": "alive"}
    assert response.headers['X-Request-ID']


def test_mongo_migration_and_index():
    db = database()
    assert db.name.endswith('_test'), 'Only use isolated test database'
    migrate(db)
    migrate(db)
    assert TestClient(app).get('/api/v1/health/ready').status_code == 200
    assert db.cleaned_jobs.index_information()['dataset_version_1_attempt_id_1_source_job_key_1']['unique']
    version=uid()
    record={'_id':uid(),'dataset_version':version,'attempt_id':'test','source_job_key':'same','job_title':'Engineer'}
    try:
        db.cleaned_jobs.insert_one(record)
        with pytest.raises(DuplicateKeyError):db.cleaned_jobs.insert_one({**record,'_id':uid()})
        with pytest.raises(WriteError) as error:db.cleaned_jobs.insert_one({**record,'_id':uid(),'source_job_key':'other','job_title':123})
        assert error.value.code==121
    finally:db.cleaned_jobs.delete_many({'dataset_version':version})
