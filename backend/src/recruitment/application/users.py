from contextlib import contextmanager
from pymongo.errors import DuplicateKeyError
from recruitment.domain.common import AppError, now, uid
from recruitment.infrastructure.security import hasher

PUBLIC_FIELDS = {'_id': 1, 'username': 1, 'role': 1, 'enabled': 1, 'created_at': 1, 'updated_at': 1}


def public_user(user):
    return {'id': user['_id'], **{k: user.get(k) for k in PUBLIC_FIELDS if k != '_id'}}


@contextmanager
def users_lock(db):
    """Non-expiring Mongo mutex: a crashed writer fails closed, never releases to a second writer.

    Standalone Mongo has no multi-document transactions. Never TTL this lock: an expired
    owner could resume and violate last-admin. Recovery requires a stopped writer (runbook).
    """
    owner = uid()
    try:
        db.admin_mutation_locks.insert_one({'_id': 'users', 'owner': owner, 'created_at': now()})
    except DuplicateKeyError:
        raise AppError('ADMIN_WRITE_BUSY', 'Có thay đổi tài khoản đang xử lý; thử lại sau.', 409)
    try:
        yield
    finally:
        db.admin_mutation_locks.delete_one({'_id': 'users', 'owner': owner})


class UsersService:
    def __init__(self, db):
        self.db = db

    def require_actor(self, actor):
        # CLI is a trusted local operator path; HTTP never accepts actor from input.
        if actor != 'CLI' and not self.db.users.find_one({'_id': actor, 'role': 'ADMIN', 'enabled': True}, {'_id': 1}):
            raise AppError('FORBIDDEN', 'Quyền quản trị vừa thay đổi; vui lòng đăng nhập lại.', 403)

    def event(self, action, actor, target):
        return {'_id': uid(), 'action': action, 'actor_id': actor, 'resource_id': target, 'created_at': now()}

    def flush_audit(self, target):
        # The outbox is committed atomically with the user change. A crashed API can
        # replay these events by their stable IDs without losing or duplicating audit.
        user = self.db.users.find_one({'_id': target}, {'audit_outbox': 1})
        for event in (user or {}).get('audit_outbox', []):
            self.db.audit_logs.update_one({'_id': event['_id']}, {'$setOnInsert': event}, upsert=True)
            self.db.users.update_one({'_id': target}, {'$pull': {'audit_outbox': {'_id': event['_id']}}})

    def create(self, username, password, role, actor):
        encoded = hasher.hash(password)  # expensive hashing outside the critical section
        with users_lock(self.db):
            self.require_actor(actor)
            record = {'_id': uid(), 'username': username, 'password_hash': encoded,
                'role': role, 'enabled': True, 'auth_version': 0, 'created_at': now()}
            record['audit_outbox'] = [self.event('USER_CREATE', actor, record['_id'])]
            try:
                self.db.users.insert_one(record)
            except DuplicateKeyError:
                raise AppError('USERNAME_EXISTS', 'Tên đăng nhập đã tồn tại.', 409)
            self.flush_audit(record['_id'])
            return public_user(record)

    def mutate(self, identifier, changes, actor, action='USER_UPDATE'):
        with users_lock(self.db):
            self.require_actor(actor)
            user = self.db.users.find_one({'_id': identifier})
            if not user:
                raise AppError('NOT_FOUND', 'Không tìm thấy tài khoản.', 404)
            if identifier == actor and changes.get('enabled') is False:
                raise AppError('SELF_DISABLE', 'Không thể tự vô hiệu hóa tài khoản đang dùng.', 409)
            loses_admin = user['role'] == 'ADMIN' and user.get('enabled') and (
                changes.get('role', user['role']) != 'ADMIN' or changes.get('enabled', True) is False)
            if loses_admin and self.db.users.count_documents({'role': 'ADMIN', 'enabled': True}) <= 1:
                raise AppError('LAST_ADMIN', 'Phải giữ ít nhất một quản trị viên hoạt động.', 409)
            # Epoch invalidates outstanding access JWTs as well as concurrent refreshes.
            self.db.users.update_one({'_id': identifier}, {'$set': {**changes, 'updated_at': now()}, '$inc': {'auth_version': 1},
                '$push': {'audit_outbox': self.event(action, actor, identifier)}})
            self.db.auth_sessions.delete_many({'user_id': identifier})
            self.flush_audit(identifier)
            return public_user(self.db.users.find_one({'_id': identifier}, PUBLIC_FIELDS))

    def reset_password(self, identifier, password, actor):
        return self.mutate(identifier, {'password_hash': hasher.hash(password)}, actor, 'USER_RESET_PASSWORD')
