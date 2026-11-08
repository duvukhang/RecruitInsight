from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from recruitment.adapters.mongo import database
from recruitment.application.auth import AuthService
from recruitment.application.profile import ProfileService
from recruitment.domain.common import AppError, now, uid
from recruitment.infrastructure.init_db import migrate
from recruitment.infrastructure.security import access_token, hasher, token_hash, verify_password
from recruitment.main import app


@pytest.fixture
def account():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    user = {'_id': uid(), 'username': uid(), 'role': 'VIEWER', 'enabled': True, 'auth_version': 0,
            'password_hash': hasher.hash('Profile-Test-2026!'), 'created_at': now()}
    db.users.insert_one(user)
    yield db, user, {'Authorization': 'Bearer ' + access_token(user)}, TestClient(app)
    db.users.delete_one({'_id': user['_id']})
    db.auth_sessions.delete_many({'user_id': user['_id']})
    db.audit_logs.delete_many({'actor_id': user['_id']})
    db.auth_limits.delete_many({'_id': {'$regex': '^(profile-password:' + user['_id'] + '|profile-test:)'}})


@pytest.mark.parametrize('role', ['ADMIN', 'ANALYST', 'VIEWER'])
def test_profile_persists_for_every_role_without_changing_permissions(account, role):
    db, user, headers, client = account
    db.users.update_one({'_id': user['_id']}, {'$set': {'role': role}})
    assert client.get('/api/v1/auth/profile').status_code == 401
    body = {'display_name': 'Nguyễn An', 'email': 'an@example.com', 'organization': 'DEMO', 'bio': 'Phân tích dữ liệu', 'avatar_color': 'violet'}
    result = client.patch('/api/v1/auth/profile', headers=headers, json=body)
    assert result.status_code == 200, result.text
    assert all(result.json()['data'][key] == value for key, value in body.items())
    assert result.json()['data']['role'] == role
    assert client.get('/api/v1/auth/me', headers=headers).json()['data']['display_name'] == body['display_name']
    assert db.users.find_one({'_id': user['_id']})['auth_version'] == 0
    assert 'password_hash' not in result.text and 'auth_version' not in result.text
    for invalid in [{}, {'role': 'ADMIN'}, {'id': uid()}, {'display_name': None}, {'display_name': ' '}, {'avatar_color': 'red'}, {'email': 'invalid'}, {'bio': 'x' * 601}]:
        assert client.patch('/api/v1/auth/profile', headers=headers, json=invalid).status_code == 422


def test_password_change_revokes_access_and_refresh_and_redacts_audit(account):
    db, user, headers, client = account
    _, raw, csrf = AuthService(db).login(user['username'], 'Profile-Test-2026!', 'profile-test')
    assert client.post('/api/v1/auth/password', headers=headers, json={'current_password': 'wrong', 'password': 'New-Profile-2026!'}).status_code == 400
    assert client.post('/api/v1/auth/password', headers=headers, json={'current_password': 'Profile-Test-2026!', 'password': 'weak'}).status_code == 422
    result = client.post('/api/v1/auth/password', headers=headers, json={'current_password': 'Profile-Test-2026!', 'password': 'New-Profile-2026!'})
    assert result.status_code == 204, result.text
    fresh = db.users.find_one({'_id': user['_id']})
    assert fresh['auth_version'] == 1 and verify_password(fresh['password_hash'], 'New-Profile-2026!')
    assert db.auth_sessions.count_documents({'user_id': user['_id']}) == 0
    assert client.get('/api/v1/auth/profile', headers=headers).status_code == 401
    with pytest.raises(AppError):
        AuthService(db).refresh(raw, csrf)
    audit = str(list(db.audit_logs.find({'actor_id': user['_id']})))
    assert 'SELF_PASSWORD_CHANGE' in audit and 'New-Profile-2026!' not in audit and 'password_hash' not in audit


def test_sessions_are_private_rotated_and_revoke_all_invalidates_access(account):
    db, user, headers, client = account
    _, raw, csrf = AuthService(db).login(user['username'], 'Profile-Test-2026!', 'profile-test', 'TEST Chrome/100')
    original = db.auth_sessions.find_one({'_id': token_hash(raw)})
    _, raw, _ = AuthService(db).refresh(raw, csrf)
    rotated = db.auth_sessions.find_one({'_id': token_hash(raw)})
    assert rotated['created_at'] == original['created_at']
    db.auth_sessions.insert_one({'_id': uid(), 'user_id': 'other-user', 'auth_version': 0, 'expires_at': now() + timedelta(days=1)})
    try:
        result = client.get('/api/v1/auth/sessions', headers=headers)
        assert result.status_code == 200 and result.json()['meta']['total'] == 1
        assert result.json()['data'][0]['user_agent'] == 'TEST Chrome/100'
        assert set(result.json()['data'][0]) == {'created_at', 'last_seen_at', 'expires_at', 'user_agent'}
        assert client.post('/api/v1/auth/revoke-sessions', headers=headers).status_code == 204
        assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
        assert db.auth_sessions.count_documents({'user_id': 'other-user'}) == 1
        with pytest.raises(AppError):
            ProfileService(db).update(user, {'display_name': 'stale'})
    finally:
        db.auth_sessions.delete_many({'user_id': 'other-user'})


def test_current_password_attempts_are_limited(account, monkeypatch):
    import importlib
    fixed = now()
    monkeypatch.setattr(importlib.import_module('recruitment.application.profile'), 'now', lambda: fixed)
    db, user, headers, client = account
    for _ in range(5):
        assert client.post('/api/v1/auth/password', headers=headers, json={'current_password': 'wrong', 'password': 'New-Profile-2026!'}).status_code == 400
    assert client.post('/api/v1/auth/password', headers=headers, json={'current_password': 'wrong', 'password': 'New-Profile-2026!'}).status_code == 429
