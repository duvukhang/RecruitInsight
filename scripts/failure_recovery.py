"""Kill the ETL driver during a real job; wait for lease recovery and reconcile published counts."""
import json,subprocess,time,urllib.request,uuid
from pathlib import Path
from generate_demo import generate
root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
token=''
def call(path,data=None):
    request=urllib.request.Request('http://localhost:8080/api/v1'+path,data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
token=call('/auth/login',{'username':env['ADMIN_USERNAME'],'password':env['ADMIN_PASSWORD']})['data']['access_token']
before=call('/analytics/overview')['meta']['dataset_version']
path=generate(root/'data'/'DEMO-recovery.csv',10000)
boundary=uuid.uuid4().hex
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="source"\r\n\r\nDEMO_RECOVERY\r\n'
      f'--{boundary}\r\nContent-Disposition: form-data; name="is_demo"\r\n\r\ntrue\r\n'
      f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="DEMO-recovery.csv"\r\n\r\n').encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
request=urllib.request.Request('http://localhost:8080/api/v1/datasets/upload',data=body,headers={
    'Authorization':'Bearer '+token,'Content-Type':'multipart/form-data; boundary='+boundary,'Idempotency-Key':uuid.uuid4().hex})
with urllib.request.urlopen(request,timeout=60) as response:upload=json.load(response)['data']
def wait(job_id,states,timeout=300):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=call('/etl/jobs/'+job_id)['data']
        if job['status'] in states:return job
        if job['status'] in ['FAILED','CANCELLED']:raise RuntimeError(str(job.get('error')))
        time.sleep(2)
    raise TimeoutError(job_id)
try:
    wait(upload['job_id'],['COMPLETED'])
    job_id=call('/etl/jobs',{'dataset_version':upload['dataset_version']})['data']['job_id']
    running=wait(job_id,['RUNNING']);first_attempt=running['attempt_id']
    # Allow the driver to register its application before failure injection.
    time.sleep(3)
    subprocess.run(['docker','compose','kill','-s','SIGKILL','etl-worker'],check=True,cwd=root)
    subprocess.run(['docker','compose','up','-d','etl-worker'],check=True,cwd=root)
    finished=wait(job_id,['COMPLETED'],420)
    assert finished['attempt_id']!=first_attempt
    assert finished['retry_count']>=1
    counts=finished['metrics']['counts'];assert sum(counts[k] for k in ['clean','invalid','duplicate'])==counts['raw']==10000
    overview=call('/analytics/overview?dataset_version='+upload['dataset_version'])
    assert overview['data']['total_jobs']==counts['clean']
    result={'result':'PASS','job_id':job_id,'first_attempt':first_attempt,'published_attempt':finished['attempt_id'],
        'retry_count':finished['retry_count'],'counts':counts,'published_rows_match':True}
    (root/'artifacts'/'recovery-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:call('/datasets/'+before+'/activate',{})
