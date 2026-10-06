"""Telegram Gateway OTP: phone_verifications jadvali va parents.phone_verified_at.

Revision ID: 20261007a_phone_verifications
Revises: 20261006a_parent_online_payments
Create Date: 2026-10-07

Qaytarish (downgrade): jadval va ustun o'chiriladi — mavjud ota-ona akkauntlariga ta'sir qilmaydi.
"""
import sqlalchemy as sa
from alembic import op

revision = '20261007a_phone_verifications'
down_revision = '20261006a_parent_online_payments'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('parents', sa.Column('phone_verified_at', sa.DateTime(), nullable=True))
    op.create_table(
        'phone_verifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(64), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('gateway_request_id', sa.String(128), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('resend_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ip', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_sent_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('parents.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_phone_verifications_public_id', 'phone_verifications', ['public_id'], unique=True)
    op.create_index('ix_phone_verifications_phone', 'phone_verifications', ['phone'])
    # Bir telefon uchun bir vaqtda faqat bitta faol (pending) verification — parallel so'rovlardan himoya
    op.create_index('uq_phone_verification_pending', 'phone_verifications', ['phone'], unique=True,
                    postgresql_where=sa.text("status = 'pending'"),
                    sqlite_where=sa.text("status = 'pending'"))


def downgrade():
    op.drop_index('uq_phone_verification_pending', table_name='phone_verifications')
    op.drop_index('ix_phone_verifications_phone', table_name='phone_verifications')
    op.drop_index('ix_phone_verifications_public_id', table_name='phone_verifications')
    op.drop_table('phone_verifications')
    op.drop_column('parents', 'phone_verified_at')
