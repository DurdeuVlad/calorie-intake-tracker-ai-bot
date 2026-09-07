"""Add user_feedback for direct-command and AI-detected feedback capture.

This migration runs on the remote branch. The local branch (f7a3b9c5d204)
may have already created the user_feedback table with kind/message/context/
resolved columns. If so, we only need to add the source column. If not
(fresh CI database where remote branch runs first), we create the table
with all columns from both designs.
"""

import sqlalchemy as sa

from alembic import op

revision = "b3f7a1c9d4e2"
down_revision = "e6c2b8d4f103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "user_feedback" in existing_tables:
        # Local branch already created the table; just add the source column.
        existing_columns = {col["name"] for col in inspector.get_columns("user_feedback")}
        if "source" not in existing_columns:
            op.add_column(
                "user_feedback",
                sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'command'")),
            )
    else:
        # Fresh database — create the table with the remote schema.
        # The merge migration (e9f5a2b7c8d3) will add kind/context/resolved.
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "user_feedback" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("user_feedback")}
        if "source" in existing_columns:
            op.drop_column("user_feedback", "source")
    # Note: we do not drop the table here because the local branch migration
    # owns the table creation. Dropping it would break the local branch's
    # downgrade path.
