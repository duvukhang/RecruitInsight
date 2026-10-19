import hashlib
import json
import math
import random
from pathlib import Path
import joblib
import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor,GradientBoostingRegressor
from xgboost import XGBRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score,median_absolute_error
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from machine_learning.features import features
from recruitment.application.datasets import published
from recruitment.domain.common import AppError,now,uid
from recruitment.infrastructure.config import settings


def metrics(actual,predicted):
    values={'mae':mean_absolute_error(actual,predicted),'rmse':math.sqrt(mean_squared_error(actual,predicted)),
            'r2':r2_score(actual,predicted) if len(actual)>1 and len(set(actual))>1 else None,
            'median_absolute_error':median_absolute_error(actual,predicted)}
    return {k:float(v) if v is not None and math.isfinite(v) else None for k,v in values.items()}


def split(records):
    if len(records)<200 or len({r['company_key'] for r in records})<10:
        raise AppError('INSUFFICIENT_TRAINING_DATA','Cần ít nhất 200 labels và 10 doanh nghiệp độc lập.',422)
    groups=np.array([r['company_key'] for r in records])
    indices=np.arange(len(records))
    train_val,test=next(GroupShuffleSplit(n_splits=1,test_size=.15,random_state=42).split(indices,groups=groups))
    a,b=next(GroupShuffleSplit(n_splits=1,test_size=.15/.85,random_state=43).split(train_val,groups=groups[train_val]))
    train,val=train_val[a],train_val[b]
    if min(len(train),len(val),len(test))<30:
        raise AppError('INSUFFICIENT_TRAINING_DATA','Mỗi split cần ít nhất 30 labels.',422)
    return train,val,test


def reservoir(cursor,limit=10000):
    rng=random.Random(42);sample=[];total=0
    for total,record in enumerate(cursor,1):
        if len(sample)<limit:sample.append(record)
        else:
            index=rng.randrange(total)
            if index<limit:sample[index]=record
    return sorted(sample,key=lambda r:r['_id']),total


def train(db,job,guard):
    dataset,match=published(db,job['payload']['dataset_version'])
    eligible={**match,'salary_mid_vnd':{'$gt':0},'salary_basis':{'$ne':'NET'}}
    records,total=reservoir(db.cleaned_jobs.find(eligible).sort('_id',1))
    train_idx,val_idx,test_idx=split(records)
    x=[features(r) for r in records];y=np.array([r['salary_mid_vnd'] for r in records])
    manifest={name:[records[i]['_id'] for i in indices] for name,indices in [('train',train_idx),('validation',val_idx),('test',test_idx)]}
    manifest['strategy']='company-group-shuffle-70/15/15';manifest['seed']=42
    manifest['sample_limit']=10000;manifest['eligible_total']=total
    manifest['dataset_hash']=hashlib.sha256(json.dumps([(r['_id'],r['salary_mid_vnd']) for r in records],sort_keys=True).encode()).hexdigest()
    candidates=[]
    algorithms=[('baseline',DummyRegressor(strategy='median')),('linear',Ridge(alpha=10,solver='lsqr')),
        ('random_forest',RandomForestRegressor(n_estimators=80,max_depth=14,min_samples_leaf=2,random_state=42,n_jobs=1)),
        ('gradient_boosting',GradientBoostingRegressor(n_estimators=80,max_depth=3,random_state=42)),
        ('xgboost',XGBRegressor(n_estimators=100,max_depth=4,learning_rate=.08,random_state=42,n_jobs=1,tree_method='hist'))]
    for algorithm,model in algorithms:
        guard()
        pipeline=Pipeline([('features',DictVectorizer()),('model',model)])
        pipeline.fit([x[i] for i in train_idx],y[train_idx])
        score=metrics(y[val_idx],pipeline.predict([x[i] for i in val_idx]))
        candidates.append((algorithm,pipeline,score))
    # Freeze the winner using validation before evaluating the holdout.
    winner=min(candidates,key=lambda item:(item[2]['mae'],item[2]['rmse']))[0]
    results=[]
    for algorithm,pipeline,validation in candidates:
        guard();version=uid();directory=settings().data_root/'artifacts'/version;directory.mkdir(parents=True)
        artifact=directory/'model.joblib';joblib.dump(pipeline,artifact)
        test_pred=pipeline.predict([x[i] for i in test_idx]);test_score=metrics(y[test_idx],test_pred)
        (directory/'split.json').write_text(json.dumps(manifest),encoding='utf-8')
        predictions=[{'record_id':records[i]['_id'],'actual':float(y[i]),'predicted':float(pred),'residual':float(y[i]-pred)} for i,pred in zip(test_idx,test_pred)]
        (directory/'holdout.json').write_text(json.dumps(predictions),encoding='utf-8')
        from machine_learning.plots import diagnostics
        importance=diagnostics(directory,pipeline,predictions)
        sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
        experiment={'_id':version,'training_job_id':job['_id'],'algorithm':algorithm,'dataset_version':dataset['_id'],
            'validation_metrics':validation,'test_metrics':test_score,'split_manifest':manifest,
            'feature_schema_version':'dict-v1','parameters':str(pipeline['model'].get_params()),'created_at':now(),
            'feature_importance':importance,'split_strategy':manifest['strategy'],
            'slice_metrics':[{ 'province':province,'n':len(ids),'metrics':metrics(y[ids],pipeline.predict([x[i] for i in ids]))}
                for province in sorted({records[i]['province'] for i in test_idx})
                if (ids:=[i for i in test_idx if records[i]['province']==province])],
            'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        db.ml_experiments.insert_one(experiment)
        registry={'_id':version,'algorithm':algorithm,'dataset_version':dataset['_id'],'status':'CANDIDATE',
            'artifact_uri':str(artifact),'artifact_sha256':sha,'validation_metrics':validation,'test_metrics':test_score,
            'selected_by_validation':algorithm==winner,'is_demo':dataset['is_demo'],'feature_schema_version':'dict-v1',
            'registered_at':now(),'created_at':now(),'training_job_id':job['_id'],'sample_counts':{k:len(v) for k,v in [('train',train_idx),('validation',val_idx),('test',test_idx)]},
            'known_titles':sorted({records[i]['job_title'].lower() for i in train_idx}),
            'experience_range':[float(min(y['experience_years'] for y in [records[i] for i in train_idx])),float(max(y['experience_years'] for y in [records[i] for i in train_idx]))]}
        db.model_registry.insert_one(registry);results.append(version)
        from machine_learning.tracking import log_model
        run_id=log_model(registry,manifest)
        if run_id:
            db.model_registry.update_one({'_id':version},{'$set':{'mlflow_run_id':run_id}})
            db.ml_experiments.update_one({'_id':version},{'$set':{'mlflow_run_id':run_id}})
    guard()
    from machine_learning.spark_training import train_spark
    results.append(train_spark(db,job,dataset,records,train_idx,val_idx,test_idx,guard))
    return {'models':results,'selected_algorithm':winner,'eligible_total':total,'sample_size':len(records),
            'note':'Local models share a reservoir sample; Spark numeric uses full training-company data and is a separate scale experiment.'}
