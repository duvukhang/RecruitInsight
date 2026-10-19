"""Reproducible synthetic fixtures; never represents the real labour market."""
import argparse
import csv
import random
from datetime import date,timedelta
from pathlib import Path


def generate(path,rows=10000,seed=42):
    rng=random.Random(seed);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=['source_job_id','job_title','company_name','province','industry','experience_years',
            'salary','salary_currency','posted_at','skills','remote_type','is_demo']
    previous=None
    with path.open('w',encoding='utf-8-sig',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
        for i in range(rows):
            title=rng.choice(['Data Engineer','Backend Developer','Data Analyst','ML Engineer','Business Analyst'])
            experience=rng.randint(0,12)
            monthly=max(5000000,round((9000000+experience*2400000+(['Data Engineer','Backend Developer','Data Analyst','ML Engineer','Business Analyst'].index(title))*900000+rng.gauss(0,1800000))/100000)*100000)
            record={'source_job_id':f'DEMO-{seed}-{i}','job_title':title,'company_name':f'DEMO Company {rng.randrange(40):02}',
                'province':rng.choice(['Hồ Chí Minh','Hà Nội','Đà Nẵng']),'industry':'Information Technology',
                'experience_years':experience,'salary':f'{monthly} VND/tháng','salary_currency':'VND',
                'posted_at':(date(2026,1,1)+timedelta(days=rng.randrange(270))).isoformat(),
                'skills':rng.choice(['python,spark,sql','java,docker,sql','python,excel,sql']),
                'remote_type':rng.choice(['ONSITE','REMOTE','HYBRID']),'is_demo':True}
            if i%37==0:record['job_title']=''
            if i%11==0:record['salary']='Negotiable'
            if i%53==0 and previous:record=dict(previous)
            writer.writerow(record);previous=record
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,default=10000);parser.add_argument('--seed',type=int,default=42);parser.add_argument('--output',default='data/DEMO-jobs.csv')
    args=parser.parse_args();print(generate(args.output,args.rows,args.seed))
