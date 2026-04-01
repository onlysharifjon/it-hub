"""add teacher_pay_per_student to groups, create expenses table

Revision ID: 20260401_group_teacher_pay
Revises: 20260401_user_block_expiry
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_group_teacher_pay'
down_revision = '20260401_user_block_expiry'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('groups', sa.Column('teacher_pay_per_student', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.create_table(
        'expenses',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('expenses')
    op.drop_column('groups', 'teacher_pay_per_student')
