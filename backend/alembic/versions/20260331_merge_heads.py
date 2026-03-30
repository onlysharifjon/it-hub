"""Merge two heads into one

Revision ID: 20260331_merge
Revises: 20260330_full_restructure, 20260330_attendance
Create Date: 2026-03-31
"""
from alembic import op

revision = '20260331_merge'
down_revision = ('20260330_full_restructure', '20260330_attendance')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
