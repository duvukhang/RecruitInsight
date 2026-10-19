from datetime import datetime, timezone
from uuid import uuid4


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class AppError(Exception):
    def __init__(self, code, message, status=400, details=None):
        self.code, self.message, self.status = code, message, status
        self.details = details or {}
        super().__init__(message)
