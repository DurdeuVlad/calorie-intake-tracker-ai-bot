from datetime import date as date_, datetime

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportDelivery(Base):
    __tablename__ = "report_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    report_type: Mapped[str] = mapped_column(String(16))
    local_date: Mapped[date_] = mapped_column()
    delivered_at: Mapped[datetime] = mapped_column()
