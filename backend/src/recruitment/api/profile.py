from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from recruitment.adapters.mongo import database
from recruitment.api.auth import current_user
from recruitment.api.user_schemas import PasswordRequest
from recruitment.application.profile import ProfileService, profile_view
from recruitment.domain.common import now

router = APIRouter(prefix='/api/v1/auth', tags=['Hồ sơ cá nhân'])
Color = Literal['cyan', 'blue', 'violet', 'emerald', 'amber']


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    display_name: str | None = Field(None, min_length=1, max_length=80)
    email: str | None = Field(None, max_length=254, pattern=r'^(?:|[^\s@]+@[^\s@]+\.[^\s@]+)$')
    organization: str | None = Field(None, max_length=120)
    bio: str | None = Field(None, max_length=600)
    avatar_color: Color | None = None

    @model_validator(mode='after')
    def supplied(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Cần ít nhất một trường hồ sơ có giá trị.')
        return self


class ProfileView(BaseModel):
    id: str
    username: str
    role: Literal['ADMIN', 'ANALYST', 'VIEWER']
    display_name: str
    avatar_color: Color
    email: str
    organization: str
    bio: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None


class ProfileResponse(BaseModel):
    data: ProfileView


class ChangePassword(PasswordRequest):
    current_password: str = Field(min_length=1, max_length=256, json_schema_extra={'writeOnly': True})


class SessionView(BaseModel):
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    expires_at: datetime
    user_agent: str = ''


class SessionPage(BaseModel):
    page: int
    page_size: int
    total: int


class SessionsResponse(BaseModel):
    data: list[SessionView]
    meta: SessionPage


@router.get('/profile', response_model=ProfileResponse)
def profile(user=Depends(current_user)):
    return {'data': profile_view(user)}


@router.patch('/profile', response_model=ProfileResponse)
def update_profile(body: ProfileUpdate, user=Depends(current_user)):
    return {'data': ProfileService(database()).update(user, body.model_dump(exclude_unset=True))}


@router.post('/password', status_code=204)
def change_password(body: ChangePassword, user=Depends(current_user)):
    ProfileService(database()).change_password(user, body.current_password, body.password)


@router.get('/sessions', response_model=SessionsResponse)
def sessions(page: int = Query(1, ge=1, le=1000), page_size: int = Query(10, ge=1, le=50), user=Depends(current_user)):
    match = {'user_id': user['_id'], 'expires_at': {'$gt': now()}, 'auth_version': user.get('auth_version', 0)}
    if user.get('auth_version', 0) == 0:
        match.pop('auth_version')
        match['$or'] = [{'auth_version': 0}, {'auth_version': {'$exists': False}}]
    collection = database().auth_sessions
    projection = {'_id': 0, 'created_at': 1, 'last_seen_at': 1, 'expires_at': 1, 'user_agent': 1}
    return {'data': list(collection.find(match, projection).sort([('created_at', -1), ('_id', 1)]).skip((page - 1) * page_size).limit(page_size).max_time_ms(5000)),
        'meta': {'page': page, 'page_size': page_size, 'total': collection.count_documents(match, maxTimeMS=5000)}}


@router.post('/revoke-sessions', status_code=204)
def revoke_sessions(user=Depends(current_user)):
    ProfileService(database()).revoke(user)
