import os
from pymongo import MongoClient
from argon2 import PasswordHasher
from recruitment.adapters.mongo import database
from recruitment.infrastructure.config import settings
from recruitment.domain.common import now, uid

COLLECTIONS = {
    "raw_jobs": ["dataset_version", "record_number", "raw_payload"],
    "cleaned_jobs": ["dataset_version", "attempt_id", "source_job_key", "job_title"],
    "invalid_jobs": ["dataset_version", "attempt_id", "raw_record_ref", "error_code"],
    "duplicate_jobs": ["dataset_version", "attempt_id", "raw_record_ref", "canonical_raw_ref"],
    "datasets": ["dataset_id", "status", "is_demo", "created_at"],
    "ingestion_runs": ["dataset_version", "status"],
    "etl_jobs": ["job_type", "status", "created_at"],
    "data_quality_reports": ["dataset_version", "attempt_id", "counts", "passed"],
    "analytics_snapshots": ["dataset_version", "attempt_id", "data"],
    "salary_predictions": ["user_id", "model_version", "predicted_salary_vnd"],
    "ml_experiments": ["dataset_version", "algorithm", "validation_metrics"],
    "model_registry": ["algorithm", "dataset_version", "status", "artifact_sha256"],
    "users": ["username", "password_hash", "role"],
    "audit_logs": ["action", "created_at"],
    "system_settings": ["value", "revision"],
    "worker_heartbeats": ["kind", "updated_at"],
}


def migrate(db):
    for name, required in COLLECTIONS.items():
        properties={key:{'bsonType':'string'} for key in ['_id','dataset_version','attempt_id','source_job_key','job_title','company_name','source','username','password_hash']}
        properties.update({key:{'bsonType':'date'} for key in ['created_at','updated_at','ingested_at','registered_at','generated_at','detected_at']})
        properties.update({key:{'bsonType':['double','int','long','decimal','null'],'minimum':0} for key in ['salary_min_vnd','salary_max_vnd','salary_mid_vnd','predicted_salary_vnd']})
        properties['required_skills']={'bsonType':'array','items':{'bsonType':'string'}}
        if name=='audit_logs':properties['_id']={'bsonType':['string','objectId']}
        if name=='users':properties['role']={'enum':['ADMIN','ANALYST','VIEWER']}
        if name=='etl_jobs':properties['status']={'enum':['PENDING','QUEUED','RUNNING','COMMITTING','COMPLETED','FAILED','CANCEL_REQUESTED','CANCELLED']}
        if name=='datasets':properties['status']={'enum':['IMPORTING','RAW_READY','PROCESSING','VALIDATED','PUBLISHED','FAILED','DELETING','DELETED']}
        validator = {"$jsonSchema": {"bsonType": "object", "required": required,'properties':properties}}
        if name not in db.list_collection_names():
            db.create_collection(name, validator=validator)
        elif next(db.list_collections(filter={'name': name})).get('options', {}).get('validator') != validator:
            db.command("collMod", name, validator=validator, validationLevel="strict")
    indexes = {
        "raw_jobs": [([("dataset_version", 1), ("record_number", 1)], True)],
        "cleaned_jobs": [([("dataset_version", 1), ("attempt_id", 1), ("source_job_key", 1)], True),
                         ([("dataset_version", 1), ("attempt_id", 1), ("province", 1), ("industry", 1), ("posted_at", 1)], False)],
        "invalid_jobs": [([("attempt_id", 1), ("raw_record_ref", 1)], True)],
        "duplicate_jobs": [([("attempt_id", 1), ("raw_record_ref", 1)], True)],
        "data_quality_reports": [([("dataset_version", 1), ("attempt_id", 1)], True)],
        "analytics_snapshots": [([("dataset_version", 1), ("attempt_id", 1)], True)],
        "etl_jobs": [([("status", 1), ("job_type", 1), ("created_at", 1)], False), ([("status", 1), ("lease_until", 1)], False)],
        "users": [([("username", 1)], True)],
        "audit_logs": [([('created_at', -1), ('_id', -1)], False), ([('actor_id', 1), ('created_at', -1)], False)],
        "salary_predictions": [([("user_id", 1), ("created_at", -1)], False)],
        "model_registry": [([('dataset_version',1),('created_at',-1)],False)],
        "datasets": [([("created_by", 1), ("idempotency_key", 1)], True)],
    }
    for name, definitions in indexes.items():
        for keys, unique in definitions:
            db[name].create_index(keys, unique=unique)
    db.auth_sessions.create_index('expires_at', expireAfterSeconds=0)
    db.auth_sessions.create_index('user_id')
    db.etl_jobs.create_index([('payload.dataset_version', 1), ('job_type', 1), ('created_at', -1), ('_id', 1)])
    for field in ['salary_mid_vnd', 'experience_years', 'posted_year', 'company_name', 'job_title', 'posted_at']:
        db.cleaned_jobs.create_index([('dataset_version', 1), ('attempt_id', 1), (field, 1), ('_id', 1)])
    db.auth_limits.create_index('expires_at', expireAfterSeconds=0)
    db.system_settings.update_one({"_id": "schema"}, {"$set": {"value": 1, "revision": 1}}, upsert=True)


def main():
    s = settings()
    root = MongoClient(s.mongo_host, username=os.environ["MONGO_ROOT_USER"],
                       password=os.environ["MONGO_ROOT_PASSWORD"], authSource="admin")
    target = root[s.mongo_database]
    if not target.command("usersInfo", s.mongo_user)["users"]:
        target.command("createUser", s.mongo_user, pwd=s.mongo_password.get_secret_value(),
                       roles=[{"role": "readWrite", "db": s.mongo_database}])
    # The integration-test user has no privileges on other application databases.
    test_db = root["recruitment_test"]
    if not test_db.command("usersInfo", s.mongo_user)["users"]:
        test_db.command("createUser", s.mongo_user, pwd=s.mongo_password.get_secret_value(),
                        roles=[{"role": "readWrite", "db": "recruitment_test"}])
    db = database()
    migrate(target)
    migrate(test_db)
    db.users.update_one({"username": s.admin_username}, {"$setOnInsert": {
        "_id": uid(), "username": s.admin_username,
        "password_hash": PasswordHasher().hash(s.admin_password.get_secret_value()),
        "role": "ADMIN", "created_at": now(), "enabled": True}}, upsert=True)
    print('MongoDB schema initialized')


if __name__ == "__main__":
    main()
