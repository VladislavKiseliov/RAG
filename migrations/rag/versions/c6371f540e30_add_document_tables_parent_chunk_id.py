"""add document_tables.parent_chunk_id

Revision ID: c6371f540e30
Revises: a4f7289b065b
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c6371f540e30'
down_revision: Union[str, Sequence[str], None] = 'a4f7289b065b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'document_tables',
        sa.Column('parent_chunk_id', postgresql.UUID(as_uuid=True), nullable=True),
        schema='rag_kernel',
    )
    op.create_foreign_key(
        'document_tables_parent_chunk_id_fkey',
        'document_tables', 'parent_chunks',
        ['parent_chunk_id'], ['id'],
        source_schema='rag_kernel', referent_schema='rag_kernel',
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('document_tables_parent_chunk_id_fkey', 'document_tables', schema='rag_kernel', type_='foreignkey')
    op.drop_column('document_tables', 'parent_chunk_id', schema='rag_kernel')