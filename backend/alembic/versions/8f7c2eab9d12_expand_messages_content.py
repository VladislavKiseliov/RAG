"""expand_messages_content

Revision ID: 8f7c2eab9d12
Revises: eb1b60eff2e4
Create Date: 2026-02-11 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f7c2eab9d12"
down_revision: Union[str, Sequence[str], None] = "eb1b60eff2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "messages",
        "content",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "messages",
        "content",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
