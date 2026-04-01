"""add stage column to groups

Revision ID: 20260401_group_stage
Revises: 20260401_student_parents
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_group_stage'
down_revision = '20260401_student_parents'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('groups', sa.Column('stage', sa.String(20), nullable=False, server_default='foundation'))


def downgrade():
    op.drop_column('groups', 'stage')
