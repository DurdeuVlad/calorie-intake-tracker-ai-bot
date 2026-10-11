"""Add companion_memory: durable user-scoped facts saved by the agent."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d9a1f7b248"
down_revision: Union[str, Sequence[str], None] = "b4e2a17c9f03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companion_memory",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["food_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_companion_memory_user", "companion_memory", ["user_id"])
    # Dedupe rule: at most one ACTIVE row per (user, normalized text). The
    # partial index ignores soft-deleted rows so a forgotten fact can be saved
    # again later.
    op.create_index(
        "uq_companion_memory_active_text",
        "companion_memory",
        ["user_id", "normalized_text"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_companion_memory_active_text", table_name="companion_memory")
    op.drop_index("idx_companion_memory_user", table_name="companion_memory")
    op.drop_table("companion_memory")
