"""merge v2.0 feedback and remote day-boundary heads

Revision ID: d38d2201ba5e
Revises: a8b4c0d6e305, a1b5e9c3f8d4
Create Date: 2026-09-07 15:21:59.267241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd38d2201ba5e'
down_revision: Union[str, Sequence[str], None] = ('a8b4c0d6e305', 'a1b5e9c3f8d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
