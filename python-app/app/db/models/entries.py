from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.constraints import (
    MAX_CALORIES,
    MAX_PROVIDER_CHARS,
    MAX_QUANTITY,
    MAX_TEXT_CHARS,
    MAX_UNIT_CHARS,
    MIN_CALORIES,
    NUMERIC_PRECISION,
    NUMERIC_SCALE,
)


class FoodEntry(Base):
    __tablename__ = "food_entries"
    __table_args__ = (
        CheckConstraint(
            f"calories IS NULL OR (calories >= {MIN_CALORIES} AND calories <= {MAX_CALORIES})",
            name="ck_food_entries_calories_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    original_message: Mapped[str] = mapped_column(Text)
    eaten_at: Mapped[datetime] = mapped_column()
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nutrition_source: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS), default="manual")
    confidence: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS), default="unknown")
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
            raise ValueError(f"Calories must be between {MIN_CALORIES} and {MAX_CALORIES}.")
        self.original_message = description
        self.calories = calories

    def move_to(self, when: datetime, now: datetime) -> None:
        if when is None or when > now:
            raise ValueError("Future meal dates are not allowed.")
        self.eaten_at = when


class FoodItem(Base):
    __tablename__ = "food_items"
    __table_args__ = (
        CheckConstraint(
            f"calories IS NULL OR (calories >= {MIN_CALORIES} AND calories <= {MAX_CALORIES})",
            name="ck_food_items_calories_range",
        ),
        CheckConstraint(
            f"quantity IS NULL OR (quantity > 0 AND quantity <= {MAX_QUANTITY})",
            name="ck_food_items_quantity_range",
        ),
        CheckConstraint(
            f"quantity_grams IS NULL OR (quantity_grams > 0 AND quantity_grams <= {MAX_QUANTITY})",
            name="ck_food_items_quantity_grams_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_entries.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    quantity_grams: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    quantity_unit: Mapped[str] = mapped_column(String(MAX_UNIT_CHARS), default="unspecified")
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_grams: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    carbs_grams: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    fat_grams: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    nutrition_source: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS), default="manual")
    nutrition_confidence: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS), default="unknown")

    entry: Mapped[FoodEntry] = relationship(back_populates="items")

    def revise(self, name: str, calories: int) -> None:
        if calories < MIN_CALORIES or calories > MAX_CALORIES:
            raise ValueError(f"Calories must be between {MIN_CALORIES} and {MAX_CALORIES}.")
        self.name = name
        self.calories = calories

    def revise_calories(self, calories: int) -> None:
        if calories < MIN_CALORIES or calories > MAX_CALORIES:
            raise ValueError(f"Calories must be between {MIN_CALORIES} and {MAX_CALORIES}.")
        self.calories = calories
