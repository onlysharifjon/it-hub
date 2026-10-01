"""minar_tournament_awards, minar_job_runs — haftalik turnir va bir martalik fon ishlari.

Revision ID: 20261002d_minar_tournament
Revises: 20261002c_minar_playground
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20261002d_minar_tournament'
down_revision = '20261002c_minar_playground'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'minar_tournament_awards',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('week_start', sa.String(10), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id', ondelete='SET NULL'), nullable=True),
        sa.Column('group_name', sa.String(200), nullable=True),
        sa.Column('place', sa.Integer(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('coins', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('week_start', 'account_id', name='uq_minar_tournament_award'),
    )
    op.create_index('ix_minar_tournament_awards_week_start', 'minar_tournament_awards', ['week_start'])
    op.create_index('ix_minar_tournament_awards_account_id', 'minar_tournament_awards', ['account_id'])
    op.create_table(
        'minar_job_runs',
        sa.Column('key', sa.String(60), primary_key=True),
        sa.Column('done_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('minar_job_runs')
    op.drop_table('minar_tournament_awards')
