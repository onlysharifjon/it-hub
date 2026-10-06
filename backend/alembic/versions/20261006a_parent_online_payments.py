"""Ota-ona ilovasi onlayn to'lovi: provayder tranzaksiyalari, invoys holatlari,
Payment → ParentInvoice bog'lami.

Revision ID: 20261006a_parent_online_payments
Revises: 20261005b_foundation_lessons
Create Date: 2026-10-06

Qaytarish (downgrade): payment_transactions jadvali va qo'shilgan ustunlar
o'chiriladi. Onlayn to'lovdan yozilgan Payment qatorlari SAQLANADI (pul
haqiqatan tushgan), faqat invoysga havolasi yo'qoladi.
"""
import sqlalchemy as sa
from alembic import op

revision = '20261006a_parent_online_payments'
down_revision = '20261005b_foundation_lessons'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('parent_invoices', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.add_column('parent_invoices', sa.Column('paid_at', sa.DateTime(), nullable=True))
    op.add_column('parent_invoices', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    # Eski STUB invoyslar hech qachon to'lanmagan — muddati o'tgan deb belgilaymiz.
    op.execute("UPDATE parent_invoices SET status = 'expired' WHERE status = 'pending'")

    op.add_column('payments', sa.Column('parent_invoice_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_payments_parent_invoice', 'payments', 'parent_invoices',
                          ['parent_invoice_id'], ['id'])
    op.create_index('ix_payments_parent_invoice_id', 'payments', ['parent_invoice_id'])

    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('parent_invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('provider_txn_id', sa.String(100), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='created'),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('provider_time', sa.BigInteger(), nullable=True),
        sa.Column('create_time', sa.BigInteger(), nullable=False),
        sa.Column('perform_time', sa.BigInteger(), nullable=True),
        sa.Column('cancel_time', sa.BigInteger(), nullable=True),
        sa.Column('cancel_reason', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('provider', 'provider_txn_id', name='uq_payment_txn_provider_id'),
    )
    op.create_index('ix_payment_transactions_invoice_id', 'payment_transactions', ['invoice_id'])


def downgrade():
    op.drop_index('ix_payment_transactions_invoice_id', table_name='payment_transactions')
    op.drop_table('payment_transactions')
    op.drop_index('ix_payments_parent_invoice_id', table_name='payments')
    op.drop_constraint('fk_payments_parent_invoice', 'payments', type_='foreignkey')
    op.drop_column('payments', 'parent_invoice_id')
    op.drop_column('parent_invoices', 'cancelled_at')
    op.drop_column('parent_invoices', 'paid_at')
    op.drop_column('parent_invoices', 'expires_at')
