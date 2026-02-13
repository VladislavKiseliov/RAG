"""add_cascade_delete

Revision ID: b04e507d243d
Revises: 3b0b6f4d8f4a
Create Date: 2026-02-13 10:33:09.176852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b04e507d243d'
down_revision: Union[str, Sequence[str], None] = '3b0b6f4d8f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
