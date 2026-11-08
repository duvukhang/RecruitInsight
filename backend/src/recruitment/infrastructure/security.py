from datetime import timedelta
import hashlib
import secrets
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from recruitment.domain.common import AppError, now
from recruitment.infrastructure.config import settings

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def access_token(user):
    return jwt.encode({'sub': user['_id'], 'role': user['role'], 'auth_version': user.get('auth_version', 0), 'iss': 'recruitment',
                       'aud': 'recruitment-web', 'iat': now(), 'exp': now() + timedelta(minutes=15)},
                      settings().jwt_secret.get_secret_value(), algorithm='HS256')


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def decode_access(value):
    try:
        return jwt.decode(value, settings().jwt_secret.get_secret_value(), algorithms=['HS256'],
                          audience='recruitment-web', issuer='recruitment', options={'require': ['exp', 'sub', 'iat']})
    except jwt.PyJWTError:
        raise AppError('UNAUTHENTICATED', 'Phiên đăng nhập không hợp lệ hoặc đã hết hạn.', 401)
