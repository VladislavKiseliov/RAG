"""documents: updated_at onupdate and rename column miniokey on s3key

Revision ID: dd62bdefa386
Revises: f7b2d4a9c8e1
Create Date: 2026-05-05 15:26:43.917880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd62bdefa386'
down_revision: Union[str, Sequence[str], None] = 'f7b2d4a9c8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
