"""add photo_path to students

Revision ID: 20260704_add_student_photo
Revises: 20260704_add_discounts
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '20260704_add_student_photo'
down_revision = '20260704_add_discounts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('students', sa.Column('photo_path', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('students', 'photo_path')
