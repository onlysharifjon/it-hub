"""Lid referrer (taklif qiluvchi) tizimi — manba darajasida sales'ga bog'lash
va oylik tarixiy statistika.

Faqat qo'shimcha (additive): ikkita yangi ustun + bitta yangi jadval.
FK'lar tekislangan Integer sifatida yoziladi (SQLite ALTER cheklovi).

Revision ID: 20260801_lead_referrals
Revises: 20260731b_student_is_demo
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = '20260801_lead_referrals'
down_revision = '20260731b_student_is_demo'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lead_sources', sa.Column('referrer_id', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('referred_by_id', sa.Integer(), nullable=True))
    op.create_index('ix_leads_referred_by_id', 'leads', ['referred_by_id'])

    op.create_table(
        'lead_referral_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('referrer_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=7), nullable=False),
        sa.Column('leads_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('paid_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('referrer_id', 'period', name='uq_referral_stat_period'),
    )
    op.create_index('ix_lead_referral_stats_referrer_id', 'lead_referral_stats', ['referrer_id'])
    op.create_index('ix_lead_referral_stats_period', 'lead_referral_stats', ['period'])


def downgrade() -> None:
    op.drop_index('ix_lead_referral_stats_period', table_name='lead_referral_stats')
    op.drop_index('ix_lead_referral_stats_referrer_id', table_name='lead_referral_stats')
    op.drop_table('lead_referral_stats')
    op.drop_index('ix_leads_referred_by_id', table_name='leads')
    op.drop_column('leads', 'referred_by_id')
    op.drop_column('lead_sources', 'referrer_id')
