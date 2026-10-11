import re
from datetime import datetime
from typing import Any

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


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)

    @field_validator("text")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped


class JournalActionEntry(BaseModel):
    id: int | None = None
    calories: int | None = None
    eaten_at: str | None = None
    description: str | None = None


class JournalActionResult(BaseModel):
    """One row of an apply_journal_actions batch, shaped for the client's
    editable confirmation card (audit section 4.3)."""

    ok: bool
    type: str
    entry: JournalActionEntry | None = None
    date: str | None = None
    message: str | None = None

    @classmethod
    def from_tool_row(cls, row: dict[str, Any]) -> "JournalActionResult":
        entry = row.get("entry") or {}
        return cls(
            ok=row.get("ok") is True,
            type=str(row.get("type") or "ACTION"),
            entry=(
                JournalActionEntry(
                    id=entry.get("id"),
                    calories=entry.get("calories"),
                    eaten_at=entry.get("eatenAt"),
                    description=entry.get("description"),
                )
                if entry
                else None
            ),
            date=row.get("date"),
            message=row.get("message"),
        )


class MessageResponse(BaseModel):
    reply: str
    actions: list[JournalActionResult] = []


class CompanionMemoryItem(BaseModel):
    id: int
    kind: str
    text: str
    source: str
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    memories: list[CompanionMemoryItem]
