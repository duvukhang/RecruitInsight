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
        from recruitment.api.users import CreateUser
        from recruitment.application.users import UsersService
        body=CreateUser(username=args.username,password=password,role=args.role)
        UsersService(db).create(body.username,body.password,body.role,'CLI')
        print(json.dumps({'created_user':args.username,'role':args.role}));return
    admin=db.users.find_one({'username':settings().admin_username,'role':'ADMIN'})
    if not admin:raise RuntimeError('Bootstrap administrator not found')
    service=PipelineService(db,MongoJobs(db))
    job=service.submit_etl(args.dataset_version,admin['_id']) if args.group=='etl' else service.submit_training(args.dataset_version,admin['_id'])
    print(json.dumps({'job_id':job['_id'],'status':job['status']}))


if __name__=='__main__':main()
