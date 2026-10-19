"""Verify reports, model state and persistence through a restart of this project's containers."""
import csv,io,json,subprocess,time,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
token=''
def call(path,data=None,method=None,binary=False):
    request=urllib.request.Request('http://localhost:8080/api/v1'+path,
        data=json.dumps(data).encode() if data is not None else None,method=method,
        headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    with urllib.request.urlopen(request,timeout=60) as response:return response.read() if binary else json.load(response)
def login():return call('/auth/login',{'username':env['ADMIN_USERNAME'],'password':env['ADMIN_PASSWORD']})['data']['access_token']
token=login();e2e=json.loads((root/'artifacts'/'e2e-result.json').read_text(encoding='utf-8'))
winner=next(m for m in e2e['models'] if m['algorithm']==e2e['training_metrics']['selected_algorithm'])
call('/models/'+winner['_id']+'/activate',{})
model=call('/models/'+winner['_id'])['data'];assert model['status']=='ACTIVE'
dataset=call('/analytics/overview')['meta']['dataset_version']
quality=call('/datasets/'+dataset+'/quality')['data'];exports={}
for kind,count_key in [('invalid','invalid'),('duplicates','duplicate'),('clean','clean')]:
    content=call('/datasets/'+dataset+'/export/'+kind,binary=True).decode('utf-8-sig')
    count=len(list(csv.reader(io.StringIO(content))))-1;assert count==quality['counts'][count_key]
    exports[kind]=count
configuration=call('/system/settings')['data'];call('/system/settings',configuration,method='PATCH')
features={'job_title':'Data Engineer','industry':'Information Technology','province':'Hồ Chí Minh','experience_years':5,'required_skills':['python','spark','sql']}
before=call('/predictions/salary',features)['data'];assert before['reference_period']['from'] and before['prediction_timestamp']
assert call('/benchmarks')['data']
subprocess.run(['docker','compose','-f','docker-compose.yml','-f','docker-compose.mlops.yml','--profile','mlops','restart'],check=True,cwd=root)
for _ in range(80):
    try:
        if call('/health/ready')['status']=='ready':break
    except (urllib.error.URLError,TimeoutError):pass
    time.sleep(2)
else:raise TimeoutError('Stack did not recover after restart')
token=login();after=call('/predictions/salary',features)['data']
assert before['model_version']==after['model_version'] and before['predicted_salary_vnd']==after['predicted_salary_vnd']
assert call('/analytics/overview')['meta']['dataset_version']==dataset
assert call('/analytics/overview')['data']['total_jobs']==quality['counts']['clean']
assert call('/predictions/'+before['_id'])['data']['_id']==before['_id']
result={'result':'PASS','exports':exports,'dataset_version':dataset,'model_version':model['_id'],
    'prediction_parity_after_restart':True,'history_persisted':True,'reference_period':after['reference_period']}
(root/'artifacts'/'persistence-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
