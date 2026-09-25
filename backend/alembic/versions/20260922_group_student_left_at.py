"""group_students.left_at — a'zolik tarixini saqlash (soft-delete).

Muammo: talaba guruhdan chiqarilganda/o'tkazilganda GroupStudent qatori
db.delete() bilan butunlay o'chirilar edi — natijada talabaning o'sha
guruhda bo'lgan davri uchun qarz hisob-kitobi (core_calc.student_cumulative_owed)
va oylik moliya hisoboti (_finance_month) butunlay "unutib qoladi", garchi
o'sha davrdagi to'lovlar Payment jadvalida saqlanib qolgan bo'lsa ham.
Bu haqiqiy production holatda tasdiqlangan (bitta talaba boshqa guruhga
o'tganda uning eski oylik qarzi hisobdan tushib qolgan, "ortiqcha to'lagan"
bo'lib ko'ringan).

Bundan buyon `remove_student_from_group` qatorni o'chirish o'rniga
`left_at`ni belgilaydi — a'zolik tarixi butunlay saqlanadi.

Revision ID: 20260922_group_student_left_at
Revises: 20260922_payment_notes
Create Date: 2026-09-22
"""
import sqlalchemy as sa
from alembic import op

revision = '20260922_group_student_left_at'
down_revision = '20260922_payment_notes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('group_students', sa.Column('left_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('group_students', 'left_at')
