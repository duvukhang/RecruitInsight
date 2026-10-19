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
        train=clean.filter(F.col('company_key').isin(companies)&F.col('salary_mid_vnd').isNotNull()&(F.col('salary_basis')!='NET'))
        count=train.count();guard()
        experience_bounds=train.agg(F.min('experience_years'),F.max('experience_years')).first()
        pipeline=Pipeline(stages=[VectorAssembler(inputCols=['experience_years'],outputCol='features'),
            LinearRegression(featuresCol='features',labelCol='salary_mid_vnd',regParam=.1,maxIter=50)])
        fitted=pipeline.fit(train)
        def evaluate(indices):
            values=[(float(records[i]['experience_years']),float(records[i]['salary_mid_vnd'])) for i in indices]
            frame=spark.createDataFrame(values,'experience_years double, salary_mid_vnd double')
            predicted=fitted.transform(frame).select('salary_mid_vnd','prediction').collect()
            return metrics([r[0] for r in predicted],[r[1] for r in predicted])
        validation=evaluate(val_idx);test_score=evaluate(test_idx)
        fitted.write().overwrite().save(str(directory/'spark-pipeline'))
        linear=fitted.stages[-1]
        artifact=directory/'model.json'
        artifact.write_text(json.dumps({'coefficient':float(linear.coefficients[0]),'intercept':float(linear.intercept)}),encoding='utf-8')
        record={'_id':version,'training_job_id':job['_id'],'algorithm':'spark_linear_numeric',
            'dataset_version':dataset['_id'],'validation_metrics':validation,'test_metrics':test_score,
            'feature_schema_version':'experience-v1','comparison_group':'full-data-numeric-scale',
            'training_count':count,'spark_application_id':spark.sparkContext.applicationId,
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
