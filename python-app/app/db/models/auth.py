from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthAccount(Base):
    __tablename__ = "auth_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Always stored normalized to lowercase.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    social_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    food_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()

    __table_args__ = (
        UniqueConstraint("social_provider", "social_subject"),
    )


class MobileRefreshToken(Base):
    __tablename__ = "mobile_refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth_accounts.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    device_id: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column()
    rotated_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mobile_refresh_tokens.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column()
