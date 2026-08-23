import uuid
from datetime import date as date_, datetime, timedelta

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

LEASE_SECONDS = 60
INBOX_MAX_ATTEMPTS = 3
OUTBOX_MAX_BACKOFF_SECONDS = 300


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class MessagingIdentity(Base):
    __tablename__ = "messaging_identities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    external_user_id: Mapped[str] = mapped_column(Text)


class TelegramAccessGrant(Base):
    """Persistent Telegram authorization, independent of journal data."""

    __tablename__ = "telegram_access_grants"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    granted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()


class MessagingRoute(Base):
    __tablename__ = "messaging_routes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    conversation_id: Mapped[str] = mapped_column(Text)


class FrontendLinkCode(Base):
    __tablename__ = "frontend_link_codes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column()
    consumed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def redeemable(self, now: datetime) -> bool:
        return self.consumed_at is None and self.expires_at > now

    def consume(self, now: datetime) -> None:
        self.consumed_at = now


class MessagingInboxMessage(Base):
    __tablename__ = "messaging_inbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING|IN_PROGRESS|COMPLETED|FAILED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    def claim(self) -> None:
        self.status = "IN_PROGRESS"
        self.lease_token = uuid.uuid4()
        self.lease_expires_at = _utcnow() + timedelta(seconds=LEASE_SECONDS)

    def complete(self, token: uuid.UUID) -> None:
        if token != self.lease_token:
            return
        self.status = "COMPLETED"
        self.payload = ""
        self.lease_token = None
        self.lease_expires_at = None

    def retry(self, token: uuid.UUID) -> None:
        if token != self.lease_token:
            return
        self.attempts += 1
        if self.attempts >= INBOX_MAX_ATTEMPTS:
            self.status = "FAILED"
            self.payload = ""
        else:
            self.status = "PENDING"
            self.next_attempt_at = _utcnow() + timedelta(seconds=min(300, 2**self.attempts))
        self.lease_token = None
        self.lease_expires_at = None


class MessagingOutboundMessage(Base):
    __tablename__ = "messaging_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    conversation_id: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING|IN_PROGRESS|SENT|FAILED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    def claim(self) -> None:
        self.status = "IN_PROGRESS"
        self.lease_token = uuid.uuid4()
        self.lease_expires_at = _utcnow() + timedelta(seconds=LEASE_SECONDS)

    def sent(self) -> None:
        self.status = "SENT"
        self.lease_token = None
        self.lease_expires_at = None

    def retry(self) -> None:
        self.status = "PENDING"
        self.attempts += 1
        self.next_attempt_at = _utcnow() + timedelta(seconds=min(OUTBOX_MAX_BACKOFF_SECONDS, 2 ** min(self.attempts, 8)))
        self.lease_token = None
        self.lease_expires_at = None


class MessagingDailyStatus(Base):
    __tablename__ = "messaging_daily_status"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    conversation_id: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    remote_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dirty: Mapped[bool] = mapped_column(Boolean, default=True)

    def request(self, text: str) -> None:
        self.text = text
        self.dirty = True

    def retry(self) -> None:
        """Give up rather than retry in a tight loop, mirroring
        PinnedDailyStatus.retry(): a persistently failing chat must not spin the
        dispatcher with zero backoff and exhaust the bot's global Telegram
        rate-limit budget. The next refresh() call (issued on every inbound
        message) marks the row dirty again with fresh text, so delivery is
        naturally retried instead of looped."""
        self.dirty = False

    def delivered(self, remote_message_id: str) -> None:
        self.remote_message_id = remote_message_id
        self.dirty = False


class PinnedDailyStatus(Base):
    __tablename__ = "pinned_daily_status"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    local_date: Mapped[date_] = mapped_column()
    desired_text: Mapped[str] = mapped_column(Text)
    desired_version: Mapped[int] = mapped_column(BigInteger, default=0)
    delivered_version: Mapped[int] = mapped_column(BigInteger, default=0)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING|IN_PROGRESS
    lease_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    def request(self, local_date: date_, text: str, now: datetime) -> None:
        self.local_date = local_date
        self.desired_text = text
        self.desired_version += 1
        self.status = "PENDING"
        self.updated_at = now
        self.lease_token = None
        self.lease_expires_at = None

    def claim(self) -> None:
        self.status = "IN_PROGRESS"
        self.lease_token = uuid.uuid4()
        self.lease_expires_at = _utcnow() + timedelta(seconds=LEASE_SECONDS)

    def delivered(self, version: int, token: uuid.UUID, message_id: int) -> None:
        if token != self.lease_token or version != self.desired_version:
            return
        self.delivered_version = version
        self.telegram_message_id = message_id
        self.status = "PENDING"
        self.lease_token = None
        self.lease_expires_at = None

    def remember_message(self, token: uuid.UUID, message_id: int) -> None:
        if token != self.lease_token:
            return
        self.telegram_message_id = message_id

    def retry(self, token: uuid.UUID) -> None:
        """Deliberate 'give up rather than truly retry' semantics (ported from the Java app):
        a failed delivery still marks the current desired version as delivered, so a
        persistently broken chat doesn't loop forever."""
        if token != self.lease_token:
            return
        self.delivered_version = self.desired_version
        self.status = "PENDING"
        self.lease_token = None
        self.lease_expires_at = None

    def clear_telegram_message(self) -> None:
        self.telegram_message_id = None
