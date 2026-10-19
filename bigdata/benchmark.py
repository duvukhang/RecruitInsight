"""Measure the same Spark normalization/window workload at different scales."""
import argparse,csv,hashlib,json,os,platform,statistics,time
from pathlib import Path
from pyspark.sql import functions as F,Window
from bigdata.etl import transform
from bigdata.spark_session import spark_session
from bigdata.ingestion import input_records
from recruitment.adapters.mongo import database
from recruitment.domain.common import uid,now
from recruitment.infrastructure.config import settings
from scripts.generate_demo import generate


def run(sizes=(100,10000,100000),repeats=3):
    if repeats<3:raise ValueError('At least three measured repetitions are required')
    run_id=uid();root=settings().data_root/'artifacts'/'evidence'/run_id;root.mkdir(parents=True)
    environment={'python':platform.python_version(),'platform':platform.platform(),'visible_cpus':os.cpu_count(),
        'seed':42,'cache':'OS cache uncontrolled; no Spark persist; warm-up excluded',
        'workload':'read JSONL + normalize UDF + deterministic dedup window + aggregate counts/checksum; excludes Mongo write and startup',
        'source_sha256':hashlib.sha256(Path('/app/bigdata/etl.py').read_bytes()+Path('/app/bigdata/normalize.py').read_bytes()).hexdigest()}
    db=database();db.benchmark_runs.insert_one({'_id':run_id,'status':'RUNNING','environment':environment,'created_at':now()})
    files={}
    for size in sizes:
        source=generate(root/f'DEMO-{size}.csv',size)
        path=root/f'DEMO-{size}.raw.jsonl'
        with path.open('w',encoding='utf-8') as output:
            for i,record in enumerate(input_records(source),1):
                output.write(json.dumps({'record_number':i,'raw_record_ref':str(i),'payload_json':json.dumps(record,ensure_ascii=False)},ensure_ascii=False)+'\n')
        files[size]=str(path)
    observations=[];fingerprints={}
    original_master=os.environ.get('SPARK_MASTER','spark://spark-master:7077')
    try:
        for configuration,master,cores in [('local1','local[1]',1),('cluster1',original_master,1),('cluster2',original_master,2)]:
            os.environ['SPARK_MASTER']=master;os.environ['SPARK_MAX_CORES']=str(cores);settings.cache_clear()
            spark=spark_session('benchmark-'+configuration+'-'+run_id)
            environment['spark']=spark.version
            try:
                for size in sizes:
                    for repetition in range(repeats+1):
                        started=time.perf_counter()
                        raw,_,_,_=transform(spark,files[size],'DEMO_BENCHMARK')
                        window=Window.partitionBy('source_job_key').orderBy(F.col('error_code').isNotNull().cast('int'),'record_number','raw_record_ref')
                        classified=raw.withColumn('rank',F.row_number().over(window)).withColumn('outcome',
                            F.when(F.col('error_code').isNotNull(),'invalid').when(F.col('rank')>1,'duplicate').otherwise('clean'))
                        result=classified.groupBy('outcome').agg(F.count('*').alias('count'),
                            F.sum(F.xxhash64('source_job_key','job_title','salary_mid_vnd','raw_record_ref')).alias('checksum')).collect()
                        elapsed=time.perf_counter()-started
                        fingerprint=sorted((r['outcome'],r['count'],r['checksum']) for r in result)
                        assert sum(r['count'] for r in result)==size
                        if size in fingerprints:assert fingerprint==fingerprints[size],'Outputs differ between configurations'
                        else:fingerprints[size]=fingerprint
                        if repetition==0:continue
                        observed_executors=spark.sparkContext._jsc.sc().getExecutorMemoryStatus().size()-1
                        if configuration.startswith('cluster') and observed_executors!=cores:
                            raise RuntimeError(f'Expected {cores} executors, observed {observed_executors}. Stop streaming/other Spark jobs before measuring.')
                        observation={'configuration':configuration,'rows':size,'repetition':repetition,'elapsed_seconds':elapsed,
                            'rows_per_second':size/elapsed,'spark_application_id':spark.sparkContext.applicationId,
                            'executors':observed_executors,'fingerprint':fingerprint}
                        observations.append(observation)
                        db.benchmark_runs.update_one({'_id':run_id},{'$push':{'observations':observation}})
                        print(json.dumps({k:v for k,v in observation.items() if k!='fingerprint'}),flush=True)
                    (root/f'plan-{configuration}-{size}.txt').write_text(classified._jdf.queryExecution().executedPlan().toString(),encoding='utf-8')
            finally:spark.stop()
        summary=[]
        for size in sizes:
            local=statistics.median(r['elapsed_seconds'] for r in observations if r['rows']==size and r['configuration']=='local1')
            for configuration in ['local1','cluster1','cluster2']:
                times=[r['elapsed_seconds'] for r in observations if r['rows']==size and r['configuration']==configuration]
                summary.append({'rows':size,'configuration':configuration,'median_seconds':statistics.median(times),
                    'min_seconds':min(times),'max_seconds':max(times),'speedup_vs_local1':local/statistics.median(times)})
        (root/'environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
        (root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        with (root/'observations.csv').open('w',newline='') as output:
            writer=csv.DictWriter(output,fieldnames=list(observations[0]));writer.writeheader();writer.writerows(observations)
        db.benchmark_runs.update_one({'_id':run_id},{'$set':{'status':'COMPLETED','summary':summary,'environment':environment,'finished_at':now(),'artifact_directory':str(root)}})
        print(json.dumps({'result':'PASS','run_id':run_id,'summary':summary}),flush=True)
        return {'run_id':run_id,'summary':summary}
    except Exception:
        db.benchmark_runs.update_one({'_id':run_id},{'$set':{'status':'FAILED','finished_at':now()}});raise
    finally:
        os.environ['SPARK_MASTER']=original_master;os.environ['SPARK_MAX_CORES']='2';settings.cache_clear()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sizes',type=int,nargs='+',default=[100,10000,100000]);parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args();run(args.sizes,args.repeats)
