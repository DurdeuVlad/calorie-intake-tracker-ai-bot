from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

UNDO_WINDOW_SECONDS = 10 * 60


class JournalChangeSet(Base):
    __tablename__ = "journal_change_sets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()
    undone_at: Mapped[datetime | None] = mapped_column(nullable=True)

    mutations: Mapped[list["JournalChangeMutation"]] = relationship(
        back_populates="change_set", cascade="all, delete-orphan", order_by="JournalChangeMutation.sequence_number"
    )

    def is_undoable_at(self, now: datetime) -> bool:
        return self.undone_at is None and now < self.expires_at

    def mark_undone(self, now: datetime) -> None:
        if self.undone_at is not None or now >= self.expires_at:
            raise ValueError("This change set can no longer be undone.")
        self.undone_at = now

    def add_mutation(self, action_type: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> None:
        sequence_number = len(self.mutations)
        self.mutations.append(
            JournalChangeMutation(sequence_number=sequence_number, action_type=action_type, before_state=before, after_state=after)
        )


class JournalChangeMutation(Base):
    __tablename__ = "journal_change_mutations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    change_set_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("journal_change_sets.id", ondelete="CASCADE"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[str] = mapped_column(String(16))  # CREATE | EDIT | MOVE | DELETE
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    change_set: Mapped[JournalChangeSet] = relationship(back_populates="mutations")
