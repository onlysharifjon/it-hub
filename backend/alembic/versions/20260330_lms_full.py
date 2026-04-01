"""LMS full: students, groups, payments

Revision ID: 20260330_lms
Revises:
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = '20260330_lms'
down_revision = '20260330_full_restructure'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add full_name to users
    op.add_column('users', sa.Column('full_name', sa.String(200), nullable=True))

    # Students
    op.create_table(
        'students',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('phone1', sa.String(20), nullable=False),
        sa.Column('phone2', sa.String(20), nullable=True),
        sa.Column('telegram_id', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Groups
    op.create_table(
        'groups',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('teacher_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('course_price', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('schedule', sa.String(200), nullable=True),
        sa.Column('start_date', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Group students
    op.create_table(
        'group_students',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('group_id', sa.Integer, sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('student_id', sa.Integer, sa.ForeignKey('students.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Payments
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('student_id', sa.Integer, sa.ForeignKey('students.id'), nullable=False),
        sa.Column('group_id', sa.Integer, sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('month', sa.Integer, nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('paid_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('notes', sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('payments')
    op.drop_table('group_students')
    op.drop_table('groups')
    op.drop_table('students')
    op.drop_column('users', 'full_name')
