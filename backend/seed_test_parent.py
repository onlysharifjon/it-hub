"""TEST ota-ona akkaunti — mobil ilova jonli API'da sinash uchun.

Idempotent (qayta ishga tushirish xavfsiz). Eng boy ma'lumotli faol talabani
tanlaydi, unga +998901234567 / Test1234 ota-onani bog'laydi va jadval bo'sh
bo'lmasligi uchun guruhga slot qo'shadi.

Ishga tushirish:
    /var/www/it-hub/.venv/bin/python -m backend.seed_test_parent
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import extract, func

from .database import SessionLocal
from . import models
from .security import hash_password

TEST_PHONE = "+998901234567"
TEST_PASSWORD = "Test1234"
TEST_FULL_NAME = "Nodira Mominova"
TEST_DISPLAY_NAME = "Nodira opa"


def _pick_richest_student(db, month: int, year: int):
    """Faol, guruhi bor talabalar orasidan (to'lov+davomat) bo'yicha eng boyini."""
    students = (
        db.query(models.Student)
        .filter(models.Student.is_active.is_(True), models.Student.is_archived.is_(False))
        .all()
    )
    best, best_score = None, -1
    for s in students:
        active_groups = [m for m in s.group_memberships if m.group and m.group.is_active]
        if not active_groups:
            continue
        pays = (
            db.query(func.count(models.Payment.id))
            .filter(models.Payment.student_id == s.id,
                    models.Payment.month == month, models.Payment.year == year)
            .scalar()
        )
        att = (
            db.query(func.count(models.Attendance.id))
            .filter(models.Attendance.student_id == s.id,
                    extract("month", models.Attendance.lesson_date) == month,
                    extract("year", models.Attendance.lesson_date) == year)
            .scalar()
        )
        score = len(active_groups) + pays * 2 + att
        if score > best_score:
            best, best_score = s, score
    return best


def _ensure_schedule(db, group):
    """Guruhda strukturaviy jadval bo'lmasa — 'Juft kunlar' (Se/Pay/Sha) qo'shadi."""
    has = db.query(models.ScheduleSlot).filter(models.ScheduleSlot.group_id == group.id).count()
    if has:
        return 0
    added = 0
    for day in (2, 4, 6):   # Seshanba, Payshanba, Shanba
        db.add(models.ScheduleSlot(
            group_id=group.id, day_of_week=day, start_time="15:00", end_time="16:30",
            room="1-xona", created_at=datetime.utcnow(),
        ))
        added += 1
    return added


def _ensure_academic_demo(db, student, group, now):
    """Yangi akademik endpointlar uchun demo ma'lumot (idempotent)."""
    added = []

    # O'qituvchi kontaktlari (bo'sh bo'lsa)
    teacher = group.teacher if group else None
    if teacher and not teacher.phone:
        teacher.phone = "+998935551122"
        teacher.telegram = "@minar_teacher"
        added.append("o'qituvchi kontaktlari")

    # Baholar
    if not db.query(models.Grade).filter(models.Grade.student_id == student.id).count():
        for i, (subj, score, etype) in enumerate([
            ("HTML & CSS asoslari", 92, "exam"),
            ("JavaScript Basics", 85, "test"),
            ("Flexbox Layout", 78, "quiz"),
        ]):
            db.add(models.Grade(
                student_id=student.id, group_id=group.id if group else None,
                subject=subj, score=score, max_score=100, exam_type=etype,
                exam_date=(now - timedelta(days=7 * (i + 1))).date(),
                created_by_id=teacher.id if teacher else None, created_at=now,
            ))
        added.append("3 ta baho")

    # Uy vazifalari + holatlar
    if group and not db.query(models.Homework).filter(models.Homework.group_id == group.id).count():
        hw_specs = [
            ("Todo App", "Todo ilova yasang: qo'shish, o'chirish, belgilash.", 2, "graded", 90),
            ("Landing sahifa", "Flexbox bilan landing sahifa yasab keling.", 0, "submitted", None),
            ("Kalkulyator", "Oddiy kalkulyator (+ - * /).", -2, "pending", None),
        ]
        for title, text, days_ago, status, hw_grade in hw_specs:
            hw = models.Homework(
                group_id=group.id, lesson_title=title, text=text,
                lesson_date=(now - timedelta(days=days_ago + 2)).date(),
                due_date=(now - timedelta(days=days_ago)).date(),
                created_by_id=teacher.id if teacher else None, created_at=now,
            )
            db.add(hw)
            db.flush()
            if status != "pending":
                db.add(models.HomeworkSubmission(
                    homework_id=hw.id, student_id=student.id, status=status,
                    grade=hw_grade, submitted_at=now - timedelta(days=max(days_ago, 0)),
                    teacher_comment="Yaxshi bajarilgan" if status == "graded" else None,
                    created_at=now,
                ))
        added.append("3 ta uy vazifasi")

    # O'qituvchi izohlari
    if not db.query(models.TeacherFeedback).filter(models.TeacherFeedback.student_id == student.id).count():
        for days, comment in [
            (3, "Darslarni yaxshi o'zlashtiryapti, faol qatnashadi."),
            (14, "Uy vazifalarini o'z vaqtida topshiradi. Amaliyotga ko'proq e'tibor bersin."),
        ]:
            db.add(models.TeacherFeedback(
                student_id=student.id, group_id=group.id if group else None,
                teacher_id=teacher.id if teacher else None,
                comment=comment, created_at=now - timedelta(days=days),
            ))
        added.append("2 ta izoh")

    # Sertifikat
    if not db.query(models.Certificate).filter(models.Certificate.student_id == student.id).count():
        db.add(models.Certificate(
            student_id=student.id, title="Foundation kursi sertifikati",
            file_url="https://minaracademy.uz/certificates/demo-foundation.pdf",
            issued_at=(now - timedelta(days=30)).date(), created_at=now,
        ))
        added.append("1 ta sertifikat")

    # Tadbirlar (umumiy)
    if not db.query(models.Event).count():
        db.add(models.Event(
            title="Ochiq eshiklar kuni",
            description="Ota-onalar uchun akademiya bilan tanishuv va o'qituvchilar bilan uchrashuv.",
            event_date=now + timedelta(days=10), location="Minar Academy, asosiy bino",
            is_active=True, created_at=now,
        ))
        db.add(models.Event(
            title="Demo Day — bitiruvchilar loyihalari",
            description="Talabalar o'z loyihalarini taqdim etadi.",
            event_date=now + timedelta(days=24), location="Minar Academy, katta zal",
            is_active=True, created_at=now,
        ))
        added.append("2 ta tadbir")

    return added


def main():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        student = _pick_richest_student(db, now.month, now.year)
        if not student:
            print("XATO: mos talaba topilmadi (faol + guruhli talaba yo'q).")
            return
        group = next((m.group for m in student.group_memberships if m.group and m.group.is_active), None)

        slots_added = _ensure_schedule(db, group) if group else 0

        # Ota-ona: mavjud bo'lsa parolni tiklaymiz, bo'lmasa yaratamiz (ORM, raw SQL emas)
        parent = db.query(models.Parent).filter(models.Parent.phone == TEST_PHONE).first()
        if parent:
            parent.hashed_password = hash_password(TEST_PASSWORD)
            parent.full_name = TEST_FULL_NAME
            parent.display_name = TEST_DISPLAY_NAME
            parent.is_active = True
            # eski refresh tokenlarni bekor qilamiz
            db.query(models.ParentRefreshToken).filter(
                models.ParentRefreshToken.parent_id == parent.id,
                models.ParentRefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": now})
            action = "yangilandi (parol tiklandi)"
        else:
            parent = models.Parent(
                full_name=TEST_FULL_NAME, display_name=TEST_DISPLAY_NAME,
                phone=TEST_PHONE, username=TEST_PHONE,
                hashed_password=hash_password(TEST_PASSWORD),
                is_active=True, created_at=now,
            )
            db.add(parent)
            db.flush()
            action = "yaratildi"

        # Talabani bog'laymiz (dublikatsiz)
        link = db.query(models.ParentChild).filter(
            models.ParentChild.parent_id == parent.id,
            models.ParentChild.student_id == student.id,
        ).first()
        if not link:
            db.add(models.ParentChild(parent_id=parent.id, student_id=student.id, created_at=now))

        demo_added = _ensure_academic_demo(db, student, group, now)

        db.commit()

        print("─" * 60)
        print(f"✓ TEST ota-ona {action}")
        print(f"  Login (username): {TEST_PHONE}")
        print(f"  Parol:            {TEST_PASSWORD}")
        print(f"  Bola:             #{student.id} — {student.full_name}")
        print(f"  Guruh:            {group.name if group else '—'}")
        sched_msg = f"qo'shildi ({slots_added} ta)" if slots_added else "allaqachon bor"
        print(f"  Jadval slotlari:  {sched_msg}")
        demo_msg = ", ".join(demo_added) if demo_added else "allaqachon bor"
        print(f"  Akademik demo:    {demo_msg}")
        print("─" * 60)
        return student.id
    finally:
        db.close()


if __name__ == "__main__":
    main()
