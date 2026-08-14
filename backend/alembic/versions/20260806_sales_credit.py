"""students.sales_credited_at va payments.via_sales — to'lov qo'shishda "Sales"
tugmasi bosilsa, sales rolidagi xodimga LeadReferralStat.paid_count +1
qo'shiladi (har talaba uchun faqat BIR MARTA).

Faqat qo'shimcha: ikkita yangi ustun.

Revision ID: 20260806_sales_credit
Revises: 20260805_attendance_nullable
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = '20260806_sales_credit'
down_revision = '20260805_attendance_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('students', sa.Column('sales_credited_at', sa.DateTime(), nullable=True))
    op.add_column('payments', sa.Column('via_sales', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('payments', 'via_sales')
    op.drop_column('students', 'sales_credited_at')
