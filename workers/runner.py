import signal
import socket
import time
import json
import threading
from pymongo.errors import AutoReconnect
from recruitment.adapters.mongo import database
from recruitment.adapters.jobs import MongoJobs
from recruitment.domain.common import now, AppError
from recruitment.infrastructure.config import settings


def execute(db, job, worker_id):
    repository = MongoJobs(db)
    stopped = threading.Event()
    lost = threading.Event()
    def heartbeat():
        while not stopped.wait(10):
            try:
                db.worker_heartbeats.update_one({'_id': worker_id}, {'$set': {'kind': settings().worker_kind, 'updated_at': now()}}, upsert=True)
                if not repository.heartbeat(job, worker_id):
                    lost.set()
                    from pyspark import SparkContext
                    if SparkContext._active_spark_context:SparkContext._active_spark_context.cancelJobGroup(job['_id'])
                    return
                current=db.etl_jobs.find_one({'_id':job['_id']},{'cancel_requested':1})
                if current and current.get('cancel_requested'):
                    from pyspark import SparkContext
                    if SparkContext._active_spark_context:SparkContext._active_spark_context.cancelJobGroup(job['_id'])
            except Exception:
                lost.set();return
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    owned = {'_id': job['_id'], 'fencing_token': job['fencing_token'], 'worker_id': worker_id}
    def guard():
        current = db.etl_jobs.find_one(owned)
        if lost.is_set() or not current or current['lease_until'] < now():
            raise AppError('LEASE_LOST', 'Worker đã mất quyền sở hữu job.')
        if current.get('cancel_requested'):
            raise AppError('CANCELLED', 'Tác vụ đã được hủy.')
    try:
        guard()
        if job['job_type'] == 'INGESTION':
            from bigdata.ingestion import ingest
            metrics = ingest(db, job, guard)
        elif job['job_type'] == 'ETL':
            from bigdata.etl import etl
            metrics = etl(db,job,guard)
        elif job['job_type'] == 'TRAINING':
            from machine_learning.training import train
            metrics = train(db,job,guard)
        else:
            raise AppError('UNSUPPORTED_JOB', 'Loại tác vụ chưa được triển khai.')
        guard()
        db.etl_jobs.update_one({**owned, 'status': {'$in':['RUNNING','COMMITTING']}}, {'$set': {
            'status': 'COMPLETED', 'progress': 100, 'metrics': metrics, 'finished_at': now()}})
    except Exception as error:
        code = error.code if isinstance(error, AppError) else 'EXECUTION_FAILED'
        message = error.message if isinstance(error, AppError) else 'Tác vụ thất bại. Xem logs worker và kiểm tra định dạng đầu vào.'
        current=db.etl_jobs.find_one(owned)
        if current and current.get('cancel_requested') and code!='LEASE_LOST':
            code='CANCELLED';message='Đã dừng tác vụ theo yêu cầu.'
        if code != 'LEASE_LOST':
            db.etl_jobs.update_one({**owned, 'status': {'$in': ['RUNNING', 'CANCEL_REQUESTED','COMMITTING']}}, {'$set': {
                'status': 'CANCELLED' if code == 'CANCELLED' else 'FAILED',
                'error': {'code': code, 'message': message}, 'finished_at': now()}})
            if job['job_type']=='INGESTION':
                version=job['payload']['dataset_version']
                db.ingestion_runs.update_one({'_id':version},{'$set':{'status':'FAILED','error':{'code':code,'message':message},'finished_at':now()}})
                db.datasets.update_one({'_id':version,'status':'IMPORTING'},{'$set':{'status':'FAILED'}})
        print(json.dumps({'job_id': job['_id'], 'error_code': code, 'exception_type': type(error).__name__}), flush=True)
    finally:
        stopped.set();thread.join(timeout=2)


def main():
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    worker_id = socket.gethostname()
    db = database()
    repository = MongoJobs(db)
    while running:
        db.worker_heartbeats.update_one({"_id": worker_id}, {"$set": {
            "kind": settings().worker_kind, "updated_at": now()}}, upsert=True)
        repository.recover()
        job = repository.claim(['INGESTION','ETL'] if settings().worker_kind == 'ETL' else ['TRAINING'], worker_id)
        if job:
            execute(db, job, worker_id)
            continue
        time.sleep(2)


if __name__ == '__main__':
    main()
