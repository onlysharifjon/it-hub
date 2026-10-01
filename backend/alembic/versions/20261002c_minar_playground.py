"""minar_playground_solves — kod maydoni yechimlari.

Revision ID: 20261002c_minar_playground
Revises: 20261002b_hw_answers
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20261002c_minar_playground'
down_revision = '20261002b_hw_answers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'minar_playground_solves',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.String(20), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('solved_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('account_id', 'task_id', name='uq_minar_playground_solve'),
    )
    op.create_index('ix_minar_playground_solves_account_id', 'minar_playground_solves', ['account_id'])
    op.create_index('ix_minar_playground_solves_solved_at', 'minar_playground_solves', ['solved_at'])


def downgrade() -> None:
    op.drop_table('minar_playground_solves')
