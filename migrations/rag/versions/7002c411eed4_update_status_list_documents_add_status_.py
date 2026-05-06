"""update status list  documents:add status 'duplicate'

Revision ID: 7002c411eed4
Revises: 329d811f2b9d
Create Date: 2026-05-06 10:30:46.424146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7002c411eed4'
down_revision: Union[str, Sequence[str], None] = '329d811f2b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.drop_constraint('ck_documents_status', 'documents', schema='rag_kernel', type_='check')

    # 2. Создаем новое ограничение с учетом 'duplicate'
    op.create_check_constraint(
        'ck_documents_status',
        'documents',
        "status IN ('pending', 'uploading', 'processing', 'extracting', 'indexing', 'completed', 'error', 'duplicate')",
        schema='rag_kernel'
    )


def downgrade() -> None:
    # Возвращаем всё как было (удаляем новое, возвращаем старое без duplicate)
    op.drop_constraint('ck_documents_status', 'documents', schema='rag_kernel', type_='check')
    op.create_check_constraint(
        'ck_documents_status',
        'documents',
        "status IN ('pending', 'uploading', 'processing', 'extracting', 'indexing', 'completed', 'error')",
        schema='rag_kernel'
    )