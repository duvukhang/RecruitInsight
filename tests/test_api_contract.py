import pytest
from fastapi.testclient import TestClient
from recruitment.main import app
from recruitment.adapters.mongo import database
from recruitment.infrastructure.init_db import migrate
from recruitment.infrastructure.security import access_token
from recruitment.domain.common import uid


@pytest.fixture
def client_and_users():
    db=database();assert db.name.endswith('_test');migrate(db)
    users=[{'_id':uid(),'username':uid(),'role':role,'enabled':True,'password_hash':'TEST_UNUSED_NO_LOGIN'} for role in ['ADMIN','VIEWER']]
    db.users.insert_many(users)
    try:yield TestClient(app),[{'Authorization':'Bearer '+access_token(user)} for user in users],users
    finally:db.users.delete_many({'_id':{'$in':[u['_id'] for u in users]}})


def test_permissions_and_structured_validation(client_and_users):
    c,(admin,viewer),users=client_and_users
    assert c.get('/api/v1/datasets').status_code==401
    assert c.get('/api/v1/datasets',headers=viewer).status_code==200
    assert c.get('/api/v1/system/status',headers=viewer).status_code==403
    bad={'job_title':'Engineer','industry':'IT','province':'HCM','experience_years':-1,'salary_mid_vnd':100}
    response=c.post('/api/v1/predictions/salary',headers=admin,json=bad)
    assert response.status_code==422
    assert response.json()['error']['code']=='VALIDATION_ERROR'
    assert response.json()['error']['request_id']
    assert c.get('/api/v1/auth/me',headers={'Authorization':'Bearer forged'}).status_code==401
    assert c.get('/api/v1/unknown-endpoint').json()['error']['code']=='NOT_FOUND'
    model_id,version=uid(),uid()
    database().model_registry.insert_one({'_id':model_id,'algorithm':'linear','dataset_version':version,'status':'CANDIDATE','artifact_sha256':'TEST_ONLY'})
    try:
        filtered=c.get('/api/v1/models?dataset_version='+version,headers=admin).json()['data']
        assert len(filtered)==1 and filtered[0]['_id']==model_id
        assert c.get('/api/v1/models',headers=viewer).status_code==403
    finally:database().model_registry.delete_one({'_id':model_id})
    assert c.post('/api/v1/datasets/upload',headers={**admin,'Idempotency-Key':uid()},
        files={'file':('script.exe',b'not a dataset')},data={'source':'TEST'}).status_code==415


def test_prediction_ownership_and_missing_model(client_and_users):
    c,(admin,viewer),users=client_and_users;db=database();identifier=uid()
    db.salary_predictions.insert_one({'_id':identifier,'user_id':users[0]['_id'],'model_version':'TEST','predicted_salary_vnd':100})
    try:
        assert c.get('/api/v1/predictions/'+identifier,headers=viewer).status_code==403
        assert c.get('/api/v1/predictions/'+identifier,headers=admin).status_code==200
        payload={'job_title':'Engineer','industry':'IT','province':'HCM','experience_years':3}
        assert c.post('/api/v1/predictions/salary',headers=viewer,json=payload).status_code==403
        if not db.system_settings.find_one({'_id':'active_model'}):
            response=c.post('/api/v1/predictions/salary',headers=admin,json=payload)
            assert response.status_code==503
            assert response.json()['error']['code']=='MODEL_NOT_AVAILABLE'
    finally:db.salary_predictions.delete_one({'_id':identifier})


def test_dashboard_active_model_and_version_scoped_latest_etl(client_and_users):
    c, (admin, viewer), users = client_and_users
    db = database()
    version, model_id = uid(), uid()
    old_pointer = db.system_settings.find_one({'_id': 'active_model'})
    job_ids = [uid(), uid(), uid()]
    from recruitment.domain.common import now
    db.model_registry.insert_one({'_id': model_id, 'algorithm': 'linear', 'dataset_version': version, 'status': 'ACTIVE', 'artifact_sha256': 'TEST'})
    db.system_settings.update_one({'_id': 'active_model'}, {'$set': {'value': model_id}, '$setOnInsert': {'revision': 1}}, upsert=True)
    for identifier, kind, target in zip(job_ids, ['ETL', 'TRAINING', 'ETL'], [version, version, uid()]):
        db.etl_jobs.insert_one({'_id': identifier, 'job_type': kind, 'status': 'QUEUED', 'created_at': now(), 'payload': {'dataset_version': target}})
    try:
        response = c.get('/api/v1/models?active_only=true', headers=admin).json()
        assert response['meta']['total'] == 1 and response['data'][0]['is_active'] is True
        assert c.get('/api/v1/models?active_only=true&dataset_version=unknown', headers=admin).json()['data'] == []
        response = c.get('/api/v1/etl/jobs?job_type=ETL&dataset_version=' + version, headers=admin).json()
        assert response['meta']['total'] == 1 and response['data'][0]['_id'] == job_ids[0]
        assert c.get('/api/v1/models?active_only=true', headers=viewer).status_code == 403
        assert c.get('/api/v1/etl/jobs?job_type=ETL', headers=viewer).status_code == 403
    finally:
        db.model_registry.delete_one({'_id': model_id})
        db.etl_jobs.delete_many({'_id': {'$in': job_ids}})
        if old_pointer: db.system_settings.replace_one({'_id': 'active_model'}, old_pointer, upsert=True)
        else: db.system_settings.delete_one({'_id': 'active_model'})
