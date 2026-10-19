from pymongo.errors import DuplicateKeyError
from recruitment.domain.common import AppError,now
from machine_learning.serving import load


class ModelService:
    def __init__(self,db,loader=load):self.db=db;self.loader=loader
    def activate(self,identifier,actor):
        model=self.db.model_registry.find_one({'_id':identifier})
        if not model:raise AppError('NOT_FOUND','Không tìm thấy model.',404)
        self.loader(model['artifact_uri'],model['artifact_sha256'])
        baseline=self.db.model_registry.find_one({'training_job_id':model['training_job_id'],'algorithm':'baseline'})
        if model['algorithm']=='baseline' or not baseline or model['validation_metrics']['mae']>baseline['validation_metrics']['mae']:
            raise AppError('MODEL_GATE_FAILED','Validation MAE phải không kém baseline; baseline chỉ dùng đối chiếu.',409)
        pointer=self.db.system_settings.find_one({'_id':'active_model'})
        if pointer and pointer['value']!=identifier:
            result=self.db.system_settings.update_one({'_id':'active_model','revision':pointer['revision']},
                {'$set':{'value':identifier,'previous_value':pointer['value'],'updated_at':now()},'$inc':{'revision':1}})
            if not result.modified_count:raise AppError('REVISION_CONFLICT','Active model vừa đổi.',409)
        elif not pointer:
            try:self.db.system_settings.insert_one({'_id':'active_model','value':identifier,'revision':1,'updated_at':now()})
            except DuplicateKeyError:raise AppError('REVISION_CONFLICT','Active model vừa đổi.',409)
        self.db.model_registry.update_many({'_id':{'$ne':identifier},'status':'ACTIVE'},{'$set':{'status':'ARCHIVED'}})
        self.db.model_registry.update_one({'_id':identifier},{'$set':{'status':'ACTIVE','activated_at':now()}})
        self.db.audit_logs.insert_one({'action':'MODEL_ACTIVATE','actor_id':actor,'resource_id':identifier,'created_at':now()})
        return identifier
