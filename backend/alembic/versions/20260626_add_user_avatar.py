"""add avatar column to users

Revision ID: 20260626_add_avatar
Revises: 20260401_group_teacher_pay, 20260408_perf_indexes
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = '20260626_add_avatar'
down_revision = ('20260401_group_teacher_pay', '20260408_perf_indexes')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('avatar', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'avatar')
