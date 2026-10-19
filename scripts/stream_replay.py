import json,subprocess,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
evidence=json.loads((root/'artifacts'/'streaming-result.json').read_text())
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
token=''
def call(path,data=None):
    req=urllib.request.Request('http://localhost:8080/api/v1'+path,data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
token=call('/auth/login',{'username':env['ADMIN_USERNAME'],'password':env['ADMIN_PASSWORD']})['data']['access_token']
before={r['_id'] for r in call('/datasets?page_size=100')['data']}
active=call('/analytics/overview')['meta']['dataset_version']
command=['docker','compose','-f','docker-compose.yml','-f','docker-compose.streaming.yml','exec','-T','kafka',
    '/opt/kafka/bin/kafka-console-producer.sh','--bootstrap-server','kafka:9092','--topic','recruitment.jobs.raw']
subprocess.run(command,input=('\n'.join(json.dumps(e) for e in evidence['events'])+'\n').encode(),check=True,cwd=root)
for _ in range(180):
    versions=call('/datasets?page_size=100')['data']
    for version in versions:
        if version['_id'] not in before and version.get('source')=='KAFKA' and version['status']=='FAILED':
            report=call('/datasets/'+version['_id']+'/quality')['data']
            if not report:continue
            assert report['counts']=={'raw':22,'clean':0,'duplicate':21,'invalid':1},report
            assert call('/analytics/overview')['meta']['dataset_version']==active
            result={'result':'PASS','counts':report['counts'],'active_pointer_preserved':True,'version':version['_id']}
            (root/'artifacts'/'stream-replay-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(0)
    time.sleep(2)
raise TimeoutError('Replay did not complete')
