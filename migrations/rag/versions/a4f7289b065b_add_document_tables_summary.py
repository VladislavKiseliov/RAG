"""add document_tables.summary

Revision ID: a4f7289b065b
Revises: d8ab6726a58b
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4f7289b065b'
down_revision: Union[str, Sequence[str], None] = 'd8ab6726a58b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document_tables', sa.Column('summary', sa.Text(), nullable=True), schema='rag_kernel')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_tables', 'summary', schema='rag_kernel')