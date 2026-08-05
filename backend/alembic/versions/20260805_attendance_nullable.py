"""attendance.is_present ustunini nullable qilish — yangi qo'shilgan dars sanasi
uchun o'quvchilarni avtomatik "keldi" deb belgilamaslik, balki "belgilanmagan"
holatda saqlash imkonini beradi. Faqat cheklovni bo'shatadi (NOT NULL -> NULL),
mavjud qatorlardagi qiymatlar (True/False) hech qanday o'zgarmaydi.

Eslatma: 20260728_staff_warnings'ning 20260714_feedback_status'dan noto'g'ri
tarmoqlanishi allaqachon 20260729_facebook_leads'da birlashtirilgan va joriy
head shu zanjir orqali keladi — shu sababli bu migratsiya oddiy chiziqli
davomat, qayta merge qilish shart emas.

Revision ID: 20260805_attendance_nullable
Revises: 20260801b_referral_credited
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = '20260805_attendance_nullable'
down_revision = '20260801b_referral_credited'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('attendance') as batch_op:
        batch_op.alter_column(
            'is_present',
            existing_type=sa.Boolean(),
            nullable=True,
            existing_server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table('attendance') as batch_op:
        batch_op.alter_column(
            'is_present',
            existing_type=sa.Boolean(),
            nullable=False,
            existing_server_default=None,
        )
