"""Add attendance table

Revision ID: 20260330_attendance
Revises: 20260330_lms
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = '20260330_attendance'
down_revision = '20260330_lms'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'attendance',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('lesson_date', sa.Date(), nullable=False),
        sa.Column('is_present', sa.Boolean(), nullable=False, server_default='true'),
        sa.UniqueConstraint('group_id', 'student_id', 'lesson_date', name='uq_attendance'),
    )


def downgrade():
    op.drop_table('attendance')
