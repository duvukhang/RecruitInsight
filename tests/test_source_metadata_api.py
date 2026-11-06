import importlib
import pytest
from fastapi.testclient import TestClient
from recruitment.main import app
from recruitment.api.auth import admin


@pytest.mark.parametrize('metadata,status', [
    (None,202),
    ('{"source_type":"synthetic","license_permission":"TEST ONLY","collected_at":"2026-01-01"}',202),
    ('not JSON',422),
    ('{"observation_from":"2026-02-01","observation_to":"2026-01-01"}',422),
])
def test_upload_metadata_http_validation_preserves_legacy_request(monkeypatch,metadata,status):
    module=importlib.import_module('recruitment.api.data')
    calls=[]
    class FakeService:
        def __init__(self, db):pass
        async def upload(self,*args):
            calls.append(args)
            return {'dataset_version':'TEST'}
    monkeypatch.setattr(module,'DatasetService',FakeService)
    monkeypatch.setattr(module,'database',lambda:None)
    app.dependency_overrides[admin]=lambda:{'_id':'TEST-USER','role':'ADMIN'}
    try:
        data={'source':'TEST','is_demo':'true'}
        if metadata is not None:data['source_metadata']=metadata
        response=TestClient(app).post('/api/v1/datasets/upload',
            files={'file':('input.csv',b'job_title,company_name\nEngineer,A')},data=data,
            headers={'Idempotency-Key':'TEST'})
        assert response.status_code==status
        if status==202:
            assert calls[0][-1]==({} if metadata is None else {'source_type':'synthetic','license_permission':'TEST ONLY','collected_at':'2026-01-01'})
        else:
            assert not calls
            assert response.json()['error']['code']=='VALIDATION_ERROR'
    finally:
        app.dependency_overrides.pop(admin,None)


def test_metadata_is_additive_and_prediction_inputs_forbid_target():
    from recruitment.api.models import SalaryFeatures
    schema=app.openapi()['components']['schemas']['Body_upload_api_v1_datasets_upload_post']
    assert 'source_metadata' not in schema['required']
    assert schema['properties']['source_metadata']['default']=='{}'
    with pytest.raises(ValueError):
        SalaryFeatures(job_title='Engineer',industry='IT',province='HCM',experience_years=2,salary_mid_vnd=100)
