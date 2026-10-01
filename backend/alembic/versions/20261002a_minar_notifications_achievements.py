"""minar_notifications, minar_achievements — Space bildirishnomalari va yutuqlar.

Revision ID: 20261002a_minar_notif_ach
Revises: 20261001d_minar_game_sessions
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20261002a_minar_notif_ach'
down_revision = '20261001d_minar_game_sessions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'minar_notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('link', sa.String(40), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_minar_notifications_account_id', 'minar_notifications', ['account_id'])
    op.create_index('ix_minar_notifications_created_at', 'minar_notifications', ['created_at'])
    op.create_table(
        'minar_achievements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(40), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('account_id', 'code', name='uq_minar_achievement'),
    )
    op.create_index('ix_minar_achievements_account_id', 'minar_achievements', ['account_id'])


def downgrade() -> None:
    op.drop_table('minar_achievements')
    op.drop_index('ix_minar_notifications_created_at', 'minar_notifications')
    op.drop_index('ix_minar_notifications_account_id', 'minar_notifications')
    op.drop_table('minar_notifications')
