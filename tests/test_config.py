import pytest
from pydantic import ValidationError
from recruitment.infrastructure.config import Settings


def test_secrets_are_masked():
    config = Settings(mongo_password='sensitive-mongo', jwt_secret='sensitive-jwt',
                      admin_password='sensitive-admin')
    assert 'sensitive-' not in repr(config)


def test_missing_secret_fails_configuration(monkeypatch):
    for key in ('MONGO_PASSWORD', 'JWT_SECRET', 'ADMIN_PASSWORD'):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
