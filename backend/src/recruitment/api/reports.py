import csv,io,json
from pathlib import Path
from fastapi import APIRouter,Depends
from fastapi.responses import StreamingResponse,FileResponse
from recruitment.api.auth import admin,current_user,analyst
from recruitment.api.data import require
from recruitment.adapters.mongo import database
from recruitment.infrastructure.config import settings
from recruitment.domain.common import AppError

router=APIRouter(prefix='/api/v1',tags=['Reports'])


@router.get('/datasets/{version}/export/{kind}')
def export(version:str,kind:str,user=Depends(admin)):
    dataset=require('datasets',version)
    definitions={'invalid':('invalid_jobs',['raw_record_ref','error_code','error_message','validation_stage']),
        'duplicates':('duplicate_jobs',['raw_record_ref','canonical_raw_ref','match_strategy','reason']),
        'clean':('cleaned_jobs',['job_title','company_name','province','industry','salary_original_text','salary_mid_vnd','salary_quality_status'])}
    if kind not in definitions:raise AppError('NOT_FOUND','Không có loại export này.',404)
    collection,columns=definitions[kind]
    columns=['dataset_version','is_demo',*columns]
    report=database().data_quality_reports.find_one({'dataset_version':version},sort=[('generated_at',-1)])
    attempt=dataset.get('published_attempt_id') or (report['attempt_id'] if report else None)
    if not attempt:raise AppError('INVALID_STATE','Chưa có kết quả ETL.',409)
    def rows():
        buffer=io.StringIO();writer=csv.writer(buffer);yield '\ufeff'
        writer.writerow(columns);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
        cursor=database()[collection].find({'dataset_version':version,'attempt_id':attempt}).batch_size(500)
        try:
            for record in cursor:
                values=[]
                for column in columns:
                    raw_value=dataset['is_demo'] if column=='is_demo' else record.get(column)
                    value=str(raw_value if raw_value is not None else '')
                    dangerous = value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n'))
                    values.append("'"+value if dangerous else value)
                writer.writerow(values);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
        finally:cursor.close()
    label='DEMO-' if dataset['is_demo'] else ''
    return StreamingResponse(rows(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{label}{kind}-{version[:8]}.csv"'})


@router.get('/models/{identifier}/diagnostics')
def diagnostics(identifier:str,user=Depends(analyst)):
    model=require('model_registry',identifier)
    directory=Path(model['artifact_uri']).parent.resolve()
    if not directory.is_relative_to((settings().data_root/'artifacts').resolve()):raise AppError('ARTIFACT_INVALID','Artifact path không hợp lệ.',503)
    def read(name):
        target=directory/name
        return json.loads(target.read_text(encoding='utf-8')) if target.is_file() else []
    names={'actual':'actual-vs-predicted.png','residuals':'residuals.png','importance':'importance.png','holdout':'holdout.json','split':'split.json'}
    experiment=database().ml_experiments.find_one({'_id':identifier}) or {}
    return {'data':{'holdout':read('holdout.json')[:1000],'importance':read('importance.json'),
                    'slice_metrics':[r for r in experiment.get('slice_metrics',[]) if r.get('n',0)>=30],
                    'slice_policy':experiment.get('slice_policy',{'minimum_samples':30}),
                    'available_artifacts':[key for key,name in names.items() if (directory/name).is_file()]}}


@router.get('/models/{identifier}/artifacts/{kind}')
def artifact(identifier:str,kind:str,user=Depends(analyst)):
    model=require('model_registry',identifier)
    names={'actual':'actual-vs-predicted.png','residuals':'residuals.png','importance':'importance.png','holdout':'holdout.json','split':'split.json'}
    if kind not in names:raise AppError('NOT_FOUND','Không có artifact này.',404)
    path=(Path(model['artifact_uri']).parent/names[kind]).resolve()
    if not path.is_relative_to((settings().data_root/'artifacts').resolve()) or not path.is_file():
        raise AppError('NOT_FOUND','Model này chưa có artifact được yêu cầu.',404)
    return FileResponse(path,filename=('DEMO-' if model['is_demo'] else '')+names[kind])


@router.get('/benchmarks')
def benchmarks(user=Depends(admin)):
    return {'data':list(database().benchmark_runs.find({}, {'observations':0}).sort('created_at',-1).limit(20))}
