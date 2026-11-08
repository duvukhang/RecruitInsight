import pytest
from recruitment.adapters.mongo import database
from recruitment.application.users import UsersService, users_lock
from recruitment.domain.common import AppError, uid
from recruitment.infrastructure.init_db import migrate


def test_nonexpiring_mutex_fails_closed_and_outbox_replays_idempotently():
    db = database()
    assert db.name.endswith('_test')
    migrate(db)
    user_id, event_id, actor = uid(), uid(), uid()
    event = {'_id': event_id, 'action': 'USER_UPDATE', 'actor_id': actor, 'resource_id': user_id}
    from recruitment.domain.common import now
    event['created_at'] = now()
    db.users.insert_one({'_id': user_id, 'username': uid(), 'password_hash': 'UNUSED-TEST', 'role': 'VIEWER', 'audit_outbox': [event]})
    try:
        with users_lock(db):
            with pytest.raises(AppError) as failure:
                with users_lock(db):
                    pytest.fail('Second writer entered critical section')
            assert failure.value.code == 'ADMIN_WRITE_BUSY'
        service = UsersService(db)
        service.flush_audit(user_id)
        db.users.update_one({'_id': user_id}, {'$push': {'audit_outbox': event}})
        service.flush_audit(user_id)
        assert db.audit_logs.count_documents({'_id': event_id}) == 1
        assert db.users.find_one({'_id': user_id})['audit_outbox'] == []
    finally:
        db.users.delete_one({'_id': user_id})
        db.audit_logs.delete_one({'_id': event_id})
