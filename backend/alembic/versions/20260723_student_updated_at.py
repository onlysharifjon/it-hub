"""add updated_at to students

Revision ID: 20260723_student_updated_at
Revises: 20260714_feedback_status
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = '20260723_student_updated_at'
down_revision = '20260714_feedback_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('students', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.execute('UPDATE students SET updated_at = created_at WHERE updated_at IS NULL')


def downgrade() -> None:
    op.drop_column('students', 'updated_at')
