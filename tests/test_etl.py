from pathlib import Path
import json
import os
import pytest
from bigdata.spark_session import spark_session
from bigdata.etl import transform, aggregate, classified_output
from recruitment.infrastructure.config import settings
from recruitment.infrastructure.init_db import migrate
from recruitment.adapters.mongo import database
from recruitment.adapters.jobs import MongoJobs
from recruitment.domain.common import uid, now, AppError


@pytest.mark.skipif(os.getenv('RUN_SPARK_TESTS') != '1', reason='Run in etl-worker with RUN_SPARK_TESTS=1 for routable driver')
def test_distributed_transform_counts():
    path=settings().data_root/'uploads'/'test-etl-fixture.raw.jsonl'
    values=[{'job_title':'Engineer','company_name':'A','source_job_id':'1','salary':'10–20 triệu VND/tháng'},
            {'job_title':'Engineer','company_name':'A','source_job_id':'1','salary':'10–20 triệu VND/tháng'},
            {'job_title':'','company_name':'A'},
            {'job_title':'Analyst','company_name':'B','source_job_id':'2','salary':'Negotiable'}]
    path.write_text('\n'.join(json.dumps({'record_number':i,'raw_record_ref':str(i),'payload_json':json.dumps(v)}) for i,v in enumerate(values)),encoding='utf-8')
    spark=spark_session('recruitment-etl-integration')
    try:
        raw,clean,duplicates,invalid=transform(spark,str(path),'TEST')
        assert [x.count() for x in [raw,clean,duplicates,invalid]]==[4,2,1,1]
        assert duplicates.first()['canonical_raw_ref']=='0'
        stats=aggregate(clean)['overview']
        assert stats['total_jobs']==2
        assert stats['salary_sample_size']==1
        assert stats['median_salary_vnd']==15000000
        assert clean.filter('experience_years is null').count()==2
        grouped=aggregate(clean)['industries'][0]
        assert grouped['median_salary_vnd']==15000000
        assert grouped['warnings']==['SMALL_SALARY_SAMPLE']
    finally:
        spark.stop();path.unlink(missing_ok=True)


@pytest.mark.skipif(os.getenv('RUN_SPARK_TESTS') != '1', reason='Dedicated Spark integration run')
def test_benchmark_uses_production_outcomes_for_invalid_and_external_duplicates():
    path=settings().data_root/'uploads'/'test-benchmark-outcomes.raw.jsonl'
    values=[{'job_title':'','company_name':'A','source_job_id':'same'},
            {'job_title':'Engineer','company_name':'A','source_job_id':'same'},
            {'job_title':'Engineer','company_name':'A','source_job_id':'same'},
            {'job_title':'Engineer','company_name':'B','source_job_id':'other','_global_duplicate_ref':'previous'}]
    path.write_text('\n'.join(json.dumps({'record_number':i,'raw_record_ref':str(i),'payload_json':json.dumps(v)}) for i,v in enumerate(values)),encoding='utf-8')
    spark=spark_session('benchmark-outcome-regression')
    try:
        _,clean,duplicates,invalid=transform(spark,str(path),'TEST')
        classified=classified_output(clean,duplicates,invalid)
        assert {r['outcome']:r['count'] for r in classified.groupBy('outcome').count().collect()}=={'clean':1,'duplicate':2,'invalid':1}
        assert duplicates.filter("source_job_key = 'TEST:same'").first()['canonical_raw_ref']=='1'
    finally:
        spark.stop();path.unlink(missing_ok=True)


@pytest.mark.skipif(os.getenv('RUN_SPARK_TESTS') != '1', reason='Dedicated Spark integration run')
def test_publish_and_quality_failure_preserves_pointer():
    from bigdata.etl import etl
    db=database();assert db.name.endswith('_test');migrate(db)
    versions=[];attempts=[];paths=[];jobs=[]
    pointer=db.system_settings.find_one({'_id':'active_dataset'})
    try:
        for should_pass in [True,False]:
            version=uid();versions.append(version)
            path=settings().data_root/'uploads'/(version+'.raw.jsonl');paths.append(path)
            rows=[]
            for i in range(20):
                value={'job_title':'Engineer' if should_pass or i<5 else '', 'company_name':'A',
                       'source_job_id':str(i), 'salary':'10–20 triệu VND/tháng'}
                rows.append(json.dumps({'record_number':i,'raw_record_ref':version+':'+str(i),'payload_json':json.dumps(value)}))
            path.write_text('\n'.join(rows),encoding='utf-8')
            db.datasets.insert_one({'_id':version,'dataset_id':version,'status':'RAW_READY','is_demo':True,
                'created_at':now(),'created_by':'etl-test','idempotency_key':version,'raw_file_ref':str(path),'source':'TEST'})
            repository=MongoJobs(db);queued=repository.enqueue('ETL_TEST',{'dataset_version':version},'test');jobs.append(queued['_id'])
            job=repository.claim(['ETL_TEST'],'test');attempts.append(job['attempt_id'])
            if should_pass:
                result=etl(db,job,lambda:None)
                assert result['counts']['clean']==20
                assert db.system_settings.find_one({'_id':'active_dataset'})['value']==version
                active=version
                assert db.cleaned_jobs.count_documents({'dataset_version':version,'attempt_id':job['attempt_id']})==20
            else:
                with pytest.raises(AppError) as failure:
                    etl(db,job,lambda:None)
                assert failure.value.code=='QUALITY_GATE_FAILED'
                assert db.system_settings.find_one({'_id':'active_dataset'})['value']==active
    finally:
        for name in ['cleaned_jobs','invalid_jobs','duplicate_jobs','data_quality_reports','analytics_snapshots']:
            db[name].delete_many({'dataset_version':{'$in':versions}})
        db.datasets.delete_many({'_id':{'$in':versions}});db.etl_jobs.delete_many({'_id':{'$in':jobs}})
        db.system_settings.delete_one({'_id':'active_dataset'})
        if pointer:db.system_settings.insert_one(pointer)
        for path in paths:path.unlink(missing_ok=True)
