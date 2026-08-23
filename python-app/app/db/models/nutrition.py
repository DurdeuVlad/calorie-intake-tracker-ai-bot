import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PrivateFood(Base):
    __tablename__ = "private_foods"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    calories_per_100g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    carbs_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fat_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column()


class NutritionSourceCache(Base):
    __tablename__ = "nutrition_source_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    barcode: Mapped[str] = mapped_column(String(64), unique=True)
    product_name: Mapped[str] = mapped_column(String(255))
    calories_per_100g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    carbs_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fat_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column()


class PendingNutritionQuote(Base):
    __tablename__ = "pending_nutrition_quotes"

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_users.id", ondelete="CASCADE"))
    quote_type: Mapped[str] = mapped_column(String(32))  # PACKAGED_MATCH | AI_ESTIMATE
    product_name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grams: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    calories_per_100g: Mapped[int] = mapped_column(Integer)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The normalized search supplied to Open Food Facts. This is populated by
    # server code only and copied into durable evidence if the quote is used.
    source_query: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source_cache_hit: Mapped[bool] = mapped_column(default=False)
    estimate_basis: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()


class NutritionEvidence(Base):
    """Immutable, server-created provenance for nutrition used in a food item."""

    __tablename__ = "nutrition_evidence"

    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    food_entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_entries.id", ondelete="CASCADE"))
    food_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_items.id", ondelete="CASCADE"), unique=True)
    selected_quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True)
    provider: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_query: Mapped[str | None] = mapped_column(String(512), nullable=True)
    selected_candidate: Mapped[str] = mapped_column(Text)
    quantity_grams: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    calories_per_100g: Mapped[int] = mapped_column(Integer)
    total_calories: Mapped[int] = mapped_column(Integer)
    derivation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(32))
    source_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source_cache_hit: Mapped[bool] = mapped_column(default=False)
    captured_at: Mapped[datetime] = mapped_column()


class OpenFoodFactsLookupCache(Base):
    """Provider response cache keyed by a one-way normalized lookup digest."""

    __tablename__ = "open_food_facts_lookup_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    lookup_kind: Mapped[str] = mapped_column(String(32))  # BARCODE | PACKAGED_NAME
    status: Mapped[str] = mapped_column(String(32))  # SUCCESS | NOT_FOUND | RATE_LIMITED | TEMPORARY_FAILURE
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column()
