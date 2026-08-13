"""004: add client_msg_id to messages

Revision ID: c7f1a9d3e6b2
Revises: a1c3e7f92b40
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7f1a9d3e6b2'
down_revision: Union[str, Sequence[str], None] = 'a1c3e7f92b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'messages',
        sa.Column('client_msg_id', postgresql.UUID(as_uuid=True), nullable=True),
        schema='users_shema',
    )
    op.create_index(
        'idx_message_on_chat_client_msg_id',
        'messages',
        ['chat_id', 'client_msg_id'],
        unique=True,
        schema='users_shema',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_message_on_chat_client_msg_id', table_name='messages', schema='users_shema')
    op.drop_column('messages', 'client_msg_id', schema='users_shema')
