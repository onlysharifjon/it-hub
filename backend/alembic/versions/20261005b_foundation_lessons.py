"""Foundation darslari — "Minar Digital Creator" 2 oylik Starter dasturi (24 dars).

Faqat hali yo'q dars raqamlari qo'shiladi: metodist kiritgan/tahrirlagan
darslar ustidan yozilmaydi.

Revision ID: 20261005b_foundation_lessons
Revises: 20261005a_student_source
Create Date: 2026-10-05
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = '20261005b_foundation_lessons'
down_revision = '20261005a_student_source'
branch_labels = None
depends_on = None

W1 = "1-hafta — Kompyuter va raqamli savodxonlik"
W2 = "2-hafta — Google Docs + Google Slides"
W3 = "3-hafta — Google Sheets + Forms + Sites"
W4 = "4-hafta — Canva"
W5 = "5-hafta — Figma"
W6 = "6-hafta — Scratch asoslari"
W7 = "7-hafta — Scratch + kreativ loyihalar"
W8 = "8-hafta — Final Project"

COURSE_NOTES = """MINAR DIGITAL CREATOR — 2 oylik Starter kursi
9–17 yoshdagi bolalar uchun kompyuter savodxonligi, Google vositalari, dizayn va kreativ dasturlash dasturi.

Asosiy g'oya: texnologiyadan shunchaki foydalanishni emas, texnologiya yordamida yaratishni o'rganish.
Davomiyligi: 8 hafta • haftasiga 3 dars • jami 24 dars • har bir dars 60 daqiqa.
Yakuniy natija: 10+ mini loyiha + 1 ta final loyiha + Portfolio + Demo Day + Certificate.

Kurs falsafasi: 20% nazariya + 80% amaliyot.
Har bir dars o'quvchini tayyor bilim bilan emas, tayyor mahsulot bilan chiqarishi kerak.
Asosiy savol: "Bugun nimani o'rgandim?" emas, "Bugun nimani yaratdim?"

Kurs yakunida o'quvchi:
- kompyuterda fayl va papkalar bilan ishlay oladi;
- internetdan ma'lumotni to'g'ri qidiradi;
- xavfsiz parol va internet qoidalarini biladi;
- Google Drive'da fayllarni tartiblaydi;
- Google Docs'da professional hujjat tayyorlaydi;
- Google Slides'da prezentatsiya yaratadi;
- Google Sheets'da oddiy jadvallar tuzadi;
- Google Forms orqali test va so'rovnoma yaratadi;
- Canva'da poster, banner va boshqa dizaynlar yaratadi;
- Figma'da interfeys va prototiplar yaratadi;
- Scratch'da animatsiya va o'yinlar yaratadi;
- oddiy video montaj qila oladi;
- Google Sites'da sodda web-sayt yaratadi;
- o'z ishlarini portfolio ko'rinishida yig'a oladi;
- o'z loyihasini auditoriya oldida taqdim qila oladi.

Asosiy platformalar:
- Google: Drive, Docs, Slides, Sheets, Forms, Sites
- Design: Canva, Figma
- Coding: Scratch
- Content: Canva Video, oddiy video editing
- Internet: Google Chrome, Internet Safety

Mini loyiha g'oyalari: Personal Folder System, My Profile Document, Expense Tracker, Simple Chart, Online Quiz, Personal Website, Poster, Mobile App Design, Scratch Game, Interactive Story, Short Video, Creative Presentation.

24 dars → 10+ mini loyiha → 1 ta katta final loyiha → Portfolio → Demo Day → Certificate
"Foydalanma — yarat." """

SAFETY_NOTES = """Raqamli xavfsizlik va internet madaniyati — o'quvchilar quyidagilarni o'rganadi:
- kuchli parol yaratish;
- shaxsiy ma'lumotlarni himoya qilish;
- phishing nima ekanini tushunish;
- noma'lum linklarni ochmaslik;
- internetdagi yolg'on ma'lumotlarni ajratish;
- ijtimoiy tarmoqlarda xavfsiz ishlash;
- boshqa insonlarning rasmi va ma'lumotidan ruxsatsiz foydalanmaslik;
- internetda madaniyatli muloqot qilish.

Asosiy prinsip: "Internetdagi hamma narsa ham xavfsiz va rost emas." """

FINAL_FORMAT = """Final Project formati:
1. G'oya — Men nima yaratmoqchiman?
2. Dizayn — Loyiham qanday ko'rinadi?
3. Yaratish — Qaysi dastur yoki platformadan foydalanaman?
4. Test — Ishlayaptimi? Xatolar bormi?
5. Demo — Loyihamni boshqalarga ko'rsataman."""

# (raqam, bo'lim, sarlavha, qo'llanma, uyga vazifa / loyiha, eslatma)
LESSONS = [
    (1, W1, "Kompyuter bilan tanishuv",
     "Ishlatiladigan vosita: Windows / macOS / Linux.\n\n"
     "Kompyuter qismlari, desktop, dasturlar, fayl va papkalar tushunchasi. "
     "Fayl yaratish, nomlash, saqlash va o'chirish.",
     "Amaliy loyiha: \"Men haqimda\" nomli papka yaratish va uning ichiga tartibli fayllar joylashtirish.",
     COURSE_NOTES),
    (2, W1, "Internet va xavfsiz qidiruv",
     "Ishlatiladigan vosita: Google Chrome.\n\n"
     "Qidiruv tizimidan foydalanish, to'g'ri kalit so'z tanlash, foydali va zararli saytlarni ajratish.",
     "Amaliy loyiha: berilgan mavzu bo'yicha 5 ta ishonchli ma'lumot topish.",
     SAFETY_NOTES),
    (3, W1, "Google Account, Google Drive va Gmail",
     "Ishlatiladigan vosita: Google Drive.\n\n"
     "Google account, Gmail, Drive, fayl yuklash, papkalar yaratish, fayllarni tartiblash va ulashish.",
     "Uyga vazifa: shaxsiy \"My Portfolio\" papkasini yaratish.",
     None),
    (4, W2, "Google Docs asoslari",
     "Matn yozish, shrift, rang, alignment, heading, ro'yxatlar, rasmlar qo'shish.",
     "Mini loyiha: \"Mening sevimli mashg'ulotim\" nomli 1 sahifalik hujjat.",
     None),
    (5, W2, "Professional hujjat yaratish",
     "Sarlavha, jadval, rasm, sahifa dizayni va tartibli hujjat yaratish.",
     "Mini loyiha: \"Mening bir kunim\" mini jurnalini yaratish.",
     None),
    (6, W2, "Google Slides",
     "Slayd yaratish, dizayn, rasm, ikonka, matn va animatsiyalar.",
     "Mini loyiha: \"Men sevgan kasb\" mavzusida 5 slaydli prezentatsiya.",
     None),
    (7, W3, "Google Sheets",
     "Kataklar, ustunlar, qatorlar, jadval tuzish, ma'lumot kiritish.",
     "Mini loyiha: \"Haftalik rejam\" jadvalini yaratish.",
     None),
    (8, W3, "Formula va diagrammalar",
     "SUM, AVERAGE kabi oddiy formulalar, ma'lumotlarni tartiblash va diagramma yaratish.",
     "Mini loyiha: \"Haftalik xarajatlar\" jadvali va diagrammasi.",
     None),
    (9, W3, "Google Forms + Google Sites",
     "Google Forms orqali test va so'rovnoma yaratish. Google Sites yordamida oddiy web-sahifa yaratish.",
     "Mini loyiha: \"Mening sinfim\" yoki \"Mening qiziqishlarim\" mini sayti.",
     None),
    (10, W4, "Canva bilan tanishuv",
     "Template, text, element, image, background va layout.",
     "Mini loyiha: motivatsion poster yaratish.",
     None),
    (11, W4, "Poster va banner dizayni",
     "Ranglar uyg'unligi, shriftlar va kompozitsiya.",
     "Mini loyiha: o'quv markazi yoki maktab tadbiri uchun reklama posterini yaratish.",
     None),
    (12, W4, "Canva Presentation + Video",
     "Canva'da prezentatsiya, oddiy video, transition, audio va animatsiya.",
     "Mini loyiha: 30–60 soniyalik kreativ video yaratish.",
     None),
    (13, W5, "Figma bilan tanishuv",
     "Frame, shape, text, color, layers va basic tools.",
     "Mini loyiha: mobil ilovaning oddiy ekranini yaratish.",
     None),
    (14, W5, "UI Design",
     "Button, icon, card, navigation va layout tushunchalari.",
     "Mini loyiha: \"O'quv ilovasi\" interfeysini yaratish.",
     None),
    (15, W5, "Prototype",
     "Bir nechta ekran yaratish va ularni o'zaro bog'lash.",
     "Mini loyiha: 3–4 ekranli mobil ilova prototipi.",
     None),
    (16, W6, "Scratch bilan dasturlash",
     "Sprite, Stage, Motion va Events.",
     "Mini loyiha: harakatlanadigan qahramon yaratish.",
     None),
    (17, W6, "Shartlar va o'zgaruvchilar",
     "If, variable, score va interaction.",
     "Mini loyiha: oddiy ball yig'ish o'yini.",
     None),
    (18, W6, "Scratch Game",
     "Collision, score, timer va game over.",
     "Mini loyiha: to'siqlardan qochish mini-o'yini.",
     None),
    (19, W7, "Interactive Story",
     "Dialoglar, sahnalar va animatsiyalar.",
     "Mini loyiha: interaktiv hikoya yaratish.",
     None),
    (20, W7, "Scratch Game Development",
     "Darajalar, ball, ovoz va bonuslar.",
     "Mini loyiha: 2 bosqichli mini game.",
     None),
    (21, W7, "Kreativ Challenge",
     "O'quvchi mustaqil ravishda berilgan vazifa asosida loyiha yaratadi.",
     "Challenge: \"30 daqiqada o'z o'yiningni yarat!\"",
     None),
    (22, W8, "Final Project: G'oya va reja",
     "O'quvchi o'z loyihasini tanlaydi. Variantlar:\n"
     "- 🎮 Scratch Game\n"
     "- 🎨 Canva Design Portfolio\n"
     "- 📱 Figma App Prototype\n"
     "- 🌐 Google Sites Website\n"
     "- 📊 Google Sheets Dashboard\n"
     "- 📚 Interactive Presentation\n"
     "- 🎬 Kreativ Video",
     "Tanlangan loyiha g'oyasi va rejasini tayyorlash.",
     FINAL_FORMAT),
    (23, W8, "Final Project Development",
     "O'quvchi loyihasini yakunlaydi.\n\n"
     "O'qituvchi:\n"
     "- dizaynni tekshiradi;\n"
     "- xatolarni tuzatishga yordam beradi;\n"
     "- loyiha taqdimotini tayyorlashga yo'naltiradi.",
     "Loyihani yakunlash va Demo Day taqdimotiga tayyorlanish.",
     FINAL_FORMAT),
    (24, W8, "DEMO DAY",
     "Har bir o'quvchi o'z loyihasini namoyish qiladi.\n\n"
     "Taqdimot formati:\n"
     "1. Men qanday muammo yoki g'oyani tanladim?\n"
     "2. Mening loyiham nima qiladi?\n"
     "3. Qaysi dasturlardan foydalandim?\n"
     "4. Loyihamni namoyish qilaman.\n"
     "5. Keyingi versiyada nimani qo'shaman?",
     "Yakunida: Certificate + Portfolio + Demo Day.",
     "Kurs yakunida o'quvchi Google servislaridan foydalana oladigan, Canva va Figma'da dizayn qila "
     "oladigan, Scratch'da dasturlashning boshlang'ich mantiqini tushunadigan va o'zining birinchi "
     "raqamli loyihalarini yarata oladigan darajaga chiqadi.\n\n\"Foydalanma — yarat.\""),
]

lessons = sa.table(
    'lessons',
    sa.column('category', sa.String), sa.column('lesson_number', sa.Integer),
    sa.column('title', sa.String), sa.column('section', sa.Text), sa.column('guide', sa.Text),
    sa.column('homework', sa.Text), sa.column('extra_notes', sa.Text), sa.column('updated_at', sa.DateTime),
)


def upgrade() -> None:
    conn = op.get_bind()
    existing = {r[0] for r in conn.execute(
        sa.text("SELECT lesson_number FROM lessons WHERE category = 'foundation'"))}
    now = datetime.utcnow()
    rows = [
        dict(category='foundation', lesson_number=n, title=t, section=s, guide=g,
             homework=h, extra_notes=e, updated_at=now)
        for n, s, t, g, h, e in LESSONS if n not in existing
    ]
    if rows:
        op.bulk_insert(lessons, rows)


def downgrade() -> None:
    pass
