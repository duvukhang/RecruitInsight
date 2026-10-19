import hashlib,json,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
result=json.loads((root/'artifacts'/'e2e-result.json').read_text(encoding='utf-8'))
def call(path,body=None):
    request=urllib.request.Request('http://localhost:5000'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
experiment=call('/api/2.0/mlflow/experiments/get-by-name?experiment_name=Recruitment')['experiment']['experiment_id']
runs=call('/api/2.0/mlflow/runs/search',{'experiment_ids':[experiment],
    'filter':"params.dataset_version = '"+result['dataset_version']+"'",'max_results':100})['runs']
assert len(runs)==6,len(runs)
checked=[]
for run in runs:
    assert run['info']['status']=='FINISHED'
    parameters={p['key']:p['value'] for p in run['data']['params']}
    metrics={m['key']:m['value'] for m in run['data']['metrics']}
    assert 'validation_mae' in metrics and 'test_rmse' in metrics
    path=run['info']['artifact_uri'].replace('mlflow-artifacts:/','').lstrip('/')
    filename='model.json' if parameters['algorithm']=='spark_linear_numeric' else 'model.joblib'
    with urllib.request.urlopen('http://localhost:5000/api/2.0/mlflow-artifacts/artifacts/'+path+'/'+filename,timeout=60) as response:
        digest=hashlib.sha256(response.read()).hexdigest()
    assert digest==parameters['artifact_sha256']
    checked.append({'run_id':run['info']['run_id'],'algorithm':parameters['algorithm'],'artifact_sha256_verified':True})
evidence={'result':'PASS','runs':checked,'count':len(checked)}
(root/'artifacts'/'mlflow-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps({'result':'PASS','verified_runs':len(checked),'artifact_checksums':'MATCH'}))
