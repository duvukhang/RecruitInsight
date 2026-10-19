"""Host HTTP integration: real containers, no mocked API or generated results."""
import argparse
import json
import sys
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from generate_demo import generate


def run(base,rows):
    root=Path(__file__).resolve().parents[1]
    env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    token=''
    def request(path,data=None,method=None,headers=None):
        payload=json.dumps(data).encode() if data is not None else None
        req=urllib.request.Request(base+'/api/v1'+path,data=payload,method=method,
            headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {}),**(headers or {})})
        try:
            with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'HTTP {error.code} on {path}: '+error.read().decode()) from None
    result=request('/auth/login',{'username':env['ADMIN_USERNAME'],'password':env['ADMIN_PASSWORD']})
    token=result['data']['access_token']
    file=generate(root/'data'/'DEMO-e2e.csv',rows)
    boundary='----recruitment-'+uuid.uuid4().hex
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="source"\r\n\r\nDEMO\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="is_demo"\r\n\r\ntrue\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="DEMO-e2e.csv"\r\nContent-Type: text/csv\r\n\r\n').encode()+file.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request(base+'/api/v1/datasets/upload',data=body,headers={
        'Authorization':'Bearer '+token,'Content-Type':'multipart/form-data; boundary='+boundary,'Idempotency-Key':str(uuid.uuid4())})
    with urllib.request.urlopen(req,timeout=60) as response:uploaded=json.load(response)['data']
    def wait(identifier):
        previous=''
        for _ in range(300):
            job=request('/etl/jobs/'+identifier)['data']
            if job['status']!=previous:print(identifier,job['status'],flush=True);previous=job['status']
            if job['status']=='COMPLETED':return job
            if job['status'] in ['FAILED','CANCELLED']:raise RuntimeError(json.dumps(job.get('error')))
            time.sleep(2)
        raise TimeoutError('Job did not finish within 10 minutes')
    wait(uploaded['job_id']);version=uploaded['dataset_version']
    etl=request('/etl/jobs',{'dataset_version':version})['data']
    etl_job=wait(etl['job_id'])
    overview=request('/analytics/overview?dataset_version='+version)
    assert overview['data']['total_jobs']>0
    assert overview['meta']['is_demo'] is True
    training=request('/models/train',{'dataset_version':version})['data']
    training_job=wait(training['job_id'])
    models=[m for m in request('/models?page_size=100')['data'] if m['training_job_id']==training['job_id']]
    assert len(models)>=4
    winner=next(m for m in models if m['selected_by_validation'] and m['algorithm']!='baseline')
    request('/models/'+winner['_id']+'/activate',{},method='POST')
    predicted=request('/predictions/salary',{'job_title':'Data Engineer','industry':'Information Technology',
        'province':'Hồ Chí Minh','experience_years':5,'required_skills':['python','spark','sql']})['data']
    assert predicted['predicted_salary_vnd']>0
    assert predicted['model_version']==winner['_id']
    history=request('/predictions/history')['data']
    assert any(item['_id']==predicted['_id'] for item in history)
    report={'result':'PASS','dataset_version':version,'input_rows':rows,'overview':overview,
        'etl_metrics':etl_job['metrics'],'training_metrics':training_job['metrics'],
        'models':[{k:m[k] for k in ['_id','algorithm','validation_metrics','test_metrics']} for m in models],
        'prediction':predicted}
    (root/'artifacts').mkdir(exist_ok=True)
    (root/'artifacts'/'e2e-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'result':'PASS','rows':rows,'clean':overview['data']['total_jobs'],'models':len(models),
                      'prediction_vnd':predicted['predicted_salary_vnd']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://localhost:8080');parser.add_argument('--rows',type=int,default=1000)
    args=parser.parse_args();run(args.base,args.rows)
