from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanionMemory(Base):
    """Durable, user-reviewable facts the agent chose to save (audit section
    4.4) -- a separate store from conversation_memory, which stays the pruned
    10-turn working buffer. Rows are soft-deleted via deleted_at; uniqueness is
    enforced at the DB level on (user_id, normalized_text) among active rows."""

    __tablename__ = "companion_memory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))  # preference | restriction | goal | fact | other
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))  # 'agent' | 'user'
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def soft_delete(self, now: datetime) -> None:
        self.deleted_at = now
        self.updated_at = now
