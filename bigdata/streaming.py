"""Bounded Kafka microbatch ingestion, checkpointed by Spark; ETL uses the normal job pipeline."""
import hashlib
import json
import signal
import threading
from pathlib import Path
from pymongo import ReturnDocument
from bigdata.spark_session import spark_session
from recruitment.adapters.mongo import database
from recruitment.domain.common import now
from recruitment.infrastructure.config import settings


def consume(batch,batch_id):
    if batch.isEmpty():return
    # maxOffsetsPerTrigger=100 bounds driver materialization; unbounded datasets never collect here.
    records=sorted(batch.selectExpr('CAST(value AS STRING) AS event','partition','offset').toLocalIterator(),key=lambda r:(r['partition'],r['offset']))
    identity=','.join(sorted(f"{r['partition']}:{r['offset']}" for r in records))
    version='stream-'+hashlib.sha256(identity.encode()).hexdigest()[:24]
    db=database()
    existing=db.datasets.find_one({'_id':version})
    if existing and existing['status'] in ['RAW_READY','PROCESSING','PUBLISHED','FAILED']:return
    path=settings().data_root/'uploads'/(version+'.raw.jsonl')
    with path.open('w',encoding='utf-8') as output:
        for index,row in enumerate(records,1):
            try:
                event=json.loads(row['event']);raw=event['payload'];event_id=str(event['event_id'])
                if not isinstance(raw,dict) or not event_id or len(event_id)>200:raise ValueError()
            except (ValueError,KeyError,TypeError):
                raw={'_parse_error':'INVALID_KAFKA_EVENT','original_line':row['event']}
                event_id=f"invalid:{row['partition']}:{row['offset']}"
            ref=f'{version}:{index}'
            seen=db.stream_seen.find_one_and_update({'_id':event_id},{'$setOnInsert':{'first_raw_ref':ref,'created_at':now()}},upsert=True,return_document=ReturnDocument.AFTER)
            if seen['first_raw_ref']!=ref:raw['_global_duplicate_ref']=seen['first_raw_ref']
            db.raw_jobs.update_one({'_id':ref},{'$setOnInsert':{'dataset_version':version,'record_number':index,
                'raw_payload':raw,'source':'KAFKA','event_id':event_id,'ingested_at':now()}},upsert=True)
            output.write(json.dumps({'record_number':index,'raw_record_ref':ref,'payload_json':json.dumps(raw,ensure_ascii=False)},ensure_ascii=False)+'\n')
    db.datasets.update_one({'_id':version},{'$setOnInsert':{'dataset_id':'kafka-microbatches','created_by':'streaming-worker',
        'idempotency_key':version,'status':'RAW_READY','source':'KAFKA','is_demo':True,'created_at':now(),
        'row_counts':{'raw':len(records)},'raw_file_ref':str(path),'kafka_batch_id':batch_id,'kafka_offsets':identity}},upsert=True)
    db.etl_jobs.update_one({'_id':'etl-'+version},{'$setOnInsert':{'job_type':'ETL','payload':{'dataset_version':version},
        'created_by':'streaming-worker','created_at':now(),'status':'QUEUED','fencing_token':0,'retry_count':0,
        'cancel_requested':False,'progress':0}},upsert=True)


def main():
    spark=spark_session('recruitment-kafka-streaming')
    stopped=threading.Event()
    def heartbeat():
        while not stopped.is_set():
            database().worker_heartbeats.update_one({'_id':'streaming-worker'},{'$set':{'kind':'STREAMING','updated_at':now()}},upsert=True)
            stopped.wait(10)
    threading.Thread(target=heartbeat,daemon=True).start()
    stream=(spark.readStream.format('kafka').option('kafka.bootstrap.servers','kafka:9092')
            .option('subscribe','recruitment.jobs.raw').option('startingOffsets','earliest')
            .option('maxOffsetsPerTrigger',100).option('failOnDataLoss','true').load())
    query=(stream.writeStream.foreachBatch(consume).option('checkpointLocation','/data/checkpoints/kafka-raw-v1')
           .trigger(processingTime='10 seconds').start())
    def shutdown(*_):stopped.set();query.stop()
    signal.signal(signal.SIGTERM,shutdown)
    try:query.awaitTermination()
    finally:stopped.set();spark.stop()


if __name__=='__main__':main()
