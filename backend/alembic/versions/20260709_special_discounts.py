"""special_discounts — ishlaydigan chegirmalar (bepul oy / oylik summa)

Revision ID: 20260709_special_discounts
Revises: 20260709_holidays_homework
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_special_discounts'
down_revision = '20260709_holidays_homework'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'special_discounts',
        sa.Column('id',            sa.Integer(),     primary_key=True),
        sa.Column('student_id',    sa.Integer(),     sa.ForeignKey('students.id'), nullable=False),
        sa.Column('group_id',      sa.Integer(),     sa.ForeignKey('groups.id'), nullable=True),
        sa.Column('kind',          sa.String(20),    nullable=False),
        sa.Column('amount',        sa.Numeric(12, 2), nullable=True),
        sa.Column('month',         sa.Integer(),     nullable=True),
        sa.Column('year',          sa.Integer(),     nullable=True),
        sa.Column('reason',        sa.String(300),   nullable=True),
        sa.Column('is_active',     sa.Boolean(),     nullable=False, server_default=sa.true()),
        sa.Column('created_by_id', sa.Integer(),     sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',    sa.DateTime(),    nullable=False),
    )
    op.create_index('ix_special_discounts_student_id', 'special_discounts', ['student_id'])
    op.create_index('ix_special_discounts_group_id', 'special_discounts', ['group_id'])


def downgrade() -> None:
    op.drop_table('special_discounts')
