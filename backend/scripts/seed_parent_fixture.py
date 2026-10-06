"""Ota-ona mobil API uchun IZOLYATSIYALANGAN test fixture: 1 ota-ona + 2 bola.

Haqiqiy talabalarga tegmaydi — "TEST —" prefiksli soxta talabalar, guruhlar,
jadval, davomat, baho, uy vazifasi, izoh va to'lov yaratadi. Production
bazasida ishga tushirmang (moliya hisobotlariga tushadi): staging/lokal baza.

Credential repoga yozilmaydi — env orqali:
    PARENT_FIXTURE_PHONE=+998900000099 PARENT_FIXTURE_PASSWORD='<kamida-10-belgi>' \\
    python -m backend.scripts.seed_parent_fixture --i-understand-this-is-not-production

Idempotent: shu telefon bilan ota-ona bo'lsa, faqat parolini yangilaydi.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta

from ..database import SessionLocal
from .. import models, tz
from ..security import hash_password

PREFIX = "TEST — "


def main() -> None:
    if "--i-understand-this-is-not-production" not in sys.argv:
        raise SystemExit("Xavfsizlik: --i-understand-this-is-not-production bayrog'i kerak (staging/lokal baza).")
    phone = os.getenv("PARENT_FIXTURE_PHONE", "+998900000099").strip()
    password = os.getenv("PARENT_FIXTURE_PASSWORD", "")
    if len(password) < 10:
        raise SystemExit("PARENT_FIXTURE_PASSWORD env (kamida 10 belgi) berilmagan.")

    db = SessionLocal()
    try:
        parent = db.query(models.Parent).filter(models.Parent.phone == phone).first()
        if parent:
            parent.hashed_password = hash_password(password)
            parent.is_active = True
            db.commit()
            print(f"Mavjud test ota-ona #{parent.id} paroli yangilandi.")
            return

        today = tz.today()
        month_start = datetime(today.year, today.month, 1, 6, 0)
        teacher = db.query(models.User).filter(models.User.username == "test_parent_fixture_teacher").first()
        if not teacher:
            teacher = models.User(username="test_parent_fixture_teacher", full_name=f"{PREFIX}Ustoz",
                                  hashed_password=hash_password(os.urandom(16).hex()), role="teacher",
                                  is_active=False, phone="+998900000098", telegram="@test_teacher")
            db.add(teacher); db.flush()

        g1 = models.Group(name=f"{PREFIX}Frontend", stage="frontend", course_price=450000,
                          teacher_id=teacher.id, lesson_time="14:00", is_active=True)
        g2 = models.Group(name=f"{PREFIX}English", stage="foundation", course_price=300000,
                          teacher_id=teacher.id, schedule="Juft kunlar", lesson_time="10:00", is_active=True)
        db.add_all([g1, g2]); db.flush()
        db.add_all([
            models.ScheduleSlot(group_id=g1.id, day_of_week=d, start_time="14:00", end_time="16:00", room="204")
            for d in (1, 3, 5)
        ])

        a = models.Student(full_name=f"{PREFIX}Alibek", phone1="+998900000097", is_active=True)
        b = models.Student(full_name=f"{PREFIX}Bekzod", phone1="+998900000096", is_active=True)
        db.add_all([a, b]); db.flush()
        db.add_all([
            models.GroupStudent(group_id=g1.id, student_id=a.id, joined_at=month_start),
            models.GroupStudent(group_id=g2.id, student_id=a.id, joined_at=month_start),
            models.GroupStudent(group_id=g2.id, student_id=b.id, joined_at=month_start),
        ])
        for i in range(1, min(today.day, 10) + 1):
            d = date(today.year, today.month, i)
            db.add(models.Attendance(group_id=g1.id, student_id=a.id, lesson_date=d, is_present=i % 3 != 0))
        db.add(models.Payment(student_id=a.id, group_id=g1.id, amount=200000, month=today.month,
                              year=today.year, notes="Fixture: naqd"))
        db.add(models.Grade(student_id=a.id, group_id=g1.id, subject="JavaScript Basics", score=41,
                            max_score=50, exam_date=today))
        hw = models.Homework(group_id=g1.id, lesson_title="Array metodlari", text="Mashqlar",
                             lesson_date=today, due_date=today + timedelta(days=3))
        db.add(hw)
        db.add(models.TeacherFeedback(student_id=a.id, group_id=g1.id, teacher_id=teacher.id,
                                      comment="Fixture izohi: yaxshi o'zlashtiryapti."))

        parent = models.Parent(full_name=f"{PREFIX}Ota-ona", phone=phone, username=phone,
                               hashed_password=hash_password(password), is_active=True)
        db.add(parent); db.flush()
        db.add_all([models.ParentChild(parent_id=parent.id, student_id=a.id),
                    models.ParentChild(parent_id=parent.id, student_id=b.id)])
        db.commit()
        print(f"Test ota-ona #{parent.id} ({phone}) va bolalar #{a.id}, #{b.id} yaratildi.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
