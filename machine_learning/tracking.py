"""MLflow REST adapter; business metadata remains in MongoDB."""
import json
import os
import time
import urllib.request
import urllib.error
from urllib.parse import quote
from pathlib import Path


def log_model(model,manifest=None):
    base=os.environ.get('MLFLOW_TRACKING_URI','').rstrip('/')
    if not base:return None
    def call(path,data=None,method=None,raw=None):
        body=raw if raw is not None else json.dumps(data).encode() if data is not None else None
        request=urllib.request.Request(base+'/api/2.0/'+path,data=body,method=method,
            headers={'Content-Type':'application/octet-stream' if raw is not None else 'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            content=response.read();return json.loads(content) if content else {}
    try:
        experiment=call('mlflow/experiments/get-by-name?experiment_name=Recruitment')['experiment']['experiment_id']
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        experiment=call('mlflow/experiments/create',{'name':'Recruitment'})['experiment_id']
    run=call('mlflow/runs/create',{'experiment_id':experiment,'start_time':int(time.time()*1000),
        'tags':[{'key':'mlflow.runName','value':model['algorithm']+'-'+model['_id'][:8]}]})['run']['info']
    run_id=run['run_id']
    call('mlflow/runs/log-batch',{'run_id':run_id,
        'params':[{'key':'dataset_version','value':model['dataset_version']},{'key':'algorithm','value':model['algorithm']},
                  {'key':'feature_schema_version','value':model['feature_schema_version']},{'key':'artifact_sha256','value':model['artifact_sha256']}],
        'metrics':[{'key':prefix+'_'+name,'value':value,'timestamp':int(time.time()*1000),'step':0}
                   for prefix in ['validation','test'] for name,value in model[prefix+'_metrics'].items() if value is not None],
        'tags':[{'key':'is_demo','value':str(model['is_demo'])}]})
    artifact_path=run['artifact_uri'].replace('mlflow-artifacts:/','').lstrip('/')
    target=Path(model['artifact_uri'])
    for file in sorted(p for p in target.parent.iterdir() if p.is_file()):
        call('mlflow-artifacts/artifacts/'+quote(artifact_path+'/'+file.name,safe='/'),method='PUT',raw=file.read_bytes())
    call('mlflow/runs/update',{'run_id':run_id,'status':'FINISHED','end_time':int(time.time()*1000)})
    return run_id
