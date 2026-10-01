"""minar_game_sessions — o'yin natijalari server tomonida tekshiriladi.

Revision ID: 20261001d_minar_game_sessions
Revises: 20261001c_minar_account_is_test
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op

revision = '20261001d_minar_game_sessions'
down_revision = '20261001c_minar_account_is_test'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'minar_game_sessions',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('game', sa.String(12), nullable=False),
        sa.Column('course', sa.String(20), nullable=False),
        sa.Column('difficulty', sa.String(10), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('state', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_minar_game_sessions_account_id', 'minar_game_sessions', ['account_id'])


def downgrade() -> None:
    op.drop_index('ix_minar_game_sessions_account_id', 'minar_game_sessions')
    op.drop_table('minar_game_sessions')
