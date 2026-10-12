"""Add mobile_devices (push token registry) and push_outbox (push delivery queue)."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f7a2b8c1d4"
down_revision: Union[str, Sequence[str], None] = "c3d9a1f7b248"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_devices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("push_token", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["auth_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "push_token"),
    )
    op.create_index("idx_mobile_devices_account", "mobile_devices", ["account_id"])

    op.create_table(
        "push_outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["auth_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_push_outbox_status_due", "push_outbox", ["status", "next_attempt_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_push_outbox_status_due", table_name="push_outbox")
    op.drop_table("push_outbox")
    op.drop_index("idx_mobile_devices_account", table_name="mobile_devices")
    op.drop_table("mobile_devices")
