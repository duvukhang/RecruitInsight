import pytest
from recruitment.adapters.mongo import database
from recruitment.infrastructure.init_db import migrate
from recruitment.application.analytics import AnalyticsService
from recruitment.domain.common import uid,now


def test_filtered_aggregation_and_version_scope():
    db=database();assert db.name.endswith('_test');migrate(db)
    version,attempt=uid(),uid()
    db.datasets.insert_one({'_id':version,'dataset_id':version,'created_by':'analytics-test','idempotency_key':version,
        'status':'PUBLISHED','published_attempt_id':attempt,'is_demo':True,'created_at':now()})
    records=[]
    for i,(province,value) in enumerate([('HCM',10000000),('HCM',None),('HN',30000000)]):
        records.append({'_id':uid(),'dataset_version':version,'attempt_id':attempt,'source_job_key':str(i),
            'job_title':'Engineer','company_key':str(i),'industry':'IT','province':province,'salary_mid_vnd':value,
            'required_skills':['python'],'experience_years':1,'company_name':str(i),'posted_at':'2026-10-01T00:00:00+00:00'})
    db.cleaned_jobs.insert_many(records)
    db.cleaned_jobs.update_one({'_id':records[0]['_id']},{'$set':{'posted_at':'2026-10-01T23:59:59.999999+00:00'}})
    try:
        service=AnalyticsService(db,version,province='HCM',industry='IT')
        overview=service.metric('overview')
        assert overview['data']['total_jobs']==2
        assert overview['data']['salary_sample_size']==1
        assert overview['data']['mean_salary_vnd']==10000000
        assert overview['meta']['missing_salary_rate']==.5
        assert service.metric('top-skills')['data']==[{'skill':'python','count':2}]
        assert len(service.metric('salary-by-location')['data'])==1
        assert AnalyticsService(db,version,province='HCM',posted_to='2026-10-01').metric('overview')['data']['total_jobs']==2
        empty=AnalyticsService(db,version,province='missing').metric('overview')
        assert empty['data']['total_jobs']==0
        assert empty['data']['median_salary_vnd'] is None
    finally:
        db.cleaned_jobs.delete_many({'dataset_version':version});db.datasets.delete_one({'_id':version})
