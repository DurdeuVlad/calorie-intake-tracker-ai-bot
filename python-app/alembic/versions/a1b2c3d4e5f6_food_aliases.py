"""Add user-scoped food aliases table (issue #108)."""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "e6c2b8d4f103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_aliases",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("calories_per_100g", sa.Integer(), nullable=True),
        sa.Column("fixed_calories", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["food_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "alias", name="uq_food_aliases_user_alias"),
    )


def downgrade() -> None:
    op.drop_table("food_aliases")
