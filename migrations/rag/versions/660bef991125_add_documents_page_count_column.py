"""add documents page_count column

Revision ID: 660bef991125
Revises: 447772e59ca2
Create Date: 2026-07-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '660bef991125'
down_revision: Union[str, Sequence[str], None] = '447772e59ca2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True), schema='rag_kernel')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'page_count', schema='rag_kernel')