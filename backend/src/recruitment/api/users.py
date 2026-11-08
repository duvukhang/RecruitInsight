import re
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from recruitment.api.user_schemas import PasswordRequest
from recruitment.adapters.mongo import database
from recruitment.api.auth import admin
from recruitment.application.users import PUBLIC_FIELDS, UsersService, public_user

router = APIRouter(prefix='/api/v1', tags=['Quản trị người dùng'], dependencies=[Depends(admin)])
Role = Literal['ADMIN', 'ANALYST', 'VIEWER']


class CreateUser(PasswordRequest):
    username: str = Field(min_length=3, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
    role: Role


class UpdateUser(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    role: Role | None = None
    enabled: bool | None = None

    @model_validator(mode='after')
    def not_empty(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('Cần role hoặc enabled có giá trị.')
        return self


class UserView(BaseModel):
    id: str
    username: str
    role: Role
    enabled: bool | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserResponse(BaseModel):
    data: UserView


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class UserList(BaseModel):
    data: list[UserView]
    meta: PageMeta


class AuditView(BaseModel):
    id: str
    action: str
    actor_id: str | None = None
    resource_id: str | None = None
    created_at: datetime


class AuditList(BaseModel):
    data: list[AuditView]
    meta: PageMeta


@router.get('/users', response_model=UserList)
def users(page: int = Query(1, ge=1, le=10000), page_size: int = Query(25, ge=1, le=100),
          q: str = Query('', max_length=128), role: Role | None = None, enabled: bool | None = None):
    match = {}
    if q:
        match['username'] = {'$regex': '^' + re.escape(q)}
    if role:
        match['role'] = role
    if enabled is not None:
        match['enabled'] = enabled
    collection = database().users
    records = collection.find(match, PUBLIC_FIELDS).sort('username', 1).skip((page - 1) * page_size).limit(page_size).max_time_ms(5000)
    return {'data': [public_user(r) for r in records], 'meta': {'page': page, 'page_size': page_size, 'total': collection.count_documents(match, maxTimeMS=5000)}}


@router.post('/users', status_code=201, response_model=UserResponse)
def create_user(body: CreateUser, actor=Depends(admin)):
    return {'data': UsersService(database()).create(body.username, body.password, body.role, actor['_id'])}


@router.patch('/users/{identifier}', response_model=UserResponse)
def update_user(identifier: str, body: UpdateUser, actor=Depends(admin)):
    return {'data': UsersService(database()).mutate(identifier, body.model_dump(exclude_unset=True), actor['_id'])}


@router.post('/users/{identifier}/reset-password', response_model=UserResponse)
def reset_password(identifier: str, body: PasswordRequest, actor=Depends(admin)):
    return {'data': UsersService(database()).reset_password(identifier, body.password, actor['_id'])}


@router.post('/users/{identifier}/revoke-sessions', response_model=UserResponse)
def revoke_sessions(identifier: str, actor=Depends(admin)):
    return {'data': UsersService(database()).mutate(identifier, {}, actor['_id'], 'USER_REVOKE_SESSIONS')}


@router.get('/audit-logs', response_model=AuditList)
def audit_logs(page: int = Query(1, ge=1, le=10000), page_size: int = Query(25, ge=1, le=100),
               action: str = Query('', max_length=100), actor_id: str = Query('', max_length=128)):
    match = {k: v for k, v in {'action': action, 'actor_id': actor_id}.items() if v}
    db = database()
    service = UsersService(db)
    for pending in db.users.find({'audit_outbox.0': {'$exists': True}}, {'_id': 1}).limit(100):
        service.flush_audit(pending['_id'])
    collection = db.audit_logs
    # Projection prevents leaking legacy detail objects or arbitrary audit payloads.
    records = collection.find(match, {'action': 1, 'actor_id': 1, 'resource_id': 1, 'created_at': 1}).sort([('created_at', -1), ('_id', -1)]).skip((page - 1) * page_size).limit(page_size).max_time_ms(5000)
    return {'data': [{'id': str(r.pop('_id')), **r} for r in records],
            'meta': {'page': page, 'page_size': page_size, 'total': collection.count_documents(match, maxTimeMS=5000)}}
