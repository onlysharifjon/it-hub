"""students.sales_credited_by_id — "Sales" krediti kimga berilgani (to'lov
o'chirilganda krediti to'g'ri qaytarish/aynan o'sha xodimning statistikasidan
ayirish uchun). Avval faqat sana (sales_credited_at) saqlangan, kim ekani
saqlanmagan edi.

Faqat qo'shimcha: bitta yangi ustun.

Revision ID: 20260817_sales_credited_by
Revises: 20260806_sales_credit
Create Date: 2026-08-17
"""
import sqlalchemy as sa
from alembic import op

revision = '20260817_sales_credited_by'
down_revision = '20260806_sales_credit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('students', sa.Column('sales_credited_by_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('students', 'sales_credited_by_id')
