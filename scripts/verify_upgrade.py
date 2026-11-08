"""Kiểm chứng HTTP thật cho RBAC/staged import; tạo dữ liệu tổng hợp có nhãn và khóa user test sau khi chạy."""
import argparse
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


def run(base='http://localhost:8080'):
    root = Path(__file__).resolve().parents[1]
    env = dict(line.split('=', 1) for line in (root / '.env').read_text(encoding='utf-8').splitlines() if '=' in line and not line.startswith('#'))
    observations, accounts = [], []

    def request(path, data=None, token='', method=None, headers=None, expected=200):
        payload = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(base + '/api/v1' + path, data=payload, method=method,
            headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {}), **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                status, body = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status, body = error.code, json.load(error)
        if status != expected:
            raise AssertionError(f'{method or "GET"} {path}: expected {expected}, got {status}; code={body.get("error", {}).get("code")}')
        observations.append({'method': method or ('POST' if data is not None else 'GET'), 'path': path, 'status': status})
        return body

    def login(username, password):
        return request('/auth/login', {'username': username, 'password': password})['data']['access_token']

    admin = login(env['ADMIN_USERNAME'], env['ADMIN_PASSWORD'])
    original = request('/analytics/overview', token=admin)['meta']['dataset_version']
    result = {'fixture': 'SYNTHETIC; not public corpus or market observations', 'observations': observations}
    try:
        request('/users', expected=401)
        for role in ['VIEWER', 'ANALYST']:
            username, password = 'TEST-E2E-' + uuid4().hex[:12], 'Test-' + secrets.token_urlsafe(24) + '9!'
            user = request('/users', {'username': username, 'password': password, 'role': role}, admin, expected=201)['data']
            accounts.append((user, password))
            token = login(username, password)
            user['token'] = token
            request('/users', token=token, expected=403)
            request('/audit-logs', token=token, expected=403)
            request('/system/settings', token=token, expected=403)
            request('/etl/jobs', {'dataset_version': original}, token, expected=403)
            request('/models', token=token, expected=403 if role == 'VIEWER' else 200)
            request('/datasets/' + original, token=token)
        viewer, analyst = accounts[0][0], accounts[1][0]
        features = {'job_title': 'Data Engineer', 'industry': 'Information Technology', 'province': 'Hồ Chí Minh', 'experience_years': 5, 'required_skills': ['python']}
        request('/predictions/salary', features, viewer['token'], expected=403)
        predicted = request('/predictions/salary', features, analyst['token'], expected=201)['data']
        request('/predictions/' + predicted['_id'], token=admin, expected=404)
        request('/users/' + viewer['id'], {'role': 'ANALYST'}, admin, 'PATCH')
        request('/auth/me', token=viewer['token'], expected=401)
        viewer['token'] = login(viewer['username'], accounts[0][1])
        request('/models', token=viewer['token'])
        request('/users/' + viewer['id'], {'enabled': False}, admin, 'PATCH')
        request('/auth/me', token=viewer['token'], expected=401)
        request('/auth/login', {'username': viewer['username'], 'password': accounts[0][1]}, expected=401)
        request('/users/' + analyst['id'] + '/revoke-sessions', token=admin, method='POST')
        request('/auth/me', token=analyst['token'], expected=401)
        rows = [{'source_job_id': 'SYNTHETIC-' + str(i), 'job_title': 'Kỹ sư kiểm thử', 'company_name': 'SYNTHETIC Co ' + str(i % 10),
                 'salary': '15 - 35 triệu', 'posted_year': 2024, 'posted_at': None, 'dataset_origin': 'synthetic'} for i in range(100)]
        blob = ('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n').encode('utf-8')
        chunk = {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob), 'row_count': 100}
        manifest = {'source': 'TEST-SYNTHETIC-STAGED', 'is_demo': True,
            'source_metadata': {'dataset_origin': 'synthetic', 'permission_status': 'SYNTHETIC_FIXTURE',
                'license_permission': 'Original project test fixture; synthetic, not public observations'}, 'chunks': [chunk, chunk]}
        staged = request('/datasets/staged', manifest, admin, headers={'Idempotency-Key': uuid4().hex}, expected=201)['data']
        version = staged['dataset_version']
        for i in range(2):
            boundary = '----' + uuid4().hex
            data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="chunk.jsonl"\r\nContent-Type: application/json\r\n\r\n').encode() + blob + f'\r\n--{boundary}--\r\n'.encode()
            req = urllib.request.Request(base + f'/api/v1/datasets/staged/{version}/chunks/{i}', data=data, method='PUT', headers={
                'Authorization': 'Bearer ' + admin, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
            with urllib.request.urlopen(req, timeout=60) as response:
                assert response.status == 200
        def wait(identifier):
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                job = request('/etl/jobs/' + identifier, token=admin)['data']
                if job['status'] == 'COMPLETED': return job
                if job['status'] in ['FAILED', 'CANCELLED']: raise AssertionError('Job failed: ' + str(job.get('error', {}).get('code')))
                time.sleep(2)
            raise TimeoutError('Job deadline exceeded')
        uploaded = request('/datasets/staged/' + version + '/complete', token=admin, method='POST', expected=202)['data']
        wait(uploaded['job_id'])
        submitted = request('/etl/jobs', {'dataset_version': version}, admin, expected=202)['data']
        wait(submitted['job_id'])
        report = request('/datasets/' + version + '/quality', token=admin)['data']
        assert report['counts'] == {'raw': 200, 'clean': 100, 'duplicate': 100, 'invalid': 0}
        assert report['profile']['year_from'] == 2024
        assert report['profile']['schema_version'] == 2
        assert report['profile']['industries'] == 0 and report['profile']['provinces'] == 0
        years = request('/analytics/job-years?dataset_version=' + version, token=admin)['data']
        assert years == [{'posted_year': 2024, 'count': 100}]
        assert request('/analytics/job-trends?dataset_version=' + version, token=admin)['data'] == []
        result.update({'result': 'PASS', 'dataset_version': version, 'quality': report, 'years': years})
        request('/datasets/' + original + '/activate', token=admin, method='POST')
        result['audit_count'] = request('/audit-logs?page_size=100', token=admin)['meta']['total']
    finally:
        for user, _ in accounts:
            request('/users/' + user['id'], {'enabled': False}, admin, 'PATCH')
        (root / 'artifacts').mkdir(exist_ok=True)
        (root / 'artifacts' / 'upgrade-2-live.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result': result['result'], 'dataset_version': result['dataset_version'], 'checks': len(observations), 'counts': result['quality']['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://localhost:8080')
    run(parser.parse_args().base)
