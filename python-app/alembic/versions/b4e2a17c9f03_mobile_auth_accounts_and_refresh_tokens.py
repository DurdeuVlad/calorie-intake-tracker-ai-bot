"""Add mobile auth accounts and rotating refresh tokens."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4e2a17c9f03"
down_revision: Union[str, Sequence[str], None] = "7e9f2c4a1b6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        # Application stores emails normalized to lowercase; uniqueness is enforced here.
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("social_provider", sa.String(length=32), nullable=True),
        sa.Column("social_subject", sa.Text(), nullable=True),
        sa.Column("food_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_user_id"], ["food_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("food_user_id"),
        sa.UniqueConstraint("social_provider", "social_subject"),
    )
    op.create_table(
        "mobile_refresh_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_to_id", sa.BigInteger(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["auth_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rotated_to_id"], ["mobile_refresh_tokens.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "idx_mobile_refresh_tokens_account", "mobile_refresh_tokens", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_mobile_refresh_tokens_account", table_name="mobile_refresh_tokens")
    op.drop_table("mobile_refresh_tokens")
    op.drop_table("auth_accounts")
