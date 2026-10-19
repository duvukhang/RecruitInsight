import hashlib
import math
import json
from functools import lru_cache
from pathlib import Path
import joblib
from machine_learning.features import features
from recruitment.infrastructure.config import settings
from recruitment.domain.common import AppError,now,uid


class NumericLinear:
    def __init__(self,data):self.data=data
    def predict(self,rows):
        return [self.data['intercept']+self.data['coefficient']*row['experience_years'] for row in rows]


@lru_cache(maxsize=4)
def load(path,sha):
    root=(settings().data_root/'artifacts').resolve()
    target=Path(path).resolve()
    if not target.is_relative_to(root) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
        raise AppError('ARTIFACT_INVALID','Artifact không tồn tại hoặc checksum không khớp.',503)
    return NumericLinear(json.loads(target.read_text())) if target.suffix=='.json' else joblib.load(target)


def predict(db,body,user_id):
    pointer=db.system_settings.find_one({'_id':'active_model'})
    if not pointer:
        raise AppError('MODEL_NOT_AVAILABLE','Chưa có model active. Hãy huấn luyện và chọn model.',503)
    model=db.model_registry.find_one({'_id':pointer['value']})
    fallback=False
    try:
        if not model:raise ValueError('Missing model')
        pipeline=load(model['artifact_uri'],model['artifact_sha256'])
    except Exception:
        previous=db.model_registry.find_one({'_id':pointer.get('previous_value')})
        try:
            if not previous:raise ValueError('Missing fallback')
            pipeline=load(previous['artifact_uri'],previous['artifact_sha256']);model=previous;fallback=True
        except Exception:raise AppError('MODEL_NOT_AVAILABLE','Không có artifact model đã xác minh để dự đoán.',503)
    value=float(pipeline.predict([features(body)])[0])
    if not math.isfinite(value) or value<=0:
        raise AppError('INVALID_PREDICTION','Model không trả mức lương hợp lệ cho dữ liệu này.',503)
    warnings=['ACTIVE_ARTIFACT_FAILED_USING_PREVIOUS_MODEL'] if fallback else []
    if model['feature_schema_version']=='dict-v1' and body['job_title'].lower() not in model.get('known_titles',[]):warnings.append('UNSEEN_JOB_TITLE')
    lower,upper=model.get('experience_range',[0,60])
    if not lower<=body['experience_years']<=upper:warnings.append('EXPERIENCE_OUTSIDE_TRAINING_RANGE')
    if model['is_demo']:warnings.append('DEMO_MODEL_NOT_MARKET_ESTIMATE')
    reference=model.get('reference_period')
    if reference is None:
        dataset=db.datasets.find_one({'_id':model['dataset_version']})
        values=list(db.cleaned_jobs.aggregate([{'$match':{'dataset_version':model['dataset_version'],
            'attempt_id':dataset['published_attempt_id'],'posted_at':{'$type':'string'}}},
            {'$group':{'_id':None,'from':{'$min':'$posted_at'},'to':{'$max':'$posted_at'}}}],maxTimeMS=5000)) if dataset else []
        reference={k:values[0][k] for k in ['from','to']} if values else {'from':None,'to':None}
        db.model_registry.update_one({'_id':model['_id']},{'$set':{'reference_period':reference}})
    result={'_id':uid(),'user_id':user_id,'model_version':model['_id'],'dataset_version':model['dataset_version'],
        'input_features':body,'predicted_salary_vnd':round(value),'currency':'VND','period':'MONTH',
        'created_at':now(),'model_metrics':model['test_metrics'],'warnings':warnings,'is_demo':model['is_demo'],'reference_period':reference}
    result['prediction_id']=result['_id'];result['prediction_timestamp']=result['created_at']
    db.salary_predictions.insert_one(result)
    return result
