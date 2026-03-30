# LMS To'liq Rivojlantirish Rejasi

## Holat
Yangi sessiya boshlanganda bu faylni o'qib, qayerdan davom etishni bil.

## Maqsad
IT Hub loyihasini to'liq LMS tizimiga aylantirish:
- Teacher: faqat metodika (read-only)
- Metodist: metodika CRUD + talabalar/guruhlar boshqaruvi
- Admin: hamma narsa + daromad + statistika

## Yangi modellar
- Student (ism, telefon1, telefon2?, telegram_id?)
- Group (nom, teacher_id, course_price, schedule, is_active)
- GroupStudent (group_id, student_id, joined_at)
- Payment (student_id, group_id, amount, month, year, paid_at, notes)

## Bajarilgan ishlar
- [x] models.py - Student, Group, GroupStudent, Payment modellari qo'shildi
- [x] schemas.py - barcha schemalar qo'shildi
- [x] main.py - barcha endpointlar qo'shildi
- [x] frontend/src/api.js - yangi API funksiyalar qo'shildi
- [x] frontend/src/App.jsx - routing va navigation
- [x] frontend/src/components/Students.jsx
- [x] frontend/src/components/Groups.jsx
- [x] frontend/src/components/Payments.jsx
- [x] frontend/src/components/Dashboard.jsx (admin only)
- [x] frontend/src/components/Sidebar.jsx - yangilandi
- [x] frontend/src/styles.css - yangi stillar
- [x] alembic migration

## Keyingi qadam (agar token tugasa)
Agar hali bajarilmagan ishlar bo'lsa bu faylda "[ ]" belgisi bilan ko'rinadi.
Claude: LMS_PLAN.md ni o'qi va davom et.
