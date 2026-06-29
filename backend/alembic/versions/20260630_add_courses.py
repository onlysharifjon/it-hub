"""add courses table and course_id to groups

Revision ID: 20260630_add_courses
Revises: 20260629_add_leads
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = '20260630_add_courses'
down_revision = '20260629_add_leads'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('total_lessons', sa.Integer, nullable=False, server_default='24'),
        sa.Column('duration_months', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.add_column('groups', sa.Column('course_id', sa.Integer, sa.ForeignKey('courses.id'), nullable=True))


def downgrade():
    op.drop_column('groups', 'course_id')
    op.drop_table('courses')
