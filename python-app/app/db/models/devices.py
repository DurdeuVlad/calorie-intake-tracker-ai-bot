from datetime import datetime, timedelta

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PUSH_MAX_ATTEMPTS = 5
PUSH_MAX_BACKOFF_SECONDS = 300


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class MobileDevice(Base):
    """A registered mobile install's push token. Rows are never deleted -- a
    DELETE just sets disabled_at so the token stops receiving pushes, and a
    later re-register clears it again (the unique (account_id, push_token)
    pair keeps refreshes idempotent)."""

    __tablename__ = "mobile_devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth_accounts.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(16))  # 'ios'|'android'
    push_token: Mapped[str] = mapped_column(Text)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()
    last_seen_at: Mapped[datetime] = mapped_column()
    disabled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("account_id", "push_token"),
        Index("idx_mobile_devices_account", "account_id"),
    )

    def refresh(
        self,
        platform: str,
        app_version: str | None,
        locale: str | None,
        now: datetime,
    ) -> None:
        """Upsert path: a re-register updates the mutable fields and re-enables
        a previously disabled device."""
        self.platform = platform
        self.app_version = app_version
        self.locale = locale
        self.updated_at = now
        self.last_seen_at = now
        self.disabled_at = None

    def disable(self, now: datetime) -> None:
        self.disabled_at = now
        self.updated_at = now


class PushOutboxMessage(Base):
    __tablename__ = "push_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth_accounts.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16))  # 'reminder'|'checkin'|'system'
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|sent|failed|cancelled
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column()
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_push_outbox_status_due", "status", "next_attempt_at"),
    )

    def mark_sent(self, now: datetime) -> None:
        self.status = "sent"
        self.sent_at = now

    def record_failure(self, now: datetime) -> None:
        """Bounded retry: after PUSH_MAX_ATTEMPTS failures the row is poison and
        goes to 'failed'; before that it stays 'pending' behind an exponential
        backoff so a transient provider outage doesn't resend in a hot loop
        (same bug class the messaging_outbox next_attempt_at filter fixes)."""
        self.attempts += 1
        if self.attempts >= PUSH_MAX_ATTEMPTS:
            self.status = "failed"
        else:
            self.next_attempt_at = now + timedelta(
                seconds=min(PUSH_MAX_BACKOFF_SECONDS, 2 ** min(self.attempts, 8))
            )
