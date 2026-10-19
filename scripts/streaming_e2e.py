"""Send valid/duplicate/poison Kafka events; verify the real streamed dataset."""
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
def call(path,data=None):
    request=urllib.request.Request('http://localhost:8080/api/v1'+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if globals().get('token') else {})})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
token=call('/auth/login',{'username':env['ADMIN_USERNAME'],'password':env['ADMIN_PASSWORD']})['data']['access_token']
before=call('/analytics/overview')['meta']['dataset_version']
run=uuid4().hex
events=[]
for i in range(20):
    events.append({'event_id':f'DEMO-{run}-{i}','is_demo':True,'payload':{'source_job_id':f'{run}-{i}',
        'job_title':'Data Engineer','company_name':'DEMO Streaming Company','province':'Hồ Chí Minh','industry':'IT',
        'salary':'20–30 triệu VND/tháng','experience_years':3,'posted_at':'2026-10-18'}})
events.append(events[0]);events.append({'event_id':'poison-'+run,'payload':{}})
command=['docker','compose','-f','docker-compose.yml','-f','docker-compose.streaming.yml','--profile','streaming','exec','-T',
         'kafka','/opt/kafka/bin/kafka-console-producer.sh','--bootstrap-server','kafka:9092','--topic','recruitment.jobs.raw']
subprocess.run(command,input=('\n'.join(json.dumps(e,ensure_ascii=False) for e in events)+'\n').encode(),check=True,cwd=root)
try:
    for _ in range(180):
        versions=call('/datasets?page_size=100')['data']
        candidates=[d for d in versions if d.get('source')=='KAFKA' and d['status']=='PUBLISHED' and d['row_counts'].get('raw')==22]
        if candidates:
            version=candidates[0]['_id'];report=call('/datasets/'+version+'/quality')['data']
            assert report['counts']=={'raw':22,'clean':20,'duplicate':1,'invalid':1},report
            found=call('/jobs?dataset_version='+version)['data']
            if not any(run in item['source_job_key'] for item in found):
                time.sleep(2);continue
            evidence={'result':'PASS','version':version,'counts':report['counts'],'previous_active':before,'events':events}
            (root/'artifacts'/'streaming-result.json').write_text(json.dumps(evidence,indent=2))
            print(json.dumps({k:v for k,v in evidence.items() if k!='events'}),flush=True);break
        time.sleep(2)
    else:raise TimeoutError('Streaming version was not published within 6 minutes')
finally:
    call('/datasets/'+before+'/activate',{})
