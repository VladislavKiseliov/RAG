"""add_documents_meta

Revision ID: 5b3c8b7a1f1d
Revises: 0904163c21ed
Create Date: 2026-02-17 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5b3c8b7a1f1d'
down_revision: Union[str, Sequence[str], None] = '0904163c21ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет JSONB-метаданные к rag_kernel.documents."""
    op.add_column('documents', sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema='rag_kernel')


def downgrade() -> None:
    """Удаляет JSONB-метаданные из rag_kernel.documents."""
    op.drop_column('documents', 'meta', schema='rag_kernel')
