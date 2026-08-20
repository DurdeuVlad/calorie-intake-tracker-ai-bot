from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

MIN_CALORIES = 0
MAX_CALORIES = 10000


class FoodEntry(Base):
    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    original_message: Mapped[str] = mapped_column(Text)
    eaten_at: Mapped[datetime] = mapped_column()
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nutrition_source: Mapped[str] = mapped_column(String(32), default="manual")
    confidence: Mapped[str] = mapped_column(String(32), default="unknown")
    created_at: Mapped[datetime] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    items: Mapped[list["FoodItem"]] = relationship(back_populates="entry", cascade="all, delete-orphan")

    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def mark_deleted(self, when: datetime) -> None:
        self.deleted_at = when

    def restore(self) -> None:
        self.deleted_at = None

    def revise(self, description: str, calories: int) -> None:
        if not description or not description.strip():
            raise ValueError("A description is required.")
        if calories < MIN_CALORIES or calories > MAX_CALORIES:
            raise ValueError("Calories must be between 0 and 10000.")
        self.original_message = description
        self.calories = calories

    def move_to(self, when: datetime, now: datetime) -> None:
        if when is None or when > now:
            raise ValueError("Future meal dates are not allowed.")
        self.eaten_at = when


class FoodItem(Base):
    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_entries.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    quantity_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    quantity_unit: Mapped[str] = mapped_column(String(16), default="unspecified")
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    carbs_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fat_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    nutrition_source: Mapped[str] = mapped_column(String(32), default="manual")
    nutrition_confidence: Mapped[str] = mapped_column(String(32), default="unknown")

    entry: Mapped[FoodEntry] = relationship(back_populates="items")

    def revise(self, name: str, calories: int) -> None:
        if calories < MIN_CALORIES or calories > MAX_CALORIES:
            raise ValueError("Calories must be between 0 and 10000.")
        self.name = name
        self.calories = calories

    def revise_calories(self, calories: int) -> None:
        if calories < MIN_CALORIES or calories > MAX_CALORIES:
            raise ValueError("Calories must be between 0 and 10000.")
        self.calories = calories
