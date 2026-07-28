"""staff_warnings + discipline_codes — audit xodimlarga ogohlantirish/jarima berish
tizimi (endi botdan CRM'ga ko'chiriladi). Faqat qo'shimcha (additive): ikkita yangi
jadval yaratiladi va mavjud `users` jadvaliga bitta yangi, bo'sh (nullable) ustun
qo'shiladi — mavjud jadvallar/qatorlar hech qanday tarzda o'zgartirilmaydi yoki
o'chirilmaydi.

Revision ID: 20260728_staff_warnings
Revises: 20260714_feedback_status
Create Date: 2026-07-28
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = '20260728_staff_warnings'
down_revision = '20260714_feedback_status'
branch_labels = None
depends_on = None


# Botning bot/main.py'dagi DISCIPLINE_CODE_TEMPLATES bilan bir xil — (kod, daraja,
# qisqa nom, to'liq matn). Bir martalik urug'lash uchun, yangi jadvalga.
DISCIPLINE_CODES = [
    ("1.1", "gray", "1.1 Bedjik taqmaslik", "Korxona hududida doimo bedjik taqilgan holda bo'lish."),
    ("1.2", "gray", "1.2 Mijozga sovuqqonlik", "Mijozlar bilan doimo kulib, hushmuomilalikda gaplashish."),
    ("1.3", "gray", "1.3 Stolda begona buyum", "Administratsiya stoli ustida ortiqcha buyumlar, shaxsiy buyumlar, shaxsiy telefon, qog'ozlar, hujjatlar turishi taqiqlanadi."),
    ("1.4", "gray", "1.4 Stolga bosh qo'yish", "Administratsiya stoliga bosh qo'yib yotish taqiqlanadi."),
    ("1.5", "gray", "1.5 Idishsiz ichimlik", "Korxona hududida rangli ichimliklarni faqat shaxsiy kружка (finjon) ga solgan holda ichish talab etiladi."),
    ("1.6", "gray", "1.6 Kelmaganga bog'lanmaslik", "Darsga kelmagan o'quvchilar bilan bog'lanib ertangi kun soat 12:00 gacha kelmaganlik sababini aniqlash, kelasi darsga chaqirish hamda izohlarda kelmaganlik sababini kiritib o'tish talab etiladi."),
    ("1.7", "gray", "1.7 Hisobot to'ldirmaslik", "Filial kesmidagi hisobotlarni belgilangan vaqt ichida to'g'ri va to'liq to'ldirish talab etiladi."),
    ("1.8", "gray", "1.8 Muzlaganga bog'lanmaslik", "Muzlatilgan o'quvchilar bilan kelishi kerak bo'lgan sanada bog'lanish, darsga chaqirish hamda izohlarni yangilash talab etiladi."),
    ("2.1", "yellow", "2.1 Check-in/out qilmaslik", "Verefixdan to'g'ri va belgilangan tartibda foydalanish. Ishga kelgan vaqtda va ketayotganda o'z vaqtida check-in va check-out qilish talab etiladi."),
    ("2.2", "yellow", "2.2 Kiyinish tartibi buzilishi", "Kiyinish uslubi va tashqi ko'rinish talablariga rioya qilmaslik (erkaklar/ayollar uchun belgilangan klassik uslub, taqiqlangan kiyimlar)."),
    ("2.3", "yellow", "2.3 Ish vaqtida telefon", "Ish vaqtida shaxsiy telefondan foydalanish taqiqlanadi."),
    ("2.4", "yellow", "2.4 Ijtimoiy tarmoq", "Ish kompyuteridan ishga aloqador bo'lmagan ijtimoiy tarmoqlarga kirish taqiqlanadi."),
    ("2.5", "yellow", "2.5 Shaxsiy ish bilan band", "Ish vaqtida shaxsiy ishlar bilan shug'ullanish taqiqlanadi."),
    ("2.6", "yellow", "2.6 Kassaga sababsiz o'tish", "Kassa hududiga besabab o'tish taqiqlanadi."),
    ("2.7", "yellow", "2.7 O'tirib konsultatsiya", "Mijozlarga turgan holda konsultatsiya berish talab etiladi."),
    ("2.8", "yellow", "2.8 Tushlikda kech qolish", "Tushlikda ajratilgan vaqtdan ko'p qolib ketish, ajratilgan vaqtda emas boshqa vaqtda tushlik qilish taqiqlanadi."),
    ("2.9", "yellow", "2.9 20 daq gacha kechikish", "Korxonaga o'z vaqtida kelish (20 daqiqagacha kechikish)."),
    ("2.10", "yellow", "2.10 Ish joyini tark etish", "Ish joyini sababsiz tark etish taqiqlanadi (20 daqiqa va undan ko'p)."),
    ("2.11", "yellow", "2.11 Bedjiksiz (2-marta)", "Korxona hududida doimo bedjik taqilgan holda bo'lish — kun davomida 2-marotaba buzilgan holat."),
    ("3.1", "red", "3.1 Ovqatlanish (ma'muriyat)", "Administratsiya hududida ovqatlanish, yegulik yeyish taqiqlanadi."),
    ("3.2", "red", "3.2 Pardoz/soch tarash", "Administratsiya hududida pardoz qilish va soch tarash, stol ustida pardoz vositalarini turishi taqiqlanadi."),
    ("3.3", "red", "3.3 Mijozga qo'pol gapirish", "Mijozlar bilan baland ovozda va qo'pol ohangda gaplashish taqiqlanadi."),
    ("3.4", "red", "3.4 Baland ovozda gaplashish", "Jamoa a'zolari va hamkasblar bilan coworking hududi, administratsiya hududi va dars xonalarida baland ovozda ishdan tashqari mavzuda gaplashish taqiqlanadi."),
    ("3.5", "red", "3.5 Musiqa tinglash", "Administratsiya hududida musiqa tinglash taqiqlanadi."),
    ("3.6", "red", "3.6 3+ soat ish joyida yo'q", "Sababsiz va ogohlantirishsiz ish vaqtida 3 soat va undan ko'p ish joyida bo'lmaslik."),
    ("3.7", "red", "3.7 21+ daq kechikish", "Korxonaga o'z vaqtida kelish (21 daqiqa va undan ko'p kechikish)."),
    ("3.8", "red", "3.8 Ogohlantirmay kelmaslik", "Eng kamida 1 kun avval ogohlantirmasdan, ruxsat so'ramasdan ishga kelmaslik."),
    ("3.9", "red", "3.9 Ruxsatsiz ketish", "Ruxsat so'ramasdan, ogohlantirishsiz ish vaqtida korxonadan ketish taqiqlanadi."),
]


def upgrade() -> None:
    # Mavjud `users` jadvaliga faqat yangi, bo'sh (nullable) ustun — hech bir mavjud
    # qatorga ta'sir qilmaydi, default qiymat yozilmaydi.
    op.add_column('users', sa.Column('telegram_chat_id', sa.String(50), nullable=True))

    op.create_table(
        'discipline_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(16), nullable=False, unique=True),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('short_name', sa.String(64), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_discipline_codes_code', 'discipline_codes', ['code'])

    op.create_table(
        'staff_warnings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('issued_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('discipline_code_id', sa.Integer(), sa.ForeignKey('discipline_codes.id'), nullable=True),
        sa.Column('code', sa.String(16), nullable=True),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('photo_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.Column('notify_error', sa.Text(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_index('ix_staff_warnings_staff_id', 'staff_warnings', ['staff_id'])
    op.create_index('ix_staff_warnings_issued_by_id', 'staff_warnings', ['issued_by_id'])
    op.create_index('ix_staff_warnings_created_at', 'staff_warnings', ['created_at'])

    # Bob-band kodeksini bir martalik urug'lash — yangi jadval, mavjud ma'lumotga
    # hech qanday aloqasi yo'q.
    discipline_codes_table = sa.table(
        'discipline_codes',
        sa.column('code', sa.String),
        sa.column('severity', sa.String),
        sa.column('short_name', sa.String),
        sa.column('text', sa.Text),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime),
    )
    now = datetime.utcnow()
    op.bulk_insert(
        discipline_codes_table,
        [
            {
                'code': code,
                'severity': severity,
                'short_name': short_name,
                'text': text,
                'is_active': True,
                'created_at': now,
            }
            for code, severity, short_name, text in DISCIPLINE_CODES
        ],
    )


def downgrade() -> None:
    op.drop_index('ix_staff_warnings_created_at', table_name='staff_warnings')
    op.drop_index('ix_staff_warnings_issued_by_id', table_name='staff_warnings')
    op.drop_index('ix_staff_warnings_staff_id', table_name='staff_warnings')
    op.drop_table('staff_warnings')
    op.drop_index('ix_discipline_codes_code', table_name='discipline_codes')
    op.drop_table('discipline_codes')
    op.drop_column('users', 'telegram_chat_id')
