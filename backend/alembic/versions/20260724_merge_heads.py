"""Merge two heads into one

Revision ID: 20260724_merge
Revises: 20260709_add_camera_attendance, 20260723_group_lesson_time
Create Date: 2026-07-24
"""
from alembic import op

revision = '20260724_merge'
down_revision = ('20260709_add_camera_attendance', '20260723_group_lesson_time')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
