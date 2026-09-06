"""User-scoped food aliases (issue #108).

A food alias maps a user's custom shorthand (e.g. "cafea") to a canonical
description and optional nutrition shortcut (calories per 100g or a fixed
total). Aliases are owned by a single user and resolved before nutrition
lookup so the model can substitute "cafea" with "coffee with milk, 30ml".

The `alias_lower` column is a PostgreSQL stored generated column
(`lower(alias)`) that backs the case-insensitive unique constraint
``uq_food_aliases_user_alias_ci`` on ``(user_id, alias_lower)``."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.constraints import (
    MAX_CALORIES,
    MAX_CALORIES_PER_100G,
    MAX_TEXT_CHARS,
    MIN_CALORIES,
    MIN_CALORIES_PER_100G,
)


class FoodAlias(Base):
    __tablename__ = "food_aliases"
    __table_args__ = (
        UniqueConstraint("user_id", "alias_lower", name="uq_food_aliases_user_alias_ci"),
        CheckConstraint(
            f"calories_per_100g IS NULL OR (calories_per_100g >= {MIN_CALORIES_PER_100G} AND calories_per_100g <= {MAX_CALORIES_PER_100G})",
            name="ck_alias_cph_range",
        ),
        CheckConstraint(
            f"fixed_calories IS NULL OR (fixed_calories >= {MIN_CALORIES} AND fixed_calories <= {MAX_CALORIES})",
            name="ck_alias_fixed_range",
        ),
        CheckConstraint(
            "NOT (calories_per_100g IS NOT NULL AND fixed_calories IS NOT NULL)",
            name="ck_alias_one_calorie",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    alias_lower: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS), Computed("lower(alias)", persisted=True))
    canonical_name: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    calories_per_100g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fixed_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column()
