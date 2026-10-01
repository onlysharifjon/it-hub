"""minar_login_tokens (QR orqali kirish) va minar_sessions.password_reset_until.

Revision ID: 20261002e_minar_qr_login
Revises: 20261002d_minar_tournament
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20261002e_minar_qr_login'
down_revision = '20261002d_minar_tournament'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'minar_login_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_minar_login_tokens_account_id', 'minar_login_tokens', ['account_id'])
    op.create_index('ix_minar_login_tokens_token_hash', 'minar_login_tokens', ['token_hash'], unique=True)
    with op.batch_alter_table('minar_sessions') as b:
        b.add_column(sa.Column('password_reset_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('minar_sessions') as b:
        b.drop_column('password_reset_until')
    op.drop_table('minar_login_tokens')
