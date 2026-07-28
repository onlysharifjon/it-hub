"""add lesson_time to groups

Revision ID: 20260723_group_lesson_time
Revises: 20260723_student_updated_at
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = '20260723_group_lesson_time'
down_revision = '20260723_student_updated_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('groups', sa.Column('lesson_time', sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column('groups', 'lesson_time')
