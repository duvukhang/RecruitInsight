import argparse,getpass,json
from argon2 import PasswordHasher
from recruitment.adapters.mongo import database
from recruitment.application.pipeline import PipelineService
from recruitment.adapters.jobs import MongoJobs
from recruitment.domain.common import uid,now
from recruitment.infrastructure.config import settings


def main():
    parser=argparse.ArgumentParser(prog='recruitment');groups=parser.add_subparsers(dest='group',required=True)
    for name,operation in [('etl','submit'),('models','train')]:
        sub=groups.add_parser(name).add_subparsers(dest='operation',required=True)
        sub.add_parser(operation).add_argument('--dataset-version',required=True)
    user=groups.add_parser('users').add_subparsers(dest='operation',required=True).add_parser('create')
    user.add_argument('--username',required=True);user.add_argument('--role',choices=['ADMIN','ANALYST','VIEWER'],required=True)
    args=parser.parse_args();db=database()
    if args.group=='users':
        password=getpass.getpass('New password (not logged): ')
        if len(password)<12:raise ValueError('Password must have at least 12 characters')
        db.users.insert_one({'_id':uid(),'username':args.username,'role':args.role,'enabled':True,
            'password_hash':PasswordHasher().hash(password),'created_at':now()})
        print(json.dumps({'created_user':args.username,'role':args.role}));return
    admin=db.users.find_one({'username':settings().admin_username,'role':'ADMIN'})
    if not admin:raise RuntimeError('Bootstrap administrator not found')
    service=PipelineService(db,MongoJobs(db))
    job=service.submit_etl(args.dataset_version,admin['_id']) if args.group=='etl' else service.submit_training(args.dataset_version,admin['_id'])
    print(json.dumps({'job_id':job['_id'],'status':job['status']}))


if __name__=='__main__':main()
