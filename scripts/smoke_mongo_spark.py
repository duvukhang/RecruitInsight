"""Run with SPARK_PACKAGES=org.mongodb.spark:mongo-spark-connector_2.12:10.7.0."""
import json
from urllib.parse import quote_plus
from pyspark.sql import functions as F
from recruitment.infrastructure.config import settings
from recruitment.adapters.mongo import database
from recruitment.application.datasets import published
from recruitment.domain.common import now
from bigdata.spark_session import spark_session
s=settings();db=database();dataset,match=published(db)
uri=f'mongodb://{quote_plus(s.mongo_user)}:{quote_plus(s.mongo_password.get_secret_value())}@{s.mongo_host}:27017/?authSource={s.mongo_database}'
spark=spark_session('recruitment-mongo-connector-integration')
try:
    frame=(spark.read.format('mongodb').option('connection.uri',uri).option('database',s.mongo_database)
           .option('collection','cleaned_jobs').option('aggregation.pipeline',json.dumps([{'$match':match}])).load())
    # Reading actual rows prevents a count-only server pushdown from masquerading as a connector scan.
    counts=frame.select('source_job_key').repartition(4).rdd.mapPartitions(lambda rows:[sum(1 for _ in rows)]).collect()
    expected=db.cleaned_jobs.count_documents(match);assert sum(counts)==expected
    result={'result':'PASS','connector':'10.7.0','rows':sum(counts),'partition_counts':counts,'application_id':spark.sparkContext.applicationId}
    db.audit_logs.insert_one({'action':'MONGO_SPARK_CONNECTOR_TEST','details':result,'created_at':now()})
    print(json.dumps(result))
finally:spark.stop()
