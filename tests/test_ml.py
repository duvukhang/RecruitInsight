import json
import math
import numpy as np
import pytest
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
import joblib
from machine_learning.features import features
from machine_learning.training import split,metrics
from machine_learning.serving import load
from recruitment.infrastructure.config import settings
from recruitment.domain.common import uid


def test_no_label_leakage_and_group_split():
    record={'job_title':'Engineer','experience_years':2,'salary_mid_vnd':999999,'salary_original_text':'999999 VND','salary_quality_status':'VALID_RANGE'}
    encoded=features(record)
    assert not any('salary' in k for k in encoded)
    records=[{'company_key':str(i%40)} for i in range(400)]
    a,b,c=split(records)
    groups=[{records[i]['company_key'] for i in part} for part in (a,b,c)]
    assert not (groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2])
    assert len(set(a)|set(b)|set(c))==400


def test_missing_experience_is_a_distinct_feature_and_split_is_reproducible():
    assert features({'experience_years':None}) != features({'experience_years':0})
    assert features({'experience_years':None})['experience_missing']==1
    records=[{'company_key':str(i%40)} for i in range(400)]
    assert all(np.array_equal(a,b) for a,b in zip(split(records),split(records)))
    for r in records:r['source_job_key']='repost'
    with pytest.raises(Exception) as error:split(records)
    assert error.value.code=='DUPLICATE_SPLIT_LEAKAGE'


def test_error_slices_require_samples_and_include_all_dimensions():
    from machine_learning.evaluation import grouped_errors
    records=[{'industry':'IT','province':'HCM','experience_years':2,'salary_mid_vnd':20_000_000,'job_title':'Engineer'} for _ in range(31)]
    records[-1]['province']='small'
    actual=[20_000_000]*31;predicted=[19_000_000]*31
    rows,policy=grouped_errors(records,actual,predicted)
    assert {r['dimension'] for r in rows}=={'industry','province','experience_group','salary_band','title_group'}
    assert all(r['n']>=30 and r['metrics']['mae']==1_000_000 and r['metrics']['r2'] is None for r in rows)
    assert policy['suppressed_group_counts']['province']==1
    assert next(r for r in rows if r['dimension']=='province')['n']==30


def test_prediction_preserves_provenance_and_warns_outside_training(monkeypatch):
    from types import SimpleNamespace
    import machine_learning.serving as serving
    model={'_id':'model-test','dataset_version':'dataset-test','artifact_uri':'unused','artifact_sha256':'unused',
        'feature_schema_version':'dict-v2','known_titles':['engineer'],'known_categories':{'province':['hcm']},
        'experience_range':[1,5],'is_demo':True,'reference_period':{'from':'2026-01-01','to':'2026-02-01'},
        'test_metrics':{'mae':100}}
    saved=[]
    db=SimpleNamespace(system_settings=SimpleNamespace(find_one=lambda q:{'value':model['_id']}),
        model_registry=SimpleNamespace(find_one=lambda q:model),
        salary_predictions=SimpleNamespace(insert_one=saved.append))
    monkeypatch.setattr(serving,'load',lambda *args:SimpleNamespace(predict=lambda rows:[20_000_000]))
    result=serving.predict(db,{'job_title':'Unknown title','province':'HN','experience_years':8},'test-user')
    assert result['model_version']=='model-test' and result['dataset_version']=='dataset-test'
    assert result['reference_period']==model['reference_period']
    assert set(result['warnings'])=={'UNSEEN_JOB_TITLE','UNSEEN_PROVINCE','EXPERIENCE_OUTSIDE_TRAINING_RANGE','DEMO_MODEL_NOT_MARKET_ESTIMATE'}
    assert saved==[result]
    assert 'confidence' not in result and 'interval' not in result


def test_local_training_candidates_share_manifest_and_select_on_validation(monkeypatch,tmp_path):
    """Real local fits/artifacts; Mongo persistence and Spark are explicit test doubles."""
    import sys
    from types import SimpleNamespace
    import machine_learning.training as training
    records=[{'_id':str(i).zfill(4),'company_key':str(i%40),'job_title':'Engineer',
        'industry':'IT','province':'HCM','experience_years':None if i%17==0 else i%10,
        'salary_mid_vnd':float(10_000_000+(i%10)*2_000_000),'salary_basis':'UNKNOWN',
        'source_job_key':str(i),'required_skills':['python']} for i in range(400)]
    class Collection:
        def __init__(self):self.rows=[]
        def insert_one(self,record):self.rows.append(record)
    class Cursor(list):
        def sort(self,*args):return self
    db=SimpleNamespace(cleaned_jobs=SimpleNamespace(find=lambda q:Cursor(records)),
        model_registry=Collection(),ml_experiments=Collection())
    monkeypatch.setattr(training,'published',lambda *args:({'_id':'TEST','is_demo':True},{}))
    monkeypatch.setattr(training,'settings',lambda:SimpleNamespace(data_root=tmp_path))
    import machine_learning.tracking as tracking
    monkeypatch.setattr(tracking,'log_model',lambda *args:None)
    monkeypatch.setitem(sys.modules,'machine_learning.spark_training',SimpleNamespace(train_spark=lambda *args:'TEST-SPARK-NOT-RUN'))
    result=training.train(db,{'_id':'TEST-JOB','payload':{'dataset_version':'TEST'}},lambda:None)
    assert {r['algorithm'] for r in db.model_registry.rows}=={'baseline','linear','random_forest','gradient_boosting','xgboost'}
    winner=min(db.model_registry.rows,key=lambda r:(r['validation_metrics']['mae'],r['validation_metrics']['rmse']))
    assert result['selected_algorithm']==winner['algorithm']
    assert [r['algorithm'] for r in db.model_registry.rows if r['selected_by_validation']]==[winner['algorithm']]
    manifests=[r['split_manifest'] for r in db.ml_experiments.rows]
    assert all(m==manifests[0] for m in manifests)
    assert manifests[0]['validation_seed']==43
    for row in db.model_registry.rows:
        path=tmp_path/'artifacts'/row['_id']
        saved=json.loads((path/'holdout.json').read_text())
        assert [p['record_id'] for p in saved]==manifests[0]['test']
        assert metrics([p['actual'] for p in saved],[p['predicted'] for p in saved])==row['test_metrics']
        restored=joblib.load(path/'model.joblib')
        first=next(r for r in records if r['_id']==saved[0]['record_id'])
        assert restored.predict([features(first)])[0]==pytest.approx(saved[0]['predicted'])


def test_known_metrics_and_artifact_roundtrip():
    score=metrics([10,20,30],[12,18,33])
    assert score['mae']==pytest.approx(7/3)
    assert score['rmse']==pytest.approx(math.sqrt(17/3))
    path=settings().data_root/'artifacts'/uid();path.mkdir(parents=True)
    target=path/'model.joblib'
    model=Pipeline([('features',DictVectorizer()),('model',Ridge(solver='lsqr'))]).fit([{'experience_years':float(i)} for i in range(20)],[100+10*i for i in range(20)])
    joblib.dump(model,target)
    import hashlib
    try:
        restored=load(str(target),hashlib.sha256(target.read_bytes()).hexdigest())
        assert restored.predict([{'experience_years':5.0}])[0]==pytest.approx(model.predict([{'experience_years':5.0}])[0])
        with pytest.raises(Exception):load(str(target),'incorrect-checksum')
    finally:
        load.cache_clear();target.unlink();path.rmdir()
