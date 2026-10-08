"""Payme Merchant API tranzaksiyalari.

Revision ID: 20261008a_payme_transactions
Revises: 20261005b_foundation_lessons
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = '20261008a_payme_transactions'
down_revision = '20261005b_foundation_lessons'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payme_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('paycom_id', sa.String(64), nullable=False),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('parent_invoices.id'), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('state', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('reason', sa.Integer(), nullable=True),
        sa.Column('paycom_time', sa.BigInteger(), nullable=False),
        sa.Column('create_time', sa.BigInteger(), nullable=False),
        sa.Column('perform_time', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('cancel_time', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_payme_transactions_id', 'payme_transactions', ['id'])
    op.create_index('ix_payme_transactions_paycom_id', 'payme_transactions', ['paycom_id'], unique=True)
    op.create_index('ix_payme_transactions_invoice_id', 'payme_transactions', ['invoice_id'])


def downgrade():
    op.drop_table('payme_transactions')
