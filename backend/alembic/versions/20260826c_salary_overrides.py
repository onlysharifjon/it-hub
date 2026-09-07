"""salary_overrides jadvali — superadmin o'qituvchining avtomatik hisoblangan
oyligini biror oy uchun qo'lda o'zgartirishi mumkin (formula: FIX 5 mln +
talaba boshiga 50 ming). Boshqa oylar formula bo'yicha hisoblanishda davom
etadi.

Faqat qo'shimcha: yangi jadval, mavjud narsalarga ta'sir qilmaydi.

Revision ID: 20260826c_salary_overrides
Revises: 20260826b_metodist_to_support_teacher
Create Date: 2026-08-26
"""
import sqlalchemy as sa
from alembic import op

revision = '20260826c_salary_overrides'
down_revision = '20260826b_metodist_to_support_teacher'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'salary_overrides',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('set_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('staff_id', 'month', 'year', name='uq_salary_override'),
    )


def downgrade() -> None:
    op.drop_table('salary_overrides')
