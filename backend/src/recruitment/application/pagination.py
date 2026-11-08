"""Signed keyset cursors, bound to immutable dataset attempt, filters and sort."""
import hashlib
import json
from datetime import timedelta
import jwt
from recruitment.domain.common import AppError, now
from recruitment.infrastructure.config import settings


def query_hash(match, sort, order, size):
    return hashlib.sha256(json.dumps([match, sort, order, size], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def encode_cursor(record, field, digest):
    return jwt.encode({'iss': 'recruitment', 'aud': 'jobs-cursor', 'exp': now() + timedelta(days=1),
        'query_hash': digest, 'value': record.get(field), 'id': record['_id']},
        settings().jwt_secret.get_secret_value(), algorithm='HS256')


def cursor_condition(token, field, order, digest):
    try:
        data = jwt.decode(token, settings().jwt_secret.get_secret_value(), algorithms=['HS256'],
            audience='jobs-cursor', issuer='recruitment', options={'require': ['exp', 'query_hash', 'id']})
        if data['query_hash'] != digest or not isinstance(data['id'], str) or 'value' not in data:
            raise ValueError('Cursor scope changed')
        value, identifier = data['value'], data['id']
    except (jwt.PyJWTError, ValueError, TypeError):
        raise AppError('INVALID_CURSOR', 'Cursor không hợp lệ/hết hạn hoặc bộ lọc đã đổi. Về trang đầu hoặc chọn version cụ thể.', 422)
    operator = '$gt' if order == 'asc' else '$lt'
    same = {field: value, '_id': {operator: identifier}}
    if value is None:
        return {'$or': [same, {field: {'$ne': None}}]} if order == 'asc' else same
    branches = [{field: {operator: value}}, same]
    if order == 'desc':
        branches.append({field: None})  # Mongo range operators type-bracket; null sorts last descending.
    return {'$or': branches}
