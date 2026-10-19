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
