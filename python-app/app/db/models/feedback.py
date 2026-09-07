"""User feedback and bug reports.

When the user tells the bot something unexpected happened (a wrong log, a
surprising reply, a bug), the agent saves a feedback record with enough
context to diagnose and learn from it. Recent feedback is loaded into the
agent context so the model can avoid repeating the same mistake.
"""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # 'bug' | 'correction' | 'suggestion'
    message: Mapped[str] = mapped_column(Text)  # what the user said
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # recent conversation + tool trace
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column()
