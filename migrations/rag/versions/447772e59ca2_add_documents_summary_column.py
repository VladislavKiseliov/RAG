"""add documents summary column

Revision ID: 447772e59ca2
Revises: 87b0b83e6cf1
Create Date: 2026-07-21 15:03:32.312642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '447772e59ca2'
down_revision: Union[str, Sequence[str], None] = '87b0b83e6cf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True), schema='rag_kernel')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'summary', schema='rag_kernel')
