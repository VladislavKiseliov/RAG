"""add abbreviations

Revision ID: fd77a5798a99
Revises: c6371f540e30
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd77a5798a99'
down_revision: Union[str, Sequence[str], None] = 'c6371f540e30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('abbreviations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('doc_id', sa.UUID(), nullable=False),
    sa.Column('acronym', sa.Text(), nullable=False),
    sa.Column('expansion', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['doc_id'], ['rag_kernel.documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('acronym', 'expansion', name='uq_abbreviations_acronym_expansion'),
    schema='rag_kernel'
    )
    op.create_index('ix_abbreviations_doc_id', 'abbreviations', ['doc_id'], unique=False, schema='rag_kernel')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_abbreviations_doc_id', table_name='abbreviations', schema='rag_kernel')
    op.drop_table('abbreviations', schema='rag_kernel')
