"""student_vacations — talaba ta'til oralig'i (hunter belgilaydi).

Faqat qo'shimcha (additive): bitta yangi jadval, mavjud jadvallar o'zgarmaydi.

Revision ID: 20260731_student_vacations
Revises: 20260729c_fb_phone_null
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = '20260731_student_vacations'
down_revision = '20260729c_fb_phone_null'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'student_vacations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(300), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_student_vacations_student_id', 'student_vacations', ['student_id'])


def downgrade() -> None:
    op.drop_index('ix_student_vacations_student_id', table_name='student_vacations')
    op.drop_table('student_vacations')
