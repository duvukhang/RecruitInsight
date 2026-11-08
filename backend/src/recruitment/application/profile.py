from datetime import timedelta
from pymongo import ReturnDocument
from recruitment.application.users import UsersService, users_lock
from recruitment.domain.common import AppError, now
from recruitment.infrastructure.security import hasher, verify_password

PROFILE_FIELDS = {'display_name', 'email', 'organization', 'bio', 'avatar_color'}


def identity(user):
    profile = user.get('profile') or {}
    return {'id': user['_id'], 'username': user['username'], 'role': user['role'],
        'display_name': profile.get('display_name') or user['username'], 'avatar_color': profile.get('avatar_color', 'cyan')}


def profile_view(user):
    profile = user.get('profile') or {}
    return {**identity(user), 'email': profile.get('email', ''), 'organization': profile.get('organization', ''),
        'bio': profile.get('bio', ''), 'created_at': user.get('created_at'), 'updated_at': user.get('updated_at'),
        'last_login_at': user.get('last_login_at')}


class ProfileService:
    def __init__(self, db):
        self.db = db
        self.users = UsersService(db)

    def fresh(self, user):
        fresh = self.db.users.find_one({'_id': user['_id'], 'enabled': True})
        if not fresh or fresh.get('auth_version', 0) != user.get('auth_version', 0):
            raise AppError('UNAUTHENTICATED', 'Phiên đăng nhập đã thay đổi. Vui lòng đăng nhập lại.', 401)
        return fresh

    def update(self, user, changes):
        if not changes or set(changes) - PROFILE_FIELDS:
            raise AppError('VALIDATION_ERROR', 'Chỉ được sửa các trường hồ sơ cá nhân.', 422)
        with users_lock(self.db):
            fresh = self.fresh(user)
            profile = {**(fresh.get('profile') or {}), **changes}
            self.db.users.update_one({'_id': user['_id']}, {'$set': {'profile': profile, 'updated_at': now()},
                '$push': {'audit_outbox': self.users.event('SELF_PROFILE_UPDATE', user['_id'], user['_id'])}})
            self.users.flush_audit(user['_id'])
            return profile_view(self.db.users.find_one({'_id': user['_id']}))

    def change_password(self, user, current, replacement):
        counter = self.db.auth_limits.find_one_and_update({'_id': 'profile-password:' + user['_id'] + ':' + now().strftime('%Y%m%d%H%M')},
            {'$inc': {'count': 1}, '$set': {'expires_at': now() + timedelta(minutes=5)}}, upsert=True, return_document=ReturnDocument.AFTER)
        if counter['count'] > 5:
            raise AppError('RATE_LIMITED', 'Đã thử đổi mật khẩu quá nhiều lần. Vui lòng thử lại sau một phút.', 429)
        if not verify_password(user['password_hash'], current):
            raise AppError('INVALID_PASSWORD', 'Mật khẩu hiện tại không đúng.', 400)
        if current == replacement:
            raise AppError('VALIDATION_ERROR', 'Mật khẩu mới phải khác mật khẩu hiện tại.', 422)
        encoded = hasher.hash(replacement)
        self.revoke(user, 'SELF_PASSWORD_CHANGE', encoded)

    def revoke(self, user, action='SELF_REVOKE_SESSIONS', encoded=None):
        with users_lock(self.db):
            fresh = self.fresh(user)
            changes = {'updated_at': now()}
            if encoded:
                changes['password_hash'] = encoded
            self.db.users.update_one({'_id': fresh['_id']}, {'$set': changes, '$inc': {'auth_version': 1},
                '$push': {'audit_outbox': self.users.event(action, fresh['_id'], fresh['_id'])}})
            self.db.auth_sessions.delete_many({'user_id': fresh['_id']})
            self.users.flush_audit(fresh['_id'])
