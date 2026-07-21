"""teacher_feedbacks.status — hunter/call_center izohni kuzatib boradi

Revision ID: 20260714_feedback_status
Revises: 20260709_coins
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = '20260714_feedback_status'
down_revision = '20260709_coins'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK constraint qo'yilmaydi — SQLite ALTER orqali constraint qo'shishni qo'llamaydi
    op.add_column('teacher_feedbacks', sa.Column('status', sa.String(20), nullable=False, server_default='new'))
    op.add_column('teacher_feedbacks', sa.Column('status_updated_by_id', sa.Integer(), nullable=True))
    op.add_column('teacher_feedbacks', sa.Column('status_updated_at', sa.DateTime(), nullable=True))
    op.create_index('ix_teacher_feedbacks_status', 'teacher_feedbacks', ['status'])


def downgrade() -> None:
    op.drop_index('ix_teacher_feedbacks_status', 'teacher_feedbacks')
    op.drop_column('teacher_feedbacks', 'status_updated_at')
    op.drop_column('teacher_feedbacks', 'status_updated_by_id')
    op.drop_column('teacher_feedbacks', 'status')
