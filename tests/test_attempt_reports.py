from recruitment.adapters.mongo import database
from recruitment.infrastructure.init_db import migrate
from recruitment.application.datasets import report_match
from recruitment.domain.common import uid,now


def test_published_reports_never_mix_retry_attempts():
    db=database();assert db.name.endswith('_test');migrate(db)
    version,old,current=uid(),uid(),uid()
    db.datasets.insert_one({'_id':version,'dataset_id':version,'status':'PUBLISHED','published_attempt_id':current,
        'created_by':'test-reports','idempotency_key':version,'is_demo':True,'created_at':now()})
    for attempt in [old,current]:
        db.invalid_jobs.insert_one({'_id':uid(),'dataset_version':version,'attempt_id':attempt,'raw_record_ref':'same-raw','error_code':'MISSING_TITLE'})
    try:
        assert db.invalid_jobs.count_documents({'dataset_version':version})==2
        assert db.invalid_jobs.count_documents(report_match(db,version))==1
        assert report_match(db,version)['attempt_id']==current
    finally:
        db.invalid_jobs.delete_many({'dataset_version':version});db.datasets.delete_one({'_id':version})
