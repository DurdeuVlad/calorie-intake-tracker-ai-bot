"""Add durable Open Food Facts lookup cache and provenance freshness fields."""

from alembic import op
import sqlalchemy as sa


revision = "e6c2b8d4f103"
down_revision = "d4f1a7c8e902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "open_food_facts_lookup_cache",
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("lookup_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    # Nullable/defaulted fields make the migration safe for active pending
    # quotes and pre-existing durable evidence.
    op.add_column("pending_nutrition_quotes", sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pending_nutrition_quotes", sa.Column("source_cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("nutrition_evidence", sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("nutrition_evidence", sa.Column("source_cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("nutrition_evidence", "source_cache_hit")
    op.drop_column("nutrition_evidence", "source_fetched_at")
    op.drop_column("pending_nutrition_quotes", "source_cache_hit")
    op.drop_column("pending_nutrition_quotes", "source_fetched_at")
    op.drop_table("open_food_facts_lookup_cache")
