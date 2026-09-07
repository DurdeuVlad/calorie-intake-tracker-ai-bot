"""Add user_feedback table for bug reports and corrections.

This migration runs on the local branch. The remote branch (b3f7a1c9d4e2)
may have already created the user_feedback table with source/message/
created_at columns. If so, we only need to add kind/context/resolved.
If not (fresh database where local branch runs first), we create the
table with all columns from both designs.
"""

import sqlalchemy as sa

from alembic import op

revision = "f7a3b9c5d204"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "user_feedback" in existing_tables:
        # Remote branch already created the table; add our columns.
        existing_columns = {col["name"] for col in inspector.get_columns("user_feedback")}
        if "kind" not in existing_columns:
            op.add_column(
                "user_feedback",
                sa.Column("kind", sa.String(16), nullable=False, server_default=sa.text("'bug'")),
            )
        if "context" not in existing_columns:
            op.add_column("user_feedback", sa.Column("context", sa.Text(), nullable=True))
        if "resolved" not in existing_columns:
            op.add_column(
                "user_feedback",
                sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("user_feedback")}
        if "ix_user_feedback_user_id" not in existing_indexes:
            op.create_index("ix_user_feedback_user_id", "user_feedback", ["user_id"])
        if "ix_user_feedback_created_at" not in existing_indexes:
            op.create_index("ix_user_feedback_created_at", "user_feedback", ["created_at"])
    else:
        # Fresh database — create the table with the local schema.
        op.create_table(
            "user_feedback",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("food_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("context", sa.Text(), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_user_feedback_user_id", "user_feedback", ["user_id"])
        op.create_index("ix_user_feedback_created_at", "user_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_user_feedback_created_at", table_name="user_feedback")
    op.drop_index("ix_user_feedback_user_id", table_name="user_feedback")
    op.drop_table("user_feedback")
