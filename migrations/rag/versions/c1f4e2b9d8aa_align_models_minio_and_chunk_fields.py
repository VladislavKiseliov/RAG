"""Align rag models: add s3key, relax chunk_count, remove parent_id/text."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1f4e2b9d8aa"
down_revision: Union[str, Sequence[str], None] = "a3d2f9c4b1aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes to match current ORM models."""
    op.add_column(
        "documents",
        sa.Column("s3key", sa.String(length=1024), nullable=True),
        schema="rag_kernel",
    )

    op.alter_column(
        "documents",
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
        schema="rag_kernel",
    )

    op.drop_index("ix_parent_chunks_parent_id", table_name="parent_chunks", schema="rag_kernel")
    op.drop_column("parent_chunks", "text", schema="rag_kernel")
    op.drop_column("parent_chunks", "parent_id", schema="rag_kernel")


def downgrade() -> None:
    """Rollback schema changes introduced by this migration."""
    op.add_column("parent_chunks", sa.Column("parent_id", sa.String(length=64), nullable=True), schema="rag_kernel")
    op.add_column("parent_chunks", sa.Column("text", sa.Text(), nullable=True), schema="rag_kernel")

    op.execute("UPDATE rag_kernel.parent_chunks SET text = content WHERE text IS NULL")
    op.execute("UPDATE rag_kernel.parent_chunks SET parent_id = substring(cast(id as text), 1, 8) WHERE parent_id IS NULL")

    op.alter_column("parent_chunks", "text", nullable=False, schema="rag_kernel")
    op.alter_column("parent_chunks", "parent_id", nullable=False, schema="rag_kernel")

    op.create_index("ix_parent_chunks_parent_id", "parent_chunks", ["parent_id"], unique=False, schema="rag_kernel")

    op.execute("UPDATE rag_kernel.documents SET chunk_count = 0 WHERE chunk_count IS NULL")
    op.alter_column(
        "documents",
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
        schema="rag_kernel",
    )

    op.drop_column("documents", "s3key", schema="rag_kernel")
