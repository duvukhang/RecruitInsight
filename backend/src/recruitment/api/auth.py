from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from recruitment.adapters.mongo import database
from recruitment.application.auth import AuthService
from recruitment.domain.common import AppError
from recruitment.infrastructure.security import decode_access, token_hash
from recruitment.domain.permissions import permits

router = APIRouter(prefix='/api/v1/auth', tags=['Authentication'])
bearer = HTTPBearer(auto_error=False)


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise AppError('UNAUTHENTICATED', 'Vui lòng đăng nhập.', 401)
    claims = decode_access(credentials.credentials)
    user = database().users.find_one({'_id': claims['sub'], 'enabled': True})
    if not user or claims.get('auth_version', 0) != user.get('auth_version', 0):
        raise AppError('UNAUTHENTICATED', 'Tài khoản không khả dụng.', 401)
    return user


def admin(user=Depends(current_user)):
    if not permits(user['role'], 'manage'):
        raise AppError('FORBIDDEN', 'Cần quyền quản trị.', 403)
    return user


def analyst(user=Depends(current_user)):
    if not permits(user['role'], 'predict'):
        raise AppError('FORBIDDEN','Cần quyền analyst hoặc admin.',403)
    return user


def cookies(response, raw, csrf, secure):
    response.set_cookie('refresh_token', raw, httponly=True, secure=secure, samesite='strict', path='/api/v1/auth', max_age=604800)
    response.set_cookie('csrf_token', csrf, httponly=False, secure=secure, samesite='strict', path='/api/v1/auth', max_age=604800)


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    data, raw, csrf = AuthService(database()).login(body.username, body.password, request.client.host, request.headers.get('user-agent', '')[:256])
    cookies(response, raw, csrf, request.url.scheme == 'https')
    return {'data': data, 'csrf_token': csrf}


@router.post('/refresh')
def refresh(request: Request, response: Response, refresh_token: str = Cookie(default=''), x_csrf_token: str = Header(default='')):
    data, raw, csrf = AuthService(database()).refresh(refresh_token, x_csrf_token)
    cookies(response, raw, csrf, request.url.scheme == 'https')
    return {'data': data, 'csrf_token': csrf}


@router.post('/logout', status_code=204)
def logout(response: Response, refresh_token: str = Cookie(default=''), x_csrf_token: str = Header(default='')):
    if not refresh_token or not x_csrf_token:
        raise AppError('FORBIDDEN','Thiếu xác thực CSRF cho yêu cầu đăng xuất.',403)
    if not database().auth_sessions.find_one({'_id':token_hash(refresh_token),'csrf_hash':token_hash(x_csrf_token)}):
        raise AppError('FORBIDDEN','Yêu cầu đăng xuất không hợp lệ.',403)
    database().auth_sessions.delete_one({'_id': token_hash(refresh_token), 'csrf_hash': token_hash(x_csrf_token)})
    response.delete_cookie('refresh_token', path='/api/v1/auth')
    response.delete_cookie('csrf_token', path='/api/v1/auth')


@router.get('/me')
def me(user=Depends(current_user)):
    from recruitment.application.profile import identity
    return {'data': identity(user)}
