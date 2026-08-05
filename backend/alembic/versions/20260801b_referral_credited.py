"""leads.referral_credited_at — referral paid_count'ni faqat bir marta
hisoblash uchun (bosqich oldinga-orqaga o'zgartirilsa ham qayta sanalmasin).

Faqat qo'shimcha: bitta yangi ustun.

Revision ID: 20260801b_referral_credited
Revises: 20260801_lead_referrals
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = '20260801b_referral_credited'
down_revision = '20260801_lead_referrals'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('referral_credited_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'referral_credited_at')
