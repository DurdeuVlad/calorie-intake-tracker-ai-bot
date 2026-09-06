import uuid
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.constraints import (
    MAX_BASIS_CHARS,
    MAX_CALORIES,
    MAX_CALORIES_PER_100G,
    MAX_IDENTIFIER_CHARS,
    MAX_PROVIDER_CHARS,
    MAX_QUANTITY,
    MAX_TEXT_CHARS,
    MIN_CALORIES,
    MIN_CALORIES_PER_100G,
    NUMERIC_PRECISION,
    NUMERIC_SCALE,
)


class PrivateFood(Base):
    __tablename__ = "private_foods"
    __table_args__ = (
        CheckConstraint(
            f"calories_per_100g IS NULL OR (calories_per_100g >= {MIN_CALORIES} AND calories_per_100g <= {MAX_CALORIES})",
            name="ck_private_foods_calories_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    calories_per_100g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    carbs_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    fat_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    created_at: Mapped[datetime] = mapped_column()


class NutritionSourceCache(Base):
    __tablename__ = "nutrition_source_cache"
    __table_args__ = (
        CheckConstraint(
            f"calories_per_100g IS NULL OR (calories_per_100g >= {MIN_CALORIES} AND calories_per_100g <= {MAX_CALORIES})",
            name="ck_nutrition_source_cache_calories_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    barcode: Mapped[str] = mapped_column(String(MAX_IDENTIFIER_CHARS), unique=True)
    product_name: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    calories_per_100g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    carbs_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    fat_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column()


class PendingNutritionQuote(Base):
    __tablename__ = "pending_nutrition_quotes"
    __table_args__ = (
        CheckConstraint(
            f"grams > 0 AND grams <= {MAX_QUANTITY}",
            name="ck_pending_nutrition_quotes_grams_range",
        ),
        CheckConstraint(
            f"calories_per_100g >= {MIN_CALORIES_PER_100G} AND calories_per_100g <= {MAX_CALORIES_PER_100G}",
            name="ck_pending_nutrition_quotes_calories_range",
        ),
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    quote_type: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS))  # PACKAGED_MATCH | AI_ESTIMATE
    product_name: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    brand: Mapped[str | None] = mapped_column(String(MAX_TEXT_CHARS), nullable=True)
    grams: Mapped[Decimal] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE))
    calories_per_100g: Mapped[int] = mapped_column(Integer)
    barcode: Mapped[str | None] = mapped_column(String(MAX_IDENTIFIER_CHARS), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The normalized search supplied to Open Food Facts. This is populated by
    # server code only and copied into durable evidence if the quote is used.
    source_query: Mapped[str | None] = mapped_column(String(MAX_BASIS_CHARS), nullable=True)
    source_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source_cache_hit: Mapped[bool] = mapped_column(default=False)
    estimate_basis: Mapped[str | None] = mapped_column(String(MAX_BASIS_CHARS), nullable=True)
    created_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()


class NutritionEvidence(Base):
    """Immutable, server-created provenance for nutrition used in a food item."""

    __tablename__ = "nutrition_evidence"
    __table_args__ = (
        CheckConstraint(
            f"quantity_grams > 0 AND quantity_grams <= {MAX_QUANTITY}",
            name="ck_nutrition_evidence_quantity_range",
        ),
        CheckConstraint(
            f"calories_per_100g >= {MIN_CALORIES_PER_100G} AND calories_per_100g <= {MAX_CALORIES_PER_100G}",
            name="ck_nutrition_evidence_calories_range",
        ),
        CheckConstraint(
            f"total_calories >= {MIN_CALORIES} AND total_calories <= {MAX_CALORIES}",
            name="ck_nutrition_evidence_total_calories_range",
        ),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    food_entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_entries.id", ondelete="CASCADE"))
    food_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_items.id", ondelete="CASCADE"), unique=True)
    selected_quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True)
    provider: Mapped[str] = mapped_column(String(MAX_IDENTIFIER_CHARS))
    source_name: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_query: Mapped[str | None] = mapped_column(String(MAX_BASIS_CHARS), nullable=True)
    selected_candidate: Mapped[str] = mapped_column(Text)
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(NUMERIC_PRECISION, NUMERIC_SCALE))
    calories_per_100g: Mapped[int] = mapped_column(Integer)
    total_calories: Mapped[int] = mapped_column(Integer)
    derivation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS))
    source_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source_cache_hit: Mapped[bool] = mapped_column(default=False)
    captured_at: Mapped[datetime] = mapped_column()


class OpenFoodFactsLookupCache(Base):
    """Provider response cache keyed by a one-way normalized lookup digest."""

    __tablename__ = "open_food_facts_lookup_cache"

    cache_key: Mapped[str] = mapped_column(String(MAX_IDENTIFIER_CHARS), primary_key=True)
    lookup_kind: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS))  # BARCODE | PACKAGED_NAME
    status: Mapped[str] = mapped_column(String(MAX_PROVIDER_CHARS))  # SUCCESS | NOT_FOUND | RATE_LIMITED | TEMPORARY_FAILURE | STALE_PROVIDER_FAILURE
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()
