"""facebook_leads — Facebook Lead Ads webhook (Make.com) uchun alohida jadval.
Faqat qo'shimcha (additive): bitta yangi jadval yaratiladi, mavjud jadvallar
hech qanday tarzda o'zgartirilmaydi. Shu bilan birga ikkita mavjud head
(20260724_merge, 20260728_staff_warnings) birlashtiriladi.

Revision ID: 20260729_facebook_leads
Revises: 20260724_merge, 20260728_staff_warnings
Create Date: 2026-07-29
"""
import sqlalchemy as sa
from alembic import op

revision = '20260729_facebook_leads'
down_revision = ('20260724_merge', '20260728_staff_warnings')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'facebook_leads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('full_name', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(30), nullable=False),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('form_name', sa.String(200), nullable=True),
        sa.Column('source', sa.String(30), nullable=False, server_default='facebook'),
        sa.Column('created_time', sa.DateTime(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_facebook_leads_phone', 'facebook_leads', ['phone'])
    op.create_index('ix_facebook_leads_received_at', 'facebook_leads', ['received_at'])


def downgrade() -> None:
    op.drop_index('ix_facebook_leads_received_at', table_name='facebook_leads')
    op.drop_index('ix_facebook_leads_phone', table_name='facebook_leads')
    op.drop_table('facebook_leads')
