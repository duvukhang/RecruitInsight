from pydantic import BaseModel, ConfigDict, Field, field_validator


class PasswordRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    password: str = Field(min_length=12, max_length=256, json_schema_extra={'writeOnly': True})

    @field_validator('password')
    @classmethod
    def strength(cls, value):
        if not (any(c.islower() for c in value) and any(c.isupper() for c in value)
                and any(c.isdigit() for c in value) and any(not c.isalnum() and not c.isspace() for c in value)):
            raise ValueError('Mật khẩu cần chữ hoa, chữ thường, số và ký hiệu.')
        return value
