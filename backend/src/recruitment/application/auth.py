import secrets
from datetime import timedelta
from pymongo import ReturnDocument
from recruitment.domain.common import AppError, now, uid
from recruitment.infrastructure.security import access_token, verify_password, token_hash, DUMMY_HASH


class AuthService:
    def __init__(self, db):
        self.db = db

    def login(self, username, password, peer, user_agent=''):
        minute = now().strftime('%Y%m%d%H%M')
        # Atomic, shared limit across API replicas. No password/token is persisted here.
        counter = self.db.auth_limits.find_one_and_update({'_id': peer + ':' + minute},
            {'$inc': {'count': 1}, '$set': {'expires_at': now() + timedelta(minutes=5)}}, upsert=True,
            return_document=ReturnDocument.AFTER)
        if counter['count'] > 10:
            raise AppError('RATE_LIMITED', 'Vui lòng thử đăng nhập lại sau một phút.', 429)
        user = self.db.users.find_one({'username': username})
        verified = verify_password(user['password_hash'] if user else DUMMY_HASH, password)
        if not verified or not user or not user.get('enabled'):
            raise AppError('UNAUTHENTICATED', 'Tên đăng nhập hoặc mật khẩu không đúng.', 401)
        raw = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(24)
        self.db.auth_sessions.insert_one({'_id': token_hash(raw), 'user_id': user['_id'],
            'auth_version': user.get('auth_version', 0),
            'csrf_hash': token_hash(csrf), 'expires_at': now() + timedelta(days=7), 'created_at': now(),
            'last_seen_at': now(), 'user_agent': user_agent[:256]})
        self.db.users.update_one({'_id': user['_id']}, {'$set': {'last_login_at': now()}})
        return self.response(user), raw, csrf

    def response(self, user):
        from recruitment.application.profile import identity
        return {'access_token': access_token(user), 'token_type': 'bearer', 'expires_in': 900,
                'user': identity(user)}

    def refresh(self, raw, csrf):
        session = self.db.auth_sessions.find_one_and_delete({'_id': token_hash(raw),
            'csrf_hash': token_hash(csrf), 'expires_at': {'$gt': now()}})
        if not session:
            raise AppError('UNAUTHENTICATED', 'Phiên đăng nhập đã hết hạn.', 401)
        user = self.db.users.find_one({'_id': session['user_id'], 'enabled': True})
        if not user or session.get('auth_version', 0) != user.get('auth_version', 0):
            raise AppError('UNAUTHENTICATED', 'Tài khoản không khả dụng.', 401)
        fresh, new_csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(24)
        self.db.auth_sessions.insert_one({'_id': token_hash(fresh), 'user_id': user['_id'],
            'auth_version': user.get('auth_version', 0),
            'csrf_hash': token_hash(new_csrf), 'expires_at': now() + timedelta(days=7), 'created_at': session.get('created_at', now()),
            'last_seen_at': now(), 'user_agent': session.get('user_agent', '')})
        return self.response(user), fresh, new_csrf
