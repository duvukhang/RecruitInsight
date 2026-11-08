"""Publish a clearly labelled synthetic 50k demo through the real HTTP pipeline."""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from generate_expanded_demo import generate


def run(base, rows):
    root = Path(__file__).resolve().parents[1]
    env = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    token = ''

    def request(path, data=None, method=None):
        payload = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(base + '/api/v1' + path, data=payload, method=method,
              headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'HTTP {error.code} {path}: ' + error.read().decode()) from None

    token = request('/auth/login', {'username': env['ADMIN_USERNAME'], 'password': env['ADMIN_PASSWORD']})['data']['access_token']
    file = generate(root / 'data' / 'DEMO-multi-50k.csv', rows)
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    metadata = {'source_type': 'synthetic', 'dataset_origin': 'synthetic', 'permission_status': 'SYNTHETIC_FIXTURE',
                'license_permission': 'Original deterministic project-generated fixture; no external job text.',
                'permission_evidence': 'scripts/generate_expanded_demo.py; all companies, dates and salaries are synthetic.',
                'adapter_version': 'demo-multi-v1', 'input_sha256': digest, 'row_count': rows,
                'observation_from': '2026-01-01', 'observation_to': '2026-09-27'}
    boundary = '----recruitment-' + uuid.uuid4().hex
    body = b''
    for key, value in {'source': 'DEMO-MULTI-50K', 'is_demo': 'true', 'source_metadata': json.dumps(metadata)}.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\nContent-Type: text/csv\r\n\r\n'.encode() + file.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(base + '/api/v1/datasets/upload', data=body, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Idempotency-Key': 'demo-multi-v1-' + digest})
    with urllib.request.urlopen(req, timeout=120) as response:
        uploaded = json.load(response)['data']

    def wait(identifier):
        previous = ''
        for _ in range(450):
            job = request('/etl/jobs/' + identifier)['data']
            if job['status'] != previous:
                print(identifier, job['status'], flush=True)
                previous = job['status']
            if job['status'] == 'COMPLETED':
                return job
            if job['status'] in ['FAILED', 'CANCELLED']:
                raise RuntimeError(str(job.get('error')))
            time.sleep(2)
        raise TimeoutError('Pipeline exceeded 15 minutes')

    wait(uploaded['job_id'])
    version = uploaded['dataset_version']
    etl = wait(request('/etl/jobs', {'dataset_version': version})['data']['job_id'])
    overview = request('/analytics/overview?dataset_version=' + version)
    assert overview['meta']['is_demo'] is True
    assert overview['data']['total_industries'] == 10 and overview['data']['total_provinces'] == 8
    counts = etl['metrics']['counts']
    assert counts['raw'] == rows and counts['clean'] + counts['invalid'] + counts['duplicate'] == rows
    assert request('/analytics/overview')['meta']['dataset_version'] == version, 'ETL did not activate this version; inspect concurrent publish'
    evidence = {'result': 'PASS', 'dataset_version': version, 'input_sha256': digest, 'input_rows': rows,
                'metadata': metadata, 'overview': overview, 'etl_metrics': etl['metrics']}
    report = root / 'artifacts' / 'profile-upgrade-data.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'dataset_version': version, 'counts': counts, 'industries': 10, 'provinces': 8}), flush=True)
    training = wait(request('/models/train', {'dataset_version': version})['data']['job_id'])
    models = [m for m in request('/models?page_size=100')['data'] if m['training_job_id'] == training['_id']]
    winner = next(m for m in models if m['selected_by_validation'] and m['algorithm'] != 'baseline')
    request('/models/' + winner['_id'] + '/activate', {}, 'POST')
    prediction = request('/predictions/salary', {'job_title': 'Data Engineer', 'industry': 'Information Technology',
                         'province': 'Hồ Chí Minh', 'experience_years': 5, 'required_skills': ['python', 'sql', 'docker']})['data']
    assert prediction['model_version'] == winner['_id'] and prediction['predicted_salary_vnd'] > 0
    evidence.update(training_metrics=training['metrics'], active_model=winner['_id'], algorithm=winner['algorithm'], prediction=prediction)
    report.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result': 'PASS', 'active_model': winner['_id'], 'algorithm': winner['algorithm']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://localhost:8080')
    parser.add_argument('--rows', type=int, default=50000)
    args = parser.parse_args()
    run(args.base, args.rows)
