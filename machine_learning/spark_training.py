import hashlib
import json
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from bigdata.spark_session import spark_session
from bigdata.etl import transform
from recruitment.domain.common import now,uid
from recruitment.infrastructure.config import settings
from machine_learning.training import metrics


def train_spark(db,job,dataset,records,train_idx,val_idx,test_idx,guard):
    """Full training groups, one numeric feature; reported as a separate scale experiment."""
    spark=spark_session('recruitment-spark-ml-'+job['_id'])
    spark.sparkContext.setJobGroup(job['_id'],'Salary training',interruptOnCancel=True)
    version=uid();directory=settings().data_root/'artifacts'/version;directory.mkdir(parents=True)
    try:
        _,clean,_,_=transform(spark,dataset['raw_file_ref'],dataset['source'],dataset.get('normalization_config'))
        companies=sorted({records[i]['company_key'] for i in train_idx})
        from pyspark.sql import functions as F
        train=clean.filter(F.col('company_key').isin(companies)&(F.col('salary_mid_vnd')>0)&(F.col('salary_basis')!='NET')&F.col('experience_years').isNotNull())
        count=train.count();guard()
        from recruitment.domain.common import AppError
        val_idx=[i for i in val_idx if records[i].get('experience_years') is not None]
        test_idx=[i for i in test_idx if records[i].get('experience_years') is not None]
        if count<100 or min(len(val_idx),len(test_idx))<30:
            raise AppError('INSUFFICIENT_TRAINING_DATA','Spark numeric cần 100 train và 30 validation/test có kinh nghiệm quan sát được.',422)
        experience_bounds=train.agg(F.min('experience_years'),F.max('experience_years')).first()
        pipeline=Pipeline(stages=[VectorAssembler(inputCols=['experience_years'],outputCol='features'),
            LinearRegression(featuresCol='features',labelCol='salary_mid_vnd',regParam=.1,maxIter=50)])
        fitted=pipeline.fit(train)
        def evaluate(indices):
            values=[(records[i]['_id'],float(records[i]['experience_years']),float(records[i]['salary_mid_vnd'])) for i in indices]
            frame=spark.createDataFrame(values,'record_id string, experience_years double, salary_mid_vnd double')
            predicted=fitted.transform(frame).select('record_id','salary_mid_vnd','prediction').collect()
            return metrics([r['salary_mid_vnd'] for r in predicted],[r['prediction'] for r in predicted]), predicted
        validation,_=evaluate(val_idx);test_score,test_predictions=evaluate(test_idx)
        predictions=[{'record_id':r['record_id'],'actual':float(r['salary_mid_vnd']),
            'predicted':float(r['prediction']),'residual':float(r['salary_mid_vnd']-r['prediction'])} for r in test_predictions]
        (directory/'holdout.json').write_text(json.dumps(predictions),encoding='utf-8')
        manifest={'strategy':'company-group-shuffle-70/15/15','seed':42,'validation_seed':43,
            'dataset_version':dataset['_id'],'attempt_id':dataset['published_attempt_id'],
            'training_companies':companies,'training_count':count,
            'validation':[records[i]['_id'] for i in val_idx],'test':[records[i]['_id'] for i in test_idx],
            'eligibility':'positive monthly midpoint, non-NET, observed experience; train companies selected by local manifest',
            'comparison_group':'full-data-numeric-scale; not directly comparable to local models'}
        (directory/'split.json').write_text(json.dumps(manifest),encoding='utf-8')
        fitted.write().overwrite().save(str(directory/'spark-pipeline'))
        linear=fitted.stages[-1]
        from machine_learning.plots import diagnostics
        importance=diagnostics(directory,None,predictions,[('experience_years',float(linear.coefficients[0]))])
        artifact=directory/'model.json'
        artifact.write_text(json.dumps({'coefficient':float(linear.coefficients[0]),'intercept':float(linear.intercept)}),encoding='utf-8')
        record={'_id':version,'training_job_id':job['_id'],'algorithm':'spark_linear_numeric',
            'dataset_version':dataset['_id'],'validation_metrics':validation,'test_metrics':test_score,
            'feature_schema_version':'experience-v1','comparison_group':'full-data-numeric-scale',
            'training_count':count,'spark_application_id':spark.sparkContext.applicationId,
            'split_manifest':manifest,'feature_importance':importance,
            'artifact_uri':str(artifact),'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
            'status':'CANDIDATE','is_demo':dataset['is_demo'],'registered_at':now(),'created_at':now(),
            'selected_by_validation':False,'sample_counts':{'train':count,'validation':len(val_idx),'test':len(test_idx)},
            'known_titles':[],'experience_range':[float(experience_bounds[0]),float(experience_bounds[1])]}
        db.model_registry.insert_one(record)
        db.ml_experiments.insert_one({**record,'created_at':now()})
        from machine_learning.tracking import log_model
        run_id=log_model(record)
        if run_id:
            db.model_registry.update_one({'_id':version},{'$set':{'mlflow_run_id':run_id}})
            db.ml_experiments.update_one({'_id':version},{'$set':{'mlflow_run_id':run_id}})
        return version
    finally:
        spark.stop()
