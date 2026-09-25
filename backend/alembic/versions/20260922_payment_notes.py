"""payment_notes jadvali — to'lov/qarzdorlik bo'yicha qo'ng'iroq izohlari
(hunter/call_center uchun: masalan "2 kundan keyin to'layman dedi",
"telefonni ko'tarmadi"). Muayyan to'lovga emas, talabaga bog'liq.

Faqat qo'shimcha: yangi jadval, mavjud narsalarga ta'sir qilmaydi.

Revision ID: 20260922_payment_notes
Revises: 20260919_minar_space
Create Date: 2026-09-22
"""
import sqlalchemy as sa
from alembic import op

revision = '20260922_payment_notes'
down_revision = '20260919_minar_space'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payment_notes',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('payment_notes')
