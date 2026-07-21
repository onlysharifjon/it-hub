"""Demo ota-ona oilasini yaratadi (mobil ilova mock ma'lumotiga mos).

Ishga tushirish:  .venv/bin/python -m backend.seed_parents
Idempotent — qayta ishga tushirish xavfsiz. Barcha yozuvlar "DEMO" bilan belgilangan.
"""
from __future__ import annotations

from datetime import datetime

from .database import SessionLocal
from . import models
from .security import hash_password

DEMO_PARENT_PHONE = "+998901234567"
DEMO_PARENT_PASSWORD = "parent123"


def _get_or_create_group(db, name, stage, price):
    g = db.query(models.Group).filter(models.Group.name == name).first()
    if g:
        return g
    g = models.Group(name=name, stage=stage, course_price=price, is_active=True, created_at=datetime.utcnow())
    db.add(g); db.flush()
    return g


def _get_or_create_student(db, name, phone, advance=0):
    s = db.query(models.Student).filter(models.Student.phone1 == phone).first()
    if s:
        return s
    s = models.Student(full_name=name, phone1=phone, advance_balance=advance,
                       is_active=True, created_at=datetime.utcnow())
    db.add(s); db.flush()
    return s


def _enroll(db, group, student):
    ex = db.query(models.GroupStudent).filter_by(group_id=group.id, student_id=student.id).first()
    if not ex:
        db.add(models.GroupStudent(group_id=group.id, student_id=student.id, joined_at=datetime.utcnow()))


def _slot(db, group, day, start, end, room=None):
    ex = db.query(models.ScheduleSlot).filter_by(group_id=group.id, day_of_week=day, start_time=start).first()
    if not ex:
        db.add(models.ScheduleSlot(group_id=group.id, day_of_week=day, start_time=start,
                                   end_time=end, room=room, created_at=datetime.utcnow()))


def main():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Guruh + jadval
        g = _get_or_create_group(db, "DEMO Frontend G-101", "frontend", 450000)
        db.flush()
        _slot(db, g, 1, "14:00", "16:00", "3-xona")   # Dushanba
        _slot(db, g, 3, "14:00", "16:00", "3-xona")   # Chorshanba
        _slot(db, g, 5, "14:00", "16:00", "3-xona")   # Juma

        # Bolalar: Alibek (qarzdor), Malika (to'lagan)
        alibek = _get_or_create_student(db, "DEMO Alibek Mominov", "+998900000101")
        malika = _get_or_create_student(db, "DEMO Malika Mominova", "+998900000102")
        _enroll(db, g, alibek)
        _enroll(db, g, malika)
        db.flush()

        # Malika joriy oy uchun to'lagan
        paid = db.query(models.Payment).filter_by(student_id=malika.id, group_id=g.id,
                                                  month=now.month, year=now.year).first()
        if not paid:
            db.add(models.Payment(student_id=malika.id, group_id=g.id, amount=450000,
                                  month=now.month, year=now.year, paid_at=now, notes="Naqd"))

        # Ota-ona akkaunti (Nodira opa) — ikkala bolaga bog'langan
        parent = db.query(models.Parent).filter_by(phone=DEMO_PARENT_PHONE).first()
        if not parent:
            parent = models.Parent(
                full_name="Nodira Mominova", display_name="Nodira opa",
                phone=DEMO_PARENT_PHONE, username=DEMO_PARENT_PHONE,
                hashed_password=hash_password(DEMO_PARENT_PASSWORD),
                is_active=True, created_at=now,
            )
            db.add(parent); db.flush()
        for child in (alibek, malika):
            link = db.query(models.ParentChild).filter_by(parent_id=parent.id, student_id=child.id).first()
            if not link:
                db.add(models.ParentChild(parent_id=parent.id, student_id=child.id, created_at=now))

        db.commit()
        print("✓ Demo oila tayyor")
        print(f"  Ota-ona login: {DEMO_PARENT_PHONE}")
        print(f"  Parol:         {DEMO_PARENT_PASSWORD}")
        print(f"  Bolalar:       DEMO Alibek (qarzdor), DEMO Malika (to'lagan)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
