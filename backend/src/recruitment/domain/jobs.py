from recruitment.domain.common import AppError

TRANSITIONS = {
    'PENDING': {'QUEUED', 'CANCELLED'},
    'QUEUED': {'RUNNING', 'CANCELLED'},
    'RUNNING': {'COMMITTING', 'FAILED', 'CANCEL_REQUESTED'},
    'CANCEL_REQUESTED': {'CANCELLED', 'FAILED'},
    'COMMITTING': {'COMPLETED', 'FAILED'},
    'FAILED': {'QUEUED'},
    'COMPLETED': set(), 'CANCELLED': set(),
}


def validate_transition(current: str, target: str):
    if target not in TRANSITIONS.get(current, set()):
        raise AppError('INVALID_STATE', f'Không thể chuyển {current} sang {target}.', 409)
