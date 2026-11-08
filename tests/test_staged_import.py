import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient
from recruitment.adapters.mongo import database
from recruitment.infrastructure.init_db import migrate
from recruitment.infrastructure.security import access_token
from recruitment.domain.common import uid
from recruitment.main import app
from bigdata.ingestion import ingest
import pytest


def test_staged_acl_checksums_seal_and_existing_ingestion():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    users = [{'_id': uid(), 'username': uid(), 'role': role, 'password_hash': 'not-used', 'enabled': True} for role in ['ADMIN', 'VIEWER']]
    db.users.insert_many(users)
    client, version, directory = TestClient(app), None, None
    admin = {'Authorization': 'Bearer ' + access_token(users[0]), 'Idempotency-Key': uid()}
    viewer = {'Authorization': 'Bearer ' + access_token(users[1])}
    data = ('\n'.join(json.dumps({'source_job_id': str(i), 'job_title': 'SYNTHETIC Kỹ sư', 'company_name': 'SYNTHETIC Co', 'posted_year': 2023}) for i in range(100)) + '\n').encode()
    chunk = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'row_count': 100}
    body = {'source': 'TEST-STAGED', 'is_demo': True, 'source_metadata': {'dataset_origin': 'synthetic'}, 'chunks': [chunk, chunk]}
    try:
        assert client.post('/api/v1/datasets/staged', json=body, headers=viewer).status_code == 403
        created = client.post('/api/v1/datasets/staged', json=body, headers=admin)
        assert created.status_code == 201
        version = created.json()['data']['dataset_version']
        assert client.post('/api/v1/datasets/staged', json=body, headers=admin).json()['data']['dataset_version'] == version
        assert client.post('/api/v1/datasets/staged', json={**body, 'source': 'DIFFERENT'}, headers=admin).status_code == 409
        url = '/api/v1/datasets/staged/' + version
        assert client.post(url + '/complete', headers=admin).status_code == 409
        assert client.put(url + '/chunks/0', headers=viewer, files={'file': ('0.jsonl', data)}).status_code == 403
        assert client.put(url + '/chunks/0', headers=admin, files={'file': ('0.jsonl', b'wrong')}).status_code == 422
        for i in range(2):
            assert client.put(url + f'/chunks/{i}', headers=admin, files={'file': ('chunk.jsonl', data)}).status_code == 200
        result = client.post(url + '/complete', headers=admin)
        assert result.status_code == 202
        assert client.post(url + '/complete', headers=admin).json()['data']['job_id'] == result.json()['data']['job_id']
        assert client.put(url + '/chunks/0', headers=admin, files={'file': ('chunk.jsonl', data)}).status_code == 409
        assert db.etl_jobs.count_documents({'payload.dataset_version': version}) == 1
        output = ingest(db, {'payload': {'dataset_version': version}, 'attempt_id': uid()}, lambda: None)
        assert output['raw_records'] == 200
        record = db.datasets.find_one({'_id': version})
        assert record['status'] == 'RAW_READY'
        directory = Path(record['file_ref']).parent
        assert db.raw_jobs.count_documents({'dataset_version': version}) == 200
    finally:
        db.users.delete_many({'_id': {'$in': [u['_id'] for u in users]}})
        if version:
            record = db.datasets.find_one({'_id': version})
            if record and record.get('file_ref'):
                directory = Path(record['file_ref']).parent
            for collection in ['raw_jobs', 'ingestion_runs', 'datasets']:
                db[collection].delete_many({'dataset_version': version} if collection == 'raw_jobs' else {'_id': version})
            db.etl_jobs.delete_many({'payload.dataset_version': version})
        if directory:
            for path in directory.iterdir():
                path.unlink()
            directory.rmdir()


def test_chunk_row_count_mismatch_is_not_accepted(tmp_path):
    from recruitment.application.staged_import import staged_records
    from recruitment.domain.common import AppError
    content = b'{"job_title":"SYNTHETIC"}\n'
    (tmp_path / '0000.jsonl').write_bytes(content)
    dataset = {'file_ref': str(tmp_path / 'staged.jsonl'), 'chunks': [
        {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content), 'row_count': 2}]}
    with pytest.raises(AppError) as failure:
        list(staged_records(dataset))
    assert failure.value.code == 'ROW_COUNT_MISMATCH'
