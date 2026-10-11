import re

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _PasswordCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    device_id: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValueError("invalid email address")
        return normalized


class SignupRequest(_PasswordCredentials):
    pass


class LoginRequest(_PasswordCredentials):
    pass


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)
    device_id: str = Field(min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class MeResponse(BaseModel):
    account_id: int
    email: str
    food_user_id: int
