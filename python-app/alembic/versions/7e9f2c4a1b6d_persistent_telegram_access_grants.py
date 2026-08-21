"""Add persistent Telegram access grants."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7e9f2c4a1b6d"
down_revision: Union[str, Sequence[str], None] = "585aef501d2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_access_grants",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("telegram_user_id"),
    )
    # Preserve every Telegram identity already admitted by the Java service.
    op.execute(sa.text("""
        INSERT INTO telegram_access_grants
            (telegram_user_id, is_admin, active, granted_by, created_at, updated_at)
        SELECT telegram_user_id, false, true, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM food_users
        WHERE telegram_user_id IS NOT NULL
    """))


def downgrade() -> None:
    op.drop_table("telegram_access_grants")
