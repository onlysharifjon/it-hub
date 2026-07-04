"""add discounts table and discount_id to group_students

Revision ID: 20260704_add_discounts
Revises: 20260630_add_courses
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '20260704_add_discounts'
down_revision = '20260630_add_courses'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'discounts',
        sa.Column('id',            sa.Integer(),      primary_key=True),
        sa.Column('name',          sa.String(200),    nullable=False),
        sa.Column('discount_type', sa.String(10),     nullable=False, server_default='percent'),
        sa.Column('value',         sa.Numeric(12, 2), nullable=False),
        sa.Column('is_active',     sa.Boolean(),      nullable=False, server_default='true'),
        sa.Column('created_at',    sa.DateTime(),     nullable=False),
    )
    op.add_column(
        'group_students',
        sa.Column('discount_id', sa.Integer(), sa.ForeignKey('discounts.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('group_students', 'discount_id')
    op.drop_table('discounts')
