"""Consistent application backup: run while compute workers are stopped."""
import gzip,hashlib,json,os,tarfile
from pathlib import Path
from bson import BSON,json_util
from recruitment.adapters.mongo import database
from recruitment.domain.common import uid,now
from recruitment.infrastructure.config import settings


def main():
    os.umask(0o077);db=database();identifier=uid();root=settings().data_root/'backups'/identifier;root.mkdir(parents=True)
    if db.etl_jobs.count_documents({'status':{'$in':['RUNNING','COMMITTING','QUEUED','CANCEL_REQUESTED']}}):
        raise RuntimeError('Stop workers and wait/cancel pending jobs before backup')
    manifest={'backup_id':identifier,'database':db.name,'created_at':now().isoformat(),'collections':{},'files':{}}
    for info in db.list_collections():
        name=info['name']
        if name.startswith('system.'):continue
        count=0;target=root/(name+'.bson.gz')
        with gzip.open(target,'wb') as output:
            for record in db[name].find({}).batch_size(500):output.write(BSON.encode(record));count+=1
        manifest['collections'][name]={'count':count,'options':info.get('options',{}),
            'indexes':[index for index in db[name].list_indexes() if index['name']!='_id_']}
    for folder in ['uploads','artifacts','events','checkpoints']:
        source=settings().data_root/folder
        if source.exists():
            with tarfile.open(root/(folder+'.tar.gz'),'w:gz') as archive:archive.add(source,arcname=folder)
    for target in root.iterdir():manifest['files'][target.name]=hashlib.sha256(target.read_bytes()).hexdigest()
    (root/'manifest.json').write_text(json_util.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'backup_id':identifier,'manifest':str(root/'manifest.json'),'collections':len(manifest['collections'])}))


if __name__=='__main__':main()
