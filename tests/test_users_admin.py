from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from recruitment.adapters.mongo import database
from recruitment.application.users import UsersService
from recruitment.infrastructure.init_db import migrate
from recruitment.infrastructure.security import access_token, hasher, token_hash
from recruitment.domain.common import AppError, uid, now
from recruitment.main import app


@pytest.fixture
def accounts():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    records = []
    for role in ['ADMIN', 'ADMIN', 'ANALYST', 'VIEWER']:
        record = {'_id': uid(), 'username': uid(), 'role': role, 'enabled': True, 'auth_version': 0,
                  'password_hash': hasher.hash('Test-Fixture-2026!'), 'created_at': now()}
        db.users.insert_one(record)
        records.append(record)
    yield db, records
    ids = [r['_id'] for r in records]
    db.users.delete_many({'_id': {'$in': ids}})
    db.auth_sessions.delete_many({'user_id': {'$in': ids}})
    db.audit_logs.delete_many({'actor_id': {'$in': ids}})
    db.auth_limits.delete_many({'_id': {'$regex': '^testclient:'}})


def headers(user):
    return {'Authorization': 'Bearer ' + access_token(user)}


def test_admin_matrix_strict_schema_and_projection(accounts):
    db, records = accounts
    client = TestClient(app)
    assert client.get('/api/v1/users').status_code == 401
    for user in records[2:]:
        for path in ['/users', '/audit-logs']:
            assert client.get('/api/v1' + path, headers=headers(user)).status_code == 403
        assert client.patch('/api/v1/users/unknown', headers=headers(user), json={'role': 'ADMIN'}).status_code == 403
        assert client.post('/api/v1/users/unknown/reset-password', headers=headers(user), json={'password': 'Secret-Test-2026!'}).status_code == 403
        for path in ['/etl/jobs', '/system/settings', '/datasets/unknown/invalid', '/datasets/unknown/duplicates', '/datasets/unknown/export/clean']:
            assert client.get('/api/v1' + path, headers=headers(user)).status_code == 403
        for path, body in [('/models/train', {'dataset_version': 'unknown'}), ('/models/unknown/activate', {}),
                           ('/users/unknown/revoke-sessions', None)]:
            assert client.post('/api/v1' + path, headers=headers(user), json=body).status_code == 403
    admin_headers = headers(records[0])
    response = client.get('/api/v1/users', headers=admin_headers)
    assert response.status_code == 200
    assert 'password_hash' not in response.text and 'auth_version' not in response.text
    assert client.post('/api/v1/users', headers=admin_headers, json={'username': 'weak', 'password': 'weak', 'role': 'VIEWER'}).status_code == 422
    assert client.patch('/api/v1/users/' + records[1]['_id'], headers=admin_headers, json={'enabled': 'false'}).status_code == 422
    assert client.patch('/api/v1/users/' + records[1]['_id'], headers=admin_headers, json={}).status_code == 422
    username = 'test-' + uid()
    body = {'username': username, 'password': 'Created-Test-2026!', 'role': 'VIEWER'}
    try:
        assert client.post('/api/v1/users', headers=admin_headers, json=body).status_code == 201
        assert client.post('/api/v1/users', headers=admin_headers, json=body).status_code == 409
        response = client.get('/api/v1/audit-logs', headers=admin_headers)
        assert response.status_code == 200 and body['password'] not in response.text
    finally:
        db.users.delete_many({'username': username})


def test_role_reset_disable_and_revoke_invalidate_access_and_refresh(accounts):
    db, records = accounts
    client = TestClient(app)
    actor, user = records[0], records[2]
    for endpoint, body in [('', {'role': 'VIEWER'}), ('/reset-password', {'password': 'Reset-Password-2026!'}),
                           ('/revoke-sessions', None), ('', {'enabled': False})]:
        user = db.users.find_one({'_id': user['_id']})
        token = headers(user)
        raw, csrf = uid(), uid()
        from datetime import timedelta
        db.auth_sessions.insert_one({'_id': token_hash(raw), 'user_id': user['_id'], 'csrf_hash': token_hash(csrf),
            'auth_version': user.get('auth_version', 0), 'expires_at': now() + timedelta(days=1)})
        url = '/api/v1/users/' + user['_id'] + endpoint
        response = client.post(url, headers=headers(actor), json=body) if endpoint else client.patch(url, headers=headers(actor), json=body)
        assert response.status_code == 200
        assert client.get('/api/v1/auth/me', headers=token).status_code == 401
        client.cookies.set('refresh_token', raw)
        assert client.post('/api/v1/auth/refresh', headers={'X-CSRF-Token': csrf}).status_code == 401
    assert client.patch('/api/v1/users/' + actor['_id'], headers=headers(actor), json={'enabled': False}).status_code == 409


def test_last_admin_concurrent_requests_fail_closed(accounts):
    db, records = accounts
    # A dedicated test database is required: do not modify unrelated administrators.
    other = db.users.count_documents({'role': 'ADMIN', 'enabled': True, '_id': {'$nin': [r['_id'] for r in records]}})
    assert other == 0, 'Run users tests on an isolated test database with no extra admins'
    def demote(user):
        try:
            UsersService(db).mutate(user['_id'], {'role': 'VIEWER'}, user['_id'])
            return 200
        except AppError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(demote, records[:2]))
    assert sorted(results) == [200, 409]
    assert db.users.count_documents({'role': 'ADMIN', 'enabled': True}) == 1


def test_current_user_reads_db_role_even_with_old_role_claim(accounts):
    db, records = accounts
    user = records[2]
    token = headers(user)
    db.users.update_one({'_id': user['_id']}, {'$set': {'role': 'VIEWER'}})
    client = TestClient(app)
    assert client.get('/api/v1/models', headers=token).status_code == 403
    assert client.post('/api/v1/predictions/salary', headers=token, json={}).status_code == 403


def test_brute_force_limit_and_stale_admin_write(accounts, monkeypatch):
    import importlib
    fixed_now = now()
    monkeypatch.setattr(importlib.import_module('recruitment.application.auth'), 'now', lambda: fixed_now)
    db, records = accounts
    client, user = TestClient(app), records[2]
    db.auth_limits.delete_many({'_id': {'$regex': '^testclient:'}})
    for _ in range(10):
        assert client.post('/api/v1/auth/login', json={'username': user['username'], 'password': 'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': user['username'], 'password': 'wrong'}).status_code == 429
    actor = records[0]
    db.users.update_one({'_id': actor['_id']}, {'$set': {'role': 'VIEWER'}})
    with pytest.raises(AppError) as error:
        UsersService(db).mutate(user['_id'], {'role': 'ADMIN'}, actor['_id'])
    assert error.value.status == 403
