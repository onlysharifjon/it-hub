"""student.is_demo — talaba hali demo darsga kelmagan holatini belgilash.

Faqat qo'shimcha (additive): bitta yangi ustun.

Revision ID: 20260731b_student_is_demo
Revises: 20260731_student_vacations
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = '20260731b_student_is_demo'
down_revision = '20260731_student_vacations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('students', sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.create_index('ix_students_is_demo', 'students', ['is_demo'])


def downgrade() -> None:
    op.drop_index('ix_students_is_demo', table_name='students')
    op.drop_column('students', 'is_demo')
