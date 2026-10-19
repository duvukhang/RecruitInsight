import pytest
from datetime import timedelta
from recruitment.domain.jobs import validate_transition
from recruitment.domain.common import AppError, now, uid
from recruitment.adapters.mongo import database
from recruitment.adapters.jobs import MongoJobs
from recruitment.infrastructure.init_db import migrate


def test_no_cancel_during_commit():
    with pytest.raises(AppError):
        validate_transition('COMMITTING', 'CANCELLED')
    validate_transition('RUNNING', 'CANCEL_REQUESTED')


def test_claim_and_stale_fencing():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    repository = MongoJobs(db)
    actor = uid()
    job = repository.enqueue('TEST', {}, actor)
    try:
        first = repository.claim(['TEST'], 'worker-a')
        assert first['_id'] == job['_id']
        assert repository.claim(['TEST'], 'worker-b') is None
        assert repository.heartbeat(first, 'worker-a')
        db.etl_jobs.update_one({'_id': job['_id']}, {'$set': {'lease_until': now() - timedelta(seconds=1)}})
        repository.recover()
        second = repository.claim(['TEST'], 'worker-b')
        assert second['fencing_token'] > first['fencing_token']
        assert second['attempt_id'] != first['attempt_id']
        assert not repository.heartbeat(first, 'worker-a')
    finally:
        db.etl_jobs.delete_one({'_id': job['_id']})


def test_commit_recovery_revokes_unpublished_attempt():
    db=database();assert db.name.endswith('_test');migrate(db)
    version,attempt,identifier=uid(),uid(),uid()
    db.datasets.insert_one({'_id':version,'dataset_id':version,'status':'PROCESSING','active_attempt':attempt,
        'created_by':'test','idempotency_key':version,'is_demo':True,'created_at':now()})
    db.etl_jobs.insert_one({'_id':identifier,'job_type':'ETL','status':'COMMITTING','created_at':now(),
        'payload':{'dataset_version':version},'attempt_id':attempt,'fencing_token':1,'lease_until':now()-timedelta(seconds=1)})
    try:
        MongoJobs(db).recover()
        assert db.etl_jobs.find_one({'_id':identifier})['status']=='FAILED'
        dataset=db.datasets.find_one({'_id':version})
        assert dataset['status']=='FAILED' and 'active_attempt' not in dataset
    finally:db.datasets.delete_one({'_id':version});db.etl_jobs.delete_one({'_id':identifier})
