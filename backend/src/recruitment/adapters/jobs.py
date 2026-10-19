from datetime import timedelta
from pymongo import ReturnDocument
from recruitment.domain.common import now, uid


class MongoJobs:
    def __init__(self, db):
        self.db = db

    def enqueue(self, kind, payload, actor):
        job = {'_id': uid(), 'job_type': kind, 'payload': payload,
               'created_by': actor, 'status': 'QUEUED', 'created_at': now(),
               'fencing_token': 0, 'retry_count': 0, 'progress': 0,
               'cancel_requested': False}
        self.db.etl_jobs.insert_one(job)
        return job

    def claim(self, kinds, worker):
        return self.db.etl_jobs.find_one_and_update(
            {'job_type': {'$in': kinds}, 'status': 'QUEUED'},
            {'$set': {'status': 'RUNNING', 'worker_id': worker, 'started_at': now(),
                      'lease_until': now() + timedelta(seconds=60), 'attempt_id': uid()},
             '$inc': {'fencing_token': 1}},
            sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)

    def heartbeat(self, job, worker):
        result = self.db.etl_jobs.update_one(
            {'_id': job['_id'], 'worker_id': worker, 'fencing_token': job['fencing_token'],
             'status': {'$in': ['RUNNING', 'CANCEL_REQUESTED']}, 'lease_until': {'$gt': now()}},
            {'$set': {'heartbeat_at': now(), 'lease_until': now() + timedelta(seconds=60)}})
        return result.modified_count == 1

    def recover(self):
        for job in self.db.etl_jobs.find({'status':'COMMITTING','lease_until':{'$lt':now()}}).limit(100):
            version=job.get('payload',{}).get('dataset_version')
            dataset=self.db.datasets.find_one({'_id':version}) if version else None
            completed=bool(dataset and dataset.get('published_attempt_id')==job.get('attempt_id') and dataset['status']=='PUBLISHED')
            if not completed and dataset:
                self.db.datasets.update_one({'_id':version,'active_attempt':job.get('attempt_id'),'status':{'$ne':'PUBLISHED'}},
                    {'$set':{'status':'FAILED'},'$unset':{'active_attempt':''}})
            self.db.etl_jobs.update_one({'_id':job['_id'],'status':'COMMITTING','fencing_token':job['fencing_token']},
                {'$set':{'status':'COMPLETED' if completed else 'FAILED','finished_at':now(),'recovered_commit':True}})
        # Old attempts are never published; a new claim receives a new fencing token.
        self.db.etl_jobs.update_many(
            {'status': 'RUNNING', 'lease_until': {'$lt': now()}, 'retry_count': {'$lt': 3}},
            {'$set': {'status': 'QUEUED', 'error': {'code': 'LEASE_EXPIRED'}}, '$inc': {'retry_count': 1}})
        self.db.etl_jobs.update_many(
            {'status': 'RUNNING', 'lease_until': {'$lt': now()}, 'retry_count': {'$gte': 3}},
            {'$set': {'status': 'FAILED', 'error': {'code': 'RETRY_EXHAUSTED'}, 'finished_at': now()}})
