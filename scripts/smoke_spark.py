"""Run inside etl-worker: verify a real standalone Spark action."""
import json
from bigdata.spark_session import spark_session

spark = spark_session('recruitment-infrastructure-smoke')
try:
    result = spark.range(10000, numPartitions=8).selectExpr('id % 7 AS bucket').groupBy('bucket').count().collect()
    assert sum(row['count'] for row in result) == 10000
    executor_count = spark.sparkContext._jsc.sc().getExecutorMemoryStatus().size() - 1
    assert executor_count >= 2, f'Expected 2 executors, observed {executor_count}'
    print(json.dumps({'application_id': spark.sparkContext.applicationId,
                      'rows': 10000, 'executors': executor_count, 'result': 'PASS'}))
finally:
    spark.stop()
