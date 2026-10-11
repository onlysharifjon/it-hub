"""parents.deleted_at — ilovadan "akkauntni o'chirish": ma'lumot saqlanadi, kirish yopiladi.

Revision ID: 20261012a_parent_deleted_at
Revises: 20261009a_finance_module
Create Date: 2026-10-12

Qaytarish (downgrade): ustun o'chiriladi — is_active=false holati saqlanib qoladi.
"""
import sqlalchemy as sa
from alembic import op

revision = '20261012a_parent_deleted_at'
down_revision = '20261009a_finance_module'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('parents', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('parents', 'deleted_at')
