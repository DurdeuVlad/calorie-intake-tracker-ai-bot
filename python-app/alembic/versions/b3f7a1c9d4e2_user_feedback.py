"""Add user_feedback for direct-command and AI-detected feedback capture."""

import sqlalchemy as sa

from alembic import op

revision = "b3f7a1c9d4e2"
down_revision = "e6c2b8d4f103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["food_users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_user_feedback_user_id", "user_feedback", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_feedback_user_id", table_name="user_feedback")
    op.drop_table("user_feedback")
