import json
import time
from functools import partial
from pyspark.sql import functions as F, Window
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, BooleanType, ArrayType
from bigdata.normalize import normalize
from bigdata.quality import quality_metrics
from bigdata.spark_session import spark_session
from recruitment.adapters.mongo import database
from recruitment.domain.common import now, AppError
from recruitment.infrastructure.config import settings

STRING_FIELDS = ['raw_record_ref','source_job_key','error_code','job_title','job_title_normalized',
 'company_name','company_key','source','province','industry','seniority_level','education_level',
 'remote_type','employment_type','job_description','posted_at','source_url','salary_original_text',
 'salary_quality_status','salary_currency','salary_period','salary_basis','salary_parse_method',
 'fx_rate_reference','fx_rate_date','global_duplicate_ref']
SCHEMA = StructType([StructField(k,StringType()) for k in STRING_FIELDS] + [
 StructField(k,DoubleType()) for k in ['experience_years','salary_min','salary_max','salary_min_vnd','salary_max_vnd','salary_mid_vnd']] + [
 StructField('record_number',LongType()),StructField('salary_is_disclosed',BooleanType()),
 StructField('required_skills',ArrayType(StringType())),
 StructField('salary_normalization_assumptions',ArrayType(StringType()))])


def transform(spark, raw_file, source, normalization=None):
    raw = spark.read.schema('record_number long, raw_record_ref string, payload_json string').json(raw_file).repartition(4)
    convert = F.udf(lambda payload, ref, number: normalize(payload,ref,number,source,normalization), SCHEMA)
    df = raw.select(convert('payload_json','raw_record_ref','record_number').alias('row')).select('row.*')
    valid = df.filter(F.col('error_code').isNull() & F.col('global_duplicate_ref').isNull())
    window = Window.partitionBy('source_job_key').orderBy('record_number','raw_record_ref')
    ranked = valid.withColumn('rank',F.row_number().over(window)).withColumn('canonical_raw_ref',F.first('raw_record_ref').over(window))
    external=df.filter(F.col('error_code').isNull() & F.col('global_duplicate_ref').isNotNull()).withColumn('rank',F.lit(2)).withColumn('canonical_raw_ref',F.col('global_duplicate_ref'))
    return df, ranked.filter('rank = 1').drop('rank','canonical_raw_ref'), ranked.filter('rank > 1').unionByName(external), df.filter(F.col('error_code').isNotNull())


def write_partition(rows, collection, version, attempt, mongo_config):
    from pymongo import UpdateOne, MongoClient
    connection=MongoClient(**mongo_config)
    db=connection[mongo_config['authSource']];batch=[]
    for row in rows:
        record=row.asDict(recursive=True)
        record.update({'_id':attempt+':'+record['raw_record_ref'], 'dataset_version':version,
                       'attempt_id':attempt,'created_at':now(),'pipeline_version':'etl-v1'})
        if collection=='invalid_jobs':
            record.update({'validation_stage':'NORMALIZATION','error_message':record['error_code'],
                           'field_errors':[{'code':record['error_code']}],'detected_at':now(),'retryable':False})
        elif collection=='duplicate_jobs':
            record.update({'match_strategy':'SOURCE_KEY_OR_CONTENT_HASH','reason':'Stable key matches canonical record','detected_at':now()})
        batch.append(UpdateOne({'_id':record['_id']},{'$set':record},upsert=True))
        if len(batch)>=500:
            db[collection].bulk_write(batch,ordered=False);batch.clear()
    if batch:db[collection].bulk_write(batch,ordered=False)
    connection.close()


def classified_output(clean, duplicates, invalid):
    columns=SCHEMA.fieldNames()
    return (clean.select(*columns).withColumn('outcome',F.lit('clean'))
        .unionByName(duplicates.select(*columns).withColumn('outcome',F.lit('duplicate')))
        .unionByName(invalid.select(*columns).withColumn('outcome',F.lit('invalid'))))


def aggregate(clean):
    summary=clean.agg(F.count('*').alias('total_jobs'), F.countDistinct('company_key').alias('total_companies'),
        F.countDistinct(F.when(F.col('industry')!='Unknown',F.col('industry'))).alias('total_industries'),
        F.countDistinct(F.when(F.col('province')!='Unknown',F.col('province'))).alias('total_provinces'),
        F.min('posted_at').alias('posted_from'),F.max('posted_at').alias('posted_to'),
        F.count('salary_mid_vnd').alias('salary_sample_size'),
        F.avg('salary_mid_vnd').alias('mean_salary_vnd'),
        F.percentile_approx('salary_mid_vnd',[.25,.5,.75,.9],10000).alias('percentiles')).first().asDict()
    percentiles=summary.pop('percentiles') or [None]*4
    summary.update(dict(zip(['p25','median_salary_vnd','p75','p90'],percentiles)))
    def groups(column):
        rows = [r.asDict() for r in clean.groupBy(column).agg(F.count('*').alias('jobs'),
            F.count('salary_mid_vnd').alias('salary_sample_size'),F.avg('salary_mid_vnd').alias('mean_salary_vnd'),
            F.percentile_approx('salary_mid_vnd',[.25,.5,.75,.9],10000).alias('percentiles'))
            .orderBy(F.desc('jobs'),F.asc_nulls_last(column)).limit(100).collect()]
        from recruitment.application.analytics import describe_groups
        return describe_groups(rows)
    skills=[r.asDict() for r in clean.select(F.explode('required_skills').alias('skill')).groupBy('skill').count().orderBy(F.desc('count')).limit(30).collect()]
    trends=[r.asDict() for r in clean.filter(F.col('posted_at').isNotNull()).withColumn('month',F.substring('posted_at',1,7)).groupBy('month').count().orderBy('month').limit(120).collect()]
    hist=[r.asDict() for r in clean.filter(F.col('salary_mid_vnd').isNotNull()).withColumn('lower_vnd',F.floor(F.col('salary_mid_vnd')/5000000)*5000000).groupBy('lower_vnd').count().orderBy('lower_vnd').limit(100).collect()]
    return {'overview':summary,'industries':groups('industry'),'locations':groups('province'),
            'experience':groups('experience_years'),'companies':groups('company_name'),
            'skills':skills,'trends':trends,'histogram':hist}


def etl(db,job,guard):
    started=time.perf_counter();version=job['payload']['dataset_version'];attempt=job['attempt_id']
    dataset=db.datasets.find_one({'_id':version})
    config=db.system_settings.find_one({'_id':'normalization'})
    normalization=dataset.get('normalization_config') or (config['value'] if config else {})
    if dataset['status']=='PUBLISHED':
        raise AppError('IMMUTABLE_VERSION','Dataset đã được công bố, không ghi đè.',409)
    spark=spark_session('recruitment-etl-'+job['_id'])
    pointer_at_start=db.system_settings.find_one({'_id':'active_dataset'})
    spark.sparkContext.setJobGroup(job['_id'],'Recruitment ETL',interruptOnCancel=True)
    if not db.datasets.update_one({'_id':version,'status':{'$ne':'PUBLISHED'}},{'$set':{'status':'PROCESSING','active_attempt':attempt,'normalization_config':normalization}}).modified_count:
        spark.stop();raise AppError('IMMUTABLE_VERSION','Version đã được công bố.',409)
    frames=[]
    try:
        all_rows,clean,duplicates,invalid=transform(spark,dataset['raw_file_ref'],dataset['source'],normalization)
        frames=[all_rows.cache(),clean.cache(),duplicates.cache(),invalid.cache()]
        counts=dict(zip(['raw','clean','duplicate','invalid'],[frame.count() for frame in frames]))
        if counts['raw'] != counts['clean']+counts['invalid']+counts['duplicate']:
            raise AppError('ETL_RECONCILIATION_FAILED','Số bản ghi raw không khớp phân loại.',500)
        for frame,collection in [(clean,'cleaned_jobs'),(invalid,'invalid_jobs'),(duplicates,'duplicate_jobs')]:
            s=settings()
            mongo_config={'host':s.mongo_host,'username':s.mongo_user,'password':s.mongo_password.get_secret_value(),
                          'authSource':s.mongo_database,'serverSelectionTimeoutMS':5000}
            guard();frame.foreachPartition(partial(write_partition,collection=collection,version=version,attempt=attempt,mongo_config=mongo_config))
        valid_rate=(counts['raw']-counts['invalid'])/counts['raw'] if counts['raw'] else 0
        usable=clean.filter(F.col('salary_mid_vnd')>0).count()
        threshold=normalization.get('validity_min',.9)
        fields=['job_title','company_name','source','province','industry','experience_years','posted_at','salary_mid_vnd']
        missing=all_rows.agg(*[F.sum(F.when(F.col(c).isNull() | F.trim(F.col(c).cast('string')).isin('', 'Unknown'),1).otherwise(0)).alias(c) for c in fields]).first().asDict()
        missing={k:int(v or 0) for k,v in missing.items()}
        salary_consistent=F.col('salary_mid_vnd').isNull() | ((F.col('salary_min_vnd')>0) & (F.col('salary_max_vnd')>=F.col('salary_min_vnd')) &
            (F.abs(F.col('salary_mid_vnd')-(F.col('salary_min_vnd')+F.col('salary_max_vnd'))/2)<1))
        rules=(F.length('job_title')>0) & (F.length('company_name')>0) & (F.col('experience_years').isNull() | F.col('experience_years').between(0,60)) & salary_consistent
        consistent=clean.filter(rules).count()
        eligible=clean.filter((F.col('salary_mid_vnd')>0) & (F.col('salary_basis')!='NET')).count()
        recent=clean.filter(F.to_timestamp('posted_at').between(F.current_timestamp()-F.expr('INTERVAL 180 DAYS'),F.current_timestamp())).count()
        report={'_id':attempt,'dataset_version':version,'attempt_id':attempt,'counts':counts,
            **quality_metrics(counts,missing,consistent,usable,eligible,recent),
            'thresholds':{'validity_min':threshold},'passed':valid_rate>=threshold and counts['clean']>0,'generated_at':now(),'normalization_config':normalization}
        report['reasons']=[] if report['passed'] else ['VALIDITY_BELOW_THRESHOLD_OR_NO_CLEAN_RECORDS']
        db.data_quality_reports.replace_one({'_id':attempt},report,upsert=True)
        if not report['passed']:
            db.datasets.update_one({'_id':version,'active_attempt':attempt,'status':{'$ne':'PUBLISHED'}},{'$set':{'status':'FAILED'}})
            raise AppError('QUALITY_GATE_FAILED',f'Chất lượng không đạt: validity phải ≥{threshold:.0%} và có ít nhất một clean record.')
        analytics=aggregate(clean);guard()
        db.analytics_snapshots.replace_one({'_id':attempt},{'_id':attempt,'dataset_version':version,
            'attempt_id':attempt,'data':analytics,'sample_size':counts['clean'],'is_demo':dataset['is_demo'],
            'analytics_schema_version':2,
            'method':'spark-sql-v2; percentile_approx accuracy=10000','updated_at':now()},upsert=True)
        owned={'_id':job['_id'],'fencing_token':job['fencing_token'],'status':'RUNNING','cancel_requested':False,'lease_until':{'$gt':now()}}
        if not db.etl_jobs.update_one(owned,{'$set':{'status':'COMMITTING'}}).modified_count:
            guard();raise AppError('LEASE_LOST','Không còn quyền công bố.')
        committed=db.datasets.update_one({'_id':version,'active_attempt':attempt,'status':'PROCESSING'},{'$set':{
            'status':'PUBLISHED','published_attempt_id':attempt,'published_at':now(),'row_counts':counts}})
        if not committed.modified_count:
            raise AppError('PUBLICATION_CONFLICT','Một attempt khác đã công bố version này.')
        # One-document pointer is atomic; a completed immutable snapshot is already available.
        if pointer_at_start:
            activated=db.system_settings.update_one({'_id':'active_dataset','revision':pointer_at_start['revision']},
                {'$set':{'value':version,'updated_at':now()},'$inc':{'revision':1}}).modified_count==1
        else:
            from pymongo.errors import DuplicateKeyError
            try:
                db.system_settings.insert_one({'_id':'active_dataset','value':version,'updated_at':now(),'revision':1});activated=True
            except DuplicateKeyError:activated=False
        return {'counts':counts,'spark_application_id':spark.sparkContext.applicationId,
            'elapsed_seconds':time.perf_counter()-started,'executors':spark.sparkContext._jsc.sc().getExecutorMemoryStatus().size()-1,'auto_activated':activated}
    finally:
        for frame in frames:frame.unpersist()
        spark.stop()
