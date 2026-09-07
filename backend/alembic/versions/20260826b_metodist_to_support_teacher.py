"""users.role — "metodist" qiymati "support_teacher"ga o'zgartirildi.

Rol nomi UserRole.metodist enumida endi "support_teacher" qiymatini oladi
(Python identifikator o'zgarmadi, faqat saqlanadigan string qiymat). Mavjud
qatorlar shu migratsiya bilan yangilanadi — schema o'zgarishi yo'q, faqat
ma'lumot (data-only migration).

Revision ID: 20260826b_metodist_to_support_teacher
Revises: 20260826_staff_salary
Create Date: 2026-08-26
"""
from alembic import op

revision = '20260826b_metodist_to_support_teacher'
down_revision = '20260826_staff_salary'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET role='support_teacher' WHERE role='metodist'")


def downgrade() -> None:
    op.execute("UPDATE users SET role='metodist' WHERE role='support_teacher'")
