"""facebook_leads.phone nullable — ba'zi Facebook formalar faqat email so'raydi,
telefon umuman kelmasligi mumkin. Faqat qo'shimcha/yumshatish (additive):
ustun turi/nomi o'zgarmaydi, faqat NOT NULL cheklovi olib tashlanadi — mavjud
qatorlardagi qiymatlar hech qanday tarzda o'zgartirilmaydi.

Revision ID: 20260729c_fb_phone_null
Revises: 20260729b_fb_leads_link
Create Date: 2026-07-29
"""
import sqlalchemy as sa
from alembic import op

revision = '20260729c_fb_phone_null'
down_revision = '20260729b_fb_leads_link'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('facebook_leads') as batch_op:
        batch_op.alter_column('phone', existing_type=sa.String(30), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('facebook_leads') as batch_op:
        batch_op.alter_column('phone', existing_type=sa.String(30), nullable=False)
