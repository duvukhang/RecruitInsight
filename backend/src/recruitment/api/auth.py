from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from recruitment.adapters.mongo import database
from recruitment.application.auth import AuthService
from recruitment.domain.common import AppError
from recruitment.infrastructure.security import decode_access, token_hash

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
    if not user:
        raise AppError('UNAUTHENTICATED', 'Tài khoản không khả dụng.', 401)
    return user


def admin(user=Depends(current_user)):
    if user['role'] != 'ADMIN':
        raise AppError('FORBIDDEN', 'Cần quyền quản trị.', 403)
    return user


def analyst(user=Depends(current_user)):
    if user['role'] not in ['ADMIN','ANALYST']:
        raise AppError('FORBIDDEN','Cần quyền analyst hoặc admin.',403)
    return user


def cookies(response, raw, csrf, secure):
    response.set_cookie('refresh_token', raw, httponly=True, secure=secure, samesite='strict', path='/api/v1/auth', max_age=604800)
    response.set_cookie('csrf_token', csrf, httponly=False, secure=secure, samesite='strict', path='/api/v1/auth', max_age=604800)


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    data, raw, csrf = AuthService(database()).login(body.username, body.password, request.client.host)
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
    return {'data': {'id': user['_id'], 'username': user['username'], 'role': user['role']}}
