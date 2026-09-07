"""users.salary + expenses.category/staff_id — xodimlar oyligi bo'limi.

users.salary — admin tomonidan belgilangan oylik miqdori.
expenses.category ('other' | 'salary') va expenses.staff_id — hunter xarajat
qo'shayotganda "oylik" turini tanlasa, qaysi xodimga qancha to'langanini
belgilaydi (superadmin Salary bo'limida ko'radi).

Faqat qo'shimcha: uchta yangi ustun, mavjud qatorlar buzilmaydi.

Revision ID: 20260826_staff_salary
Revises: 20260817_sales_credited_by
Create Date: 2026-08-26
"""
import sqlalchemy as sa
from alembic import op

revision = '20260826_staff_salary'
down_revision = '20260817_sales_credited_by'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('salary', sa.Numeric(12, 2), nullable=True))
    op.add_column('expenses', sa.Column('category', sa.String(20), nullable=False, server_default='other'))
    op.add_column('expenses', sa.Column('staff_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('expenses', 'staff_id')
    op.drop_column('expenses', 'category')
    op.drop_column('users', 'salary')
