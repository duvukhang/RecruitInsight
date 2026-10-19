from recruitment.ports.jobs import JobRepository
from recruitment.application.datasets import published
from recruitment.domain.common import AppError


class PipelineService:
    def __init__(self,db,jobs:JobRepository):self.db=db;self.jobs=jobs
    def submit_etl(self,version,actor):
        dataset=self.db.datasets.find_one({'_id':version})
        if not dataset:raise AppError('NOT_FOUND','Không tìm thấy dataset.',404)
        if dataset['status'] not in ['RAW_READY','FAILED'] or not dataset.get('raw_file_ref'):
            raise AppError('INVALID_STATE','Dataset chưa có Raw hoặc đã được công bố.',409)
        return self.jobs.enqueue('ETL',{'dataset_version':version},actor)
    def submit_training(self,version,actor):
        published(self.db,version)
        return self.jobs.enqueue('TRAINING',{'dataset_version':version},actor)
    def retry(self,identifier):
        result=self.db.etl_jobs.update_one({'_id':identifier,'status':'FAILED','retry_count':{'$lt':3}},
            {'$set':{'status':'QUEUED','cancel_requested':False},'$inc':{'retry_count':1}})
        if not result.modified_count:raise AppError('INVALID_STATE','Job không thể retry.',409)
    def cancel(self,identifier):
        job=self.db.etl_jobs.find_one({'_id':identifier})
        if not job:raise AppError('NOT_FOUND','Không tìm thấy job.',404)
        if job['status'] not in ['QUEUED','RUNNING']:raise AppError('INVALID_STATE','Job không thể hủy ở trạng thái này.',409)
        status='CANCELLED' if job['status']=='QUEUED' else 'CANCEL_REQUESTED'
        if not self.db.etl_jobs.update_one({'_id':identifier,'status':job['status']},{'$set':{'status':status,'cancel_requested':True}}).modified_count:
            raise AppError('REVISION_CONFLICT','Trạng thái job vừa đổi.',409)
        return status
