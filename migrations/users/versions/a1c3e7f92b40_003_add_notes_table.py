"""003: add notes table

Revision ID: a1c3e7f92b40
Revises: 2c1c4cc00f90
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1c3e7f92b40'
down_revision: Union[str, Sequence[str], None] = '2c1c4cc00f90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('notes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guid', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=512), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('links', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('folder', sa.String(length=64), nullable=True),
    sa.Column('reminder', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('follow_up', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('chunk_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users_shema.users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guid'),
    schema='users_shema'
    )
    op.create_index('idx_note_on_user_id', 'notes', ['user_id'], unique=False, schema='users_shema')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_note_on_user_id', table_name='notes', schema='users_shema')
    op.drop_table('notes', schema='users_shema')