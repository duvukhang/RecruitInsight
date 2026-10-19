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
