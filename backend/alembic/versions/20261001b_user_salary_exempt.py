"""users.salary_exempt — oyliksiz ishlaydigan xodim.

O'qituvchi uchun FIX (5 mln) ham, talaba ulushi (KPI) ham hisoblanmaydi.
Sharifjon Muminov (username: sharifjon) oyliksiz ishlaydi — shu bilan belgilanadi.

Revision ID: 20261001b_user_salary_exempt
Revises: 20261001_group_teacher_history
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op

revision = '20261001b_user_salary_exempt'
down_revision = '20261001_group_teacher_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('salary_exempt', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE users SET salary_exempt = true WHERE username = 'sharifjon'")


def downgrade() -> None:
    op.drop_column('users', 'salary_exempt')
