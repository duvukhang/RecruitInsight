"""Restore to a new *_restore database and isolated files; never drop an existing database."""
import argparse,gzip,hashlib,json,os,re,shutil,tarfile
from pathlib import Path
from bson import decode_file_iter,json_util
from pymongo import MongoClient
from recruitment.infrastructure.config import settings


def main(manifest_path,target_database):
    if not re.fullmatch(r'recruitment_[a-zA-Z0-9_]*restore',target_database):raise ValueError('Target must be an isolated recruitment_*restore database')
    s=settings();path=Path(manifest_path).resolve();backup_root=(s.data_root/'backups').resolve()
    if not path.is_relative_to(backup_root):raise ValueError('Manifest must be within /data/backups')
    manifest=json_util.loads(path.read_text(encoding='utf-8'));identifier=manifest['backup_id']
    if not re.fullmatch('[a-f0-9-]{36}',identifier):raise ValueError('Invalid backup identifier')
    restore_root=backup_root/('restored-'+identifier+'-'+target_database)
    if restore_root.exists():raise ValueError('Restore files already exist; use a new backup/run')
    root=MongoClient(s.mongo_host,username=os.environ['MONGO_ROOT_USER'],password=os.environ['MONGO_ROOT_PASSWORD'],authSource='admin')
    if target_database in root.list_database_names():raise ValueError('Target database already exists; refusing overwrite')
    for name,expected in manifest['files'].items():
        target=(path.parent/name).resolve()
        if not target.is_relative_to(path.parent) or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('Backup checksum mismatch')
    restore_root.mkdir(mode=0o700)
    for folder in ['uploads','artifacts','events','checkpoints']:
        source=path.parent/(folder+'.tar.gz')
        if not source.exists():continue
        with tarfile.open(source) as archive:
            for member in archive.getmembers():
                target=(restore_root/member.name).resolve()
                if not target.is_relative_to(restore_root) or member.issym() or member.islnk() or member.isdev():raise ValueError('Unsafe archive member')
                if member.isdir():target.mkdir(parents=True,exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with archive.extractfile(member) as original,target.open('wb') as output:shutil.copyfileobj(original,output)
    def rewrite(value):
        result=dict(value)
        for field in ['file_ref','raw_file_ref','artifact_uri','artifact_directory','split_manifest_ref']:
            item=result.get(field)
            if not isinstance(item,str):continue
            for folder in ['uploads','artifacts','events','checkpoints']:
                prefix=str(s.data_root/folder)+'/'
                if item.startswith(prefix):result[field]=str(restore_root/folder)+'/'+item[len(prefix):]
        return result
    db=root[target_database]
    for name,definition in manifest['collections'].items():
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name):raise ValueError('Invalid collection name')
        db.create_collection(name,**definition['options']);batch=[]
        with gzip.open(path.parent/(name+'.bson.gz'),'rb') as source:
            for record in decode_file_iter(source):
                batch.append(rewrite(record))
                if len(batch)>=500:db[name].insert_many(batch);batch=[]
        if batch:db[name].insert_many(batch)
        for index in definition['indexes']:
            options={k:v for k,v in index.items() if k not in ['v','key','ns']}
            db[name].create_index(list(index['key'].items()),**options)
        assert db[name].count_documents({})==definition['count'],name
    prediction=db.salary_predictions.find_one({});parity=None
    if prediction:
        model=db.model_registry.find_one({'_id':prediction['model_version']})
        os.environ['DATA_ROOT']=str(restore_root);settings.cache_clear()
        from machine_learning.serving import load
        from machine_learning.features import features
        restored=load(model['artifact_uri'],model['artifact_sha256'])
        actual=round(float(restored.predict([features(prediction['input_features'])])[0]))
        parity=actual==prediction['predicted_salary_vnd'];assert parity,'Prediction parity failed'
    result={'result':'PASS','database':target_database,'restore_root':str(restore_root),'collections':len(manifest['collections']),'prediction_parity':parity}
    (restore_root/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--database',required=True)
    args=parser.parse_args();main(args.manifest,args.database)
