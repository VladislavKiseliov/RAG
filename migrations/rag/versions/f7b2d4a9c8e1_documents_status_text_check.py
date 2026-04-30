"""switch documents.status from enum to text+check

Revision ID: f7b2d4a9c8e1
Revises: c936e7b091b7
Create Date: 2026-04-29 15:10:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f7b2d4a9c8e1"
down_revision = "c936e7b091b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE rag_kernel.documents
        ALTER COLUMN status TYPE TEXT
        USING status::text;
        """
    )
    op.execute("DROP TYPE IF EXISTS rag_kernel.document_status_enum;")
    op.execute(
        """
        ALTER TABLE rag_kernel.documents
        ADD CONSTRAINT ck_documents_status
        CHECK (status IN ('pending', 'uploading', 'processing', 'extracting', 'indexing', 'completed', 'error'));
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE rag_kernel.documents DROP CONSTRAINT IF EXISTS ck_documents_status;")
    op.execute(
        """
        CREATE TYPE rag_kernel.document_status_enum AS ENUM (
            'pending',
            'uploading',
            'processing',
            'extracting',
            'indexing',
            'completed',
            'error'
        );
        """
    )
    op.execute(
        """
        ALTER TABLE rag_kernel.documents
        ALTER COLUMN status TYPE rag_kernel.document_status_enum
        USING status::rag_kernel.document_status_enum;
        """
    )
