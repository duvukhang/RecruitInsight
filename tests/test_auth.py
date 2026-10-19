from fastapi.testclient import TestClient
from argon2 import PasswordHasher
from recruitment.main import app
from recruitment.adapters.mongo import database
from recruitment.domain.common import uid
from recruitment.infrastructure.init_db import migrate


def test_login_refresh_rotation_and_logout():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    user_id, username = uid(), uid()
    db.users.insert_one({'_id': user_id, 'username': username, 'role': 'VIEWER', 'enabled': True,
                         'password_hash': PasswordHasher().hash('test-password')})
    c = TestClient(app)
    try:
        assert c.get('/api/v1/auth/me').status_code == 401
        assert c.post('/api/v1/auth/login', json={'username': username, 'password': 'wrong'}).status_code == 401
        response = c.post('/api/v1/auth/login', json={'username': username, 'password': 'test-password'})
        assert response.status_code == 200
        token = response.json()['data']['access_token']
        assert c.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).json()['data']['role'] == 'VIEWER'
        old_cookie = c.cookies.get('refresh_token')
        csrf = response.json()['csrf_token']
        assert c.post('/api/v1/auth/refresh', headers={'X-CSRF-Token': 'wrong'}).status_code == 401
        rotated = c.post('/api/v1/auth/refresh', headers={'X-CSRF-Token': csrf})
        assert rotated.status_code == 200
        assert c.cookies.get('refresh_token') != old_cookie
        assert db.auth_sessions.count_documents({'user_id': user_id}) == 1
        assert c.post('/api/v1/auth/logout',headers={'X-CSRF-Token':'invalid-csrf'}).status_code==403
        assert db.auth_sessions.count_documents({'user_id':user_id})==1
        c.post('/api/v1/auth/logout', headers={'X-CSRF-Token': rotated.json()['csrf_token']})
        assert db.auth_sessions.count_documents({'user_id': user_id}) == 0
    finally:
        db.users.delete_one({'_id': user_id})
        db.auth_sessions.delete_many({'user_id': user_id})
        db.auth_limits.delete_many({'_id': {'$regex': '^testclient:'}})
