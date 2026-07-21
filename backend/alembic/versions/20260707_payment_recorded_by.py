"""payment.recorded_by_id — who received each payment

Revision ID: 20260707_pay_recorded_by
Revises: 20260706_rich_intake
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = '20260707_pay_recorded_by'
down_revision = '20260706_rich_intake'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite: FK ORM darajasida hal qilinadi (batch-mode inline FK nomsiz konstreynt
    # muammosini keltiradi), shuning uchun oddiy indekslangan ustun qo'shamiz.
    op.add_column('payments', sa.Column('recorded_by_id', sa.Integer(), nullable=True))
    op.create_index('ix_payments_recorded_by_id', 'payments', ['recorded_by_id'])


def downgrade() -> None:
    op.drop_index('ix_payments_recorded_by_id', 'payments')
    op.drop_column('payments', 'recorded_by_id')
