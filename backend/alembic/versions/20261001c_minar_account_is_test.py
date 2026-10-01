"""minar_accounts.is_test — test akkaunt.

Test akkaunt arxivlangan "talaba"ga bog'lanadi (CRM hisoblari va reytingga kirmaydi),
lekin Minar Space'ga login qila oladi.

Revision ID: 20261001c_minar_account_is_test
Revises: 20261001b_user_salary_exempt
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op

revision = '20261001c_minar_account_is_test'
down_revision = '20261001b_user_salary_exempt'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('minar_accounts', sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('minar_accounts', 'is_test')
