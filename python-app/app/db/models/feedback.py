from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(16))  # command | ai_detected
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column()
