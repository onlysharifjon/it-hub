"""coin_transactions — o'qituvchi talabaga coin beradi (oylik 350 budjet)

Revision ID: 20260709_coins
Revises: 20260709_student_visits
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_coins'
down_revision = '20260709_student_visits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'coin_transactions',
        sa.Column('id',         sa.Integer(),   primary_key=True),
        sa.Column('student_id', sa.Integer(),   sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('teacher_id', sa.Integer(),   sa.ForeignKey('users.id'), nullable=False),
        sa.Column('group_id',   sa.Integer(),   sa.ForeignKey('groups.id'), nullable=True),
        sa.Column('amount',     sa.Integer(),   nullable=False),
        sa.Column('reason',     sa.String(300), nullable=True),
        sa.Column('created_at', sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_coin_transactions_student_id', 'coin_transactions', ['student_id'])
    op.create_index('ix_coin_transactions_teacher_id', 'coin_transactions', ['teacher_id'])
    op.create_index('ix_coin_transactions_created_at', 'coin_transactions', ['created_at'])


def downgrade() -> None:
    op.drop_table('coin_transactions')
