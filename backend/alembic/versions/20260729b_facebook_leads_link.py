"""facebook_leads.lead_id — Facebook webhook'dan kelgan lidlarni CRM'ning asosiy
`leads` jadvali (Lidlar bo'limi) bilan bog'lash uchun. Faqat qo'shimcha (additive):
bitta yangi, bo'sh (nullable) ustun qo'shiladi — mavjud jadvallar/qatorlar hech
qanday tarzda o'zgartirilmaydi yoki o'chirilmaydi.

Revision ID: 20260729b_fb_leads_link
Revises: 20260729_facebook_leads
Create Date: 2026-07-29
"""
import sqlalchemy as sa
from alembic import op

revision = '20260729b_fb_leads_link'
down_revision = '20260729_facebook_leads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('facebook_leads', sa.Column('lead_id', sa.Integer(), nullable=True))
    op.create_index('ix_facebook_leads_lead_id', 'facebook_leads', ['lead_id'])


def downgrade() -> None:
    op.drop_index('ix_facebook_leads_lead_id', table_name='facebook_leads')
    op.drop_column('facebook_leads', 'lead_id')
