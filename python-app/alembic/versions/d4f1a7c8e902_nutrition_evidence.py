"""Persist server-selected Open Food Facts nutrition provenance."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d4f1a7c8e902"
down_revision = "7e9f2c4a1b6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable keeps existing pending quotes valid; it is only an audit input
    # and no historical quote can be trusted as a selected record.
    op.add_column("pending_nutrition_quotes", sa.Column("source_query", sa.String(length=512), nullable=True))
    op.create_table(
        "nutrition_evidence",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_entry_id", sa.BigInteger(), nullable=False),
        sa.Column("food_item_id", sa.BigInteger(), nullable=False),
        sa.Column("selected_quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_query", sa.String(length=512), nullable=True),
        sa.Column("selected_candidate", sa.Text(), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("calories_per_100g", sa.Integer(), nullable=False),
        sa.Column("total_calories", sa.Integer(), nullable=False),
        sa.Column("derivation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_entry_id"], ["food_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_item_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint("food_item_id"),
        sa.UniqueConstraint("selected_quote_id"),
    )


def downgrade() -> None:
    op.drop_table("nutrition_evidence")
    op.drop_column("pending_nutrition_quotes", "source_query")
