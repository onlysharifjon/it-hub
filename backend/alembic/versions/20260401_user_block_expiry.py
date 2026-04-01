"""add block/expiry fields to users

Revision ID: 20260401_user_block_expiry
Revises: 20260401_tariffs_archive
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_user_block_expiry'
down_revision = '20260401_tariffs_archive'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('blocked_reason',  sa.Text(),        nullable=True))
    op.add_column('users', sa.Column('blocked_contact', sa.String(300),   nullable=True))
    op.add_column('users', sa.Column('blocked_at',      sa.DateTime(),     nullable=True))
    op.add_column('users', sa.Column('expires_at',      sa.DateTime(),     nullable=True))


def downgrade():
    op.drop_column('users', 'expires_at')
    op.drop_column('users', 'blocked_at')
    op.drop_column('users', 'blocked_contact')
    op.drop_column('users', 'blocked_reason')
