"""App Store review akkaunti uchun XAYOLIY ma'lumot: 1 o'quvchi, 1 guruh (oyiga 700 000 so'm, joriy oy to'lanmagan),
jadval, davomat, baho, uy vazifasi, o'qituvchi (oylikdan ozod) izohi, bildirishnoma. Haqiqiy shaxslarga tegmaydi
("TEST — App Review" prefiksi).

Review raqami bilan kirilganda (parol yoki OTP) avtomatik chaqiriladi: farzandi yo'q review ota-onasiga
xayoliy o'quvchi biriktiriladi. Akkaunt o'chirilib, qayta kirilsa — o'sha xayoliy o'quvchi qayta biriktiriladi
(o'quvchining akademik yozuvlari o'chirilmaydi). Qo'lda:
    docker exec minar-crm-api-1 python -m backend.scripts.seed_review_account

To'lov yozuvi yaratmaydi — qarz faqat tasdiqlangan Payme callback'i bilan yopiladi.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import models, tz
from ..phone_utils import normalize_phone
from ..security import hash_password

PREFIX = "TEST — App Review "
STUDENT_NAME = f"{PREFIX}Farzand"
MONTHLY_FEE = 700_000


def _create_student(db: Session, phone: str) -> models.Student:
    today = tz.today()
    month_start = today.replace(day=1)
    joined = datetime(month_start.year, month_start.month, 1, 6, 0)     # UTC 06:00 = Toshkent 11:00, joriy oy
    # Faol (ilovada o'qituvchi kontakti ko'rinsin), lekin oylikdan ozod va paroli noma'lum — CRM'ga kira olmaydi.
    teacher = models.User(username=f"app_review_teacher_{secrets.token_hex(3)}", full_name=f"{PREFIX}Ustoz",
                          hashed_password=hash_password(secrets.token_urlsafe(32)), role="teacher",
                          is_active=True, salary_exempt=True, telegram="@minaracademy")
    db.add(teacher); db.flush()
    g = models.Group(name=f"{PREFIX}Frontend", stage="frontend", course_price=MONTHLY_FEE,
                     teacher_id=teacher.id, lesson_time="14:00", is_active=True, created_at=joined)
    db.add(g); db.flush()
    db.add_all([models.ScheduleSlot(group_id=g.id, day_of_week=d, start_time="14:00", end_time="16:00", room="101")
                for d in (1, 3, 5)])
    s = models.Student(full_name=STUDENT_NAME, phone1=phone, is_active=True, created_at=joined)
    db.add(s); db.flush()
    db.add(models.GroupStudent(group_id=g.id, student_id=s.id, joined_at=joined))
    d, n = month_start, 0
    while d < today:
        if d.isoweekday() in (1, 3, 5):
            db.add(models.Attendance(group_id=g.id, student_id=s.id, lesson_date=d, is_present=n % 5 != 4))
            n += 1
        d += timedelta(days=1)
    db.add_all([
        models.Grade(student_id=s.id, group_id=g.id, subject="HTML asoslari", score=45, max_score=50,
                     exam_type="exam", exam_date=month_start),
        models.Grade(student_id=s.id, group_id=g.id, subject="CSS Flexbox", score=38, max_score=50,
                     exam_type="exam", exam_date=max(month_start, today - timedelta(days=1))),
        models.Homework(group_id=g.id, lesson_title="Shaxsiy sahifa", text="HTML'da shaxsiy sahifa yarating",
                        lesson_date=today, due_date=today + timedelta(days=3)),
        models.Homework(group_id=g.id, lesson_title="Flexbox mashqlari", text="5 ta layout",
                        lesson_date=month_start, due_date=month_start + timedelta(days=2)),
        models.TeacherFeedback(student_id=s.id, group_id=g.id, teacher_id=teacher.id,
                               comment="Darslarda faol, uy vazifalarini vaqtida topshiradi."),
    ])
    return s


def ensure_review_children(db: Session, parent: models.Parent) -> bool:
    """Review ota-onasida faqat xayoliy o'quvchi bo'lishini ta'minlaydi (commit chaqiruvchida).
    Haqiqiy o'quvchilar bilan bog'lanish uziladi (o'quvchi yozuvlariga tegilmaydi). True — o'zgarish bo'ldi."""
    links = db.query(models.ParentChild).filter_by(parent_id=parent.id).all()
    real = [l for l in links if not (l.student and l.student.full_name == STUDENT_NAME)]
    for l in real:
        db.delete(l)
    if len(real) < len(links):
        if real:
            db.flush()
        return bool(real)
    s = (db.query(models.Student).filter(models.Student.full_name == STUDENT_NAME)
         .order_by(models.Student.id).first()) or _create_student(db, parent.phone)
    if not (parent.full_name or "").startswith(PREFIX):
        parent.full_name, parent.display_name = f"{PREFIX}Ota-ona", "Test Ota-ona"
    db.add(models.ParentChild(parent_id=parent.id, student_id=s.id))
    db.add(models.ParentNotification(
        parent_id=parent.id, student_id=s.id, type="payment", title="To'lov eslatmasi",
        body=f"{tz.today():%m.%Y} uchun 700 000 so'm to'lov kutilmoqda.", created_at=datetime.utcnow()))
    db.flush()
    return True


def seed(db: Session, phone: str) -> str:
    key = normalize_phone(phone)
    existing = [p for p in db.query(models.Parent).filter(models.Parent.phone.like(f"%{key[-2:]}")).all()
                if normalize_phone(p.phone) == key or normalize_phone(p.username) == key]
    if len(existing) > 1:
        return f"EXISTS parents={[p.id for p in existing]} — o'zgartirilmadi"
    parent = existing[0] if existing else None
    if parent is None:
        parent = models.Parent(phone=phone, username=phone, full_name=f"{PREFIX}Ota-ona", is_active=True,
                               hashed_password=hash_password(secrets.token_urlsafe(32)))
        db.add(parent); db.flush()
    if not ensure_review_children(db, parent):
        return f"EXISTS parent #{parent.id} — farzand bor, o'zgartirilmadi"
    db.commit()
    return f"CREATED parent #{parent.id}"


def main() -> None:
    from ..database import SessionLocal
    from ..parent.phone_auth.service import review_phone
    phone = review_phone()
    if not phone:
        raise SystemExit("PARENT_REVIEW_PHONE / PARENT_REVIEW_OTP env berilmagan.")
    db = SessionLocal()
    try:
        print(seed(db, phone))
    finally:
        db.close()


if __name__ == "__main__":
    main()
