"""attendance.is_present ustunini nullable qilish — yangi qo'shilgan dars sanasi
uchun o'quvchilarni avtomatik "keldi" deb belgilamaslik, balki "belgilanmagan"
holatda saqlash imkonini beradi. Faqat cheklovni bo'shatadi (NOT NULL -> NULL),
mavjud qatorlardagi qiymatlar (True/False) hech qanday o'zgarmaydi.

Bir vaqtning o'zida bu migratsiya ikkita ajralib qolgan "head"ni ham birlashtiradi:
20260728_staff_warnings o'ziga xato ravishda 20260714_feedback_status'dan
tarmoqlangan edi (aslida o'sha paytdagi haqiqiy head 20260724_merge bo'lishi
kerak edi) — shu sabab ikkita mustaqil head paydo bo'lgan. Merge hech qanday
ma'lumotni o'zgartirmaydi, faqat ikki tarmoqni bitta zanjirga qaytaradi.

Revision ID: 20260805_attendance_nullable
Revises: 20260724_merge, 20260728_staff_warnings
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = '20260805_attendance_nullable'
down_revision = ('20260724_merge', '20260728_staff_warnings')
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
