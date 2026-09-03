from datetime import datetime, time

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FoodUser(Base):
    __tablename__ = "food_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column()

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(String(64))
    calorie_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reports_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    morning_report_time: Mapped[time] = mapped_column(Time, default=time(8, 0))
    evening_report_time: Mapped[time] = mapped_column(Time, default=time(22, 0))
    pinned_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    onboarding_stage: Mapped[str] = mapped_column(String(32), default="TIMEZONE", server_default="TIMEZONE")
    preferred_language: Mapped[str] = mapped_column(String(2), default="ro", server_default="ro")
    # Hour (0-23, local time) the tracking day starts at. 0 (midnight) matches
    # the original calendar-day behavior every existing user already has.
    day_boundary_hour: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    day_boundary_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # "max": calorie_target is a ceiling (default, current behavior). "min": a
    # floor for users who need to eat more, not less -- inverts alert direction
    # and display framing wherever the target is surfaced.
    target_mode: Mapped[str] = mapped_column(String(8), default="max", server_default="max")
    budget_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    tracking_nudge_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    user: Mapped[FoodUser] = relationship(back_populates="settings")

    def require_calorie_target(self) -> None:
        self.onboarding_stage = "CALORIE_TARGET"

    def skip_calorie_target(self) -> None:
        self.onboarding_stage = "COMPLETE"
        self.onboarding_completed = True

    def set_preferred_language(self, lang: str | None) -> None:
        self.preferred_language = "en" if lang == "en" else "ro"
