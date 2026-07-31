"""add document_meta_sections

Revision ID: d8ab6726a58b
Revises: 660bef991125
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8ab6726a58b'
down_revision: Union[str, Sequence[str], None] = '660bef991125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('document_meta_sections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('doc_id', sa.UUID(), nullable=False),
    sa.Column('section_type', sa.String(length=32), nullable=False),
    sa.Column('s3_md_path', sa.String(length=1024), nullable=False),
    sa.CheckConstraint("section_type IN ('TOC', 'ABBREVIATIONS', 'APPENDICES')", name='ck_document_meta_sections_section_type'),
    sa.ForeignKeyConstraint(['doc_id'], ['rag_kernel.documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('doc_id', 'section_type', name='uq_document_meta_sections_doc_section_type'),
    schema='rag_kernel'
    )
    op.create_index('ix_document_meta_sections_doc_id', 'document_meta_sections', ['doc_id'], unique=False, schema='rag_kernel')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_document_meta_sections_doc_id', table_name='document_meta_sections', schema='rag_kernel')
    op.drop_table('document_meta_sections', schema='rag_kernel')