from pyspark.sql import SparkSession
import os
from recruitment.infrastructure.config import settings


def spark_session(name):
    s = settings()
    builder=(SparkSession.builder.appName(name).master(s.spark_master)
            .config('spark.driver.host', s.spark_driver_host)
            .config('spark.driver.bindAddress', '0.0.0.0')
            .config('spark.executor.memory', '1g')
            .config('spark.cores.max', os.environ.get('SPARK_MAX_CORES','2'))
            .config('spark.executor.cores', '1')
            .config('spark.sql.shuffle.partitions', '4')
            .config('spark.eventLog.enabled', 'true')
            .config('spark.eventLog.dir', '/data/events')
            .config('spark.ui.enabled', 'false'))
    builder=builder.config('spark.redaction.regex','(?i)secret|password|token|credential|connection[.]uri')
    builder=builder.config('spark.sql.redaction.options.regex','(?i)url|uri|secret|password|token|credential')
    if os.environ.get('SPARK_PACKAGES'):
        builder=builder.config('spark.jars.packages',os.environ['SPARK_PACKAGES']).config('spark.jars.repositories','https://repo.maven.apache.org/maven2')
    return builder.getOrCreate()
