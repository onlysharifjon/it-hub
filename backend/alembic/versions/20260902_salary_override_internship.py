"""salary_overrides.is_internship — superadmin biror xodimni (o'qituvchi yoki
boshqa rol) biror oy uchun "stajirovka" deb belgilashi mumkin, shu oy uchun
oylik 0 bo'ladi (lekin darsga/ishga hech qanday cheklov yo'q).

Faqat qo'shimcha: mavjud jadvalga bitta ustun qo'shiladi.

Revision ID: 20260902_salary_override_internship
Revises: 20260826c_salary_overrides
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20260902_salary_override_internship'
down_revision = '20260826c_salary_overrides'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'salary_overrides',
        sa.Column('is_internship', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('salary_overrides', 'is_internship')
