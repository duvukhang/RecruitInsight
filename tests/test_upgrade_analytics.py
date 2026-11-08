import pytest
from fastapi.testclient import TestClient
from recruitment.adapters.mongo import database
from recruitment.infrastructure.init_db import migrate
from recruitment.infrastructure.security import access_token
from recruitment.domain.common import uid, now
from recruitment.main import app


def test_year_only_analytics_server_filters_company_search_and_export_safety():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    version, attempt, user_id = uid(), uid(), uid()
    user = {'_id': user_id, 'username': uid(), 'role': 'ADMIN', 'enabled': True, 'password_hash': 'UNUSED-TEST'}
    db.users.insert_one(user)
    db.datasets.insert_one({'_id': version, 'dataset_id': version, 'status': 'PUBLISHED', 'published_attempt_id': attempt,
        'is_demo': True, 'created_at': now(), 'created_by': user_id, 'idempotency_key': uid(), 'source': 'TEST-ONLY'})
    rows = []
    for i in range(31):
        rows.append({'_id': uid(), 'dataset_version': version, 'attempt_id': attempt, 'source_job_key': str(i),
            'job_title': '\t=TEST()' if i == 0 else 'Kỹ sư', 'company_name': 'Unicode Công ty' if i == 30 else 'Other',
            'company_key': str(i), 'industry': 'IT', 'province': 'Hà Nội', 'salary_mid_vnd': i * 1e6 if i else None,
            'experience_years': None if i == 0 else i, 'posted_year': 2024, 'posted_at': None,
            'employment_type': 'Toàn thời gian', 'required_skills': []})
    db.cleaned_jobs.insert_many(rows)
    client, headers = TestClient(app), {'Authorization': 'Bearer ' + access_token(user)}
    try:
        base = '/api/v1/jobs?dataset_version=' + version
        result = client.get(base + '&q=Unicode', headers=headers).json()
        assert result['meta']['total'] == 1 and result['data'][0]['company_name'] == 'Unicode Công ty'
        result = client.get(base + '&salary_min=25000000&salary_max=30000000&experience_min=25&posted_year=2024', headers=headers).json()
        assert result['meta']['total'] == 6
        assert len(client.get(base + '&page=2&page_size=25', headers=headers).json()['data']) == 6
        assert client.get(base + '&salary_min=20&salary_max=10', headers=headers).status_code == 422
        assert client.get(base + '&experience_min=nan', headers=headers).status_code == 422
        for sort in ['posted_at', 'salary_mid_vnd', 'experience_years', 'job_title']:
            for order in ['asc', 'desc']:
                token, ids = '', []
                while token is not None:
                    from urllib.parse import quote
                    response = client.get(base + f'&page_size=7&sort={sort}&order={order}&cursor=' + quote(token), headers=headers)
                    assert response.status_code == 200, (sort, order, response.text)
                    payload = response.json()
                    ids.extend(item['_id'] for item in payload['data'])
                    assert payload['meta']['total'] == 31
                    token = payload['meta']['next_cursor']
                assert len(ids) == len(set(ids)) == 31, (sort, order)
        page = client.get(base + '&cursor=&page_size=7', headers=headers).json()
        token = page['meta']['next_cursor']
        from urllib.parse import quote
        assert client.get(base + '&cursor=' + quote(token) + '&page_size=7&q=changed', headers=headers).status_code == 422
        assert client.get(base + '&cursor=forged&page_size=7', headers=headers).status_code == 422
        assert client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401
        years = client.get('/api/v1/analytics/job-years?dataset_version=' + version, headers=headers).json()
        assert years['data'] == [{'posted_year': 2024, 'count': 31}]
        assert years['meta']['reference_period'] == {'from': None, 'to': None}
        assert client.get('/api/v1/analytics/job-trends?dataset_version=' + version, headers=headers).json()['data'] == []
        assert client.get(base + '&posted_from=2024-01-01', headers=headers).json()['meta']['total'] == 0
        exported = client.get(f'/api/v1/datasets/{version}/export/clean', headers=headers)
        assert exported.status_code == 200 and "'\t=TEST()" in exported.text
        explain = db.cleaned_jobs.find({'dataset_version': version, 'attempt_id': attempt, 'company_name': 'Unicode Công ty'}).hint('dataset_version_1_attempt_id_1_company_name_1__id_1').explain()
        assert explain['executionStats']['nReturned'] == 1
        assert explain['executionStats']['totalDocsExamined'] <= 1
    finally:
        db.users.delete_one({'_id': user_id})
        db.cleaned_jobs.delete_many({'dataset_version': version})
        db.datasets.delete_one({'_id': version})
