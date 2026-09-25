"""Guruh kurs progressi — chiqib ketgan talabalarning davomati "o'tilgan darslar"ga qo'shilmaydi."""
from datetime import date, datetime

from backend import core_calc
from backend.models import Attendance, Group, GroupStudent, Student


def _mk_student(db, name, phone):
    s = Student(full_name=name, phone1=phone, is_active=True, created_at=datetime.utcnow())
    db.add(s); db.commit(); db.refresh(s)
    return s


def _mk_group(db, name="S003"):
    g = Group(name=name, stage="foundation", course_price=700000, is_active=True,
              created_at=datetime.utcnow())
    db.add(g); db.commit(); db.refresh(g)
    return g


def _mark(db, group, student, days, present=True):
    for d in days:
        db.add(Attendance(group_id=group.id, student_id=student.id, lesson_date=d, is_present=present))
    db.commit()


def test_left_student_lessons_not_counted(db):
    """Eski talaba yakka o'qigan darslar yangi tarkib progressiga qo'shilmaydi (S003/Hamrobek holati)."""
    g = _mk_group(db)
    old = _mk_student(db, "Eski talaba", "+998900000001")
    new = _mk_student(db, "Yangi talaba", "+998900000002")
    db.add(GroupStudent(group_id=g.id, student_id=old.id, joined_at=datetime(2026, 7, 1),
                        left_at=datetime(2026, 9, 9)))
    db.add(GroupStudent(group_id=g.id, student_id=new.id, joined_at=datetime(2026, 9, 2)))
    db.commit()
    _mark(db, g, old, [date(2026, 7, 10), date(2026, 7, 13), date(2026, 8, 28), date(2026, 9, 2)])
    _mark(db, g, new, [date(2026, 9, 2), date(2026, 9, 4)])

    assert core_calc.group_completed_lessons(db, [g.id]) == {g.id: 2}
    # O'tgan oy uchun o'sha paytdagi a'zolar bo'yicha — eski talaba hali a'zo edi.
    assert core_calc.group_completed_lessons(db, [g.id], upto=date(2026, 8, 31)) == {g.id: 3}


def test_absent_marks_count_and_unmarked_do_not(db):
    """Kelmagan (False) dars ham o'tilgan hisoblanadi; belgilanmagan (None) — yo'q."""
    g = _mk_group(db)
    s = _mk_student(db, "Talaba", "+998900000003")
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(2026, 9, 1)))
    db.commit()
    _mark(db, g, s, [date(2026, 9, 2)], present=True)
    _mark(db, g, s, [date(2026, 9, 4)], present=False)
    _mark(db, g, s, [date(2026, 9, 7)], present=None)

    assert core_calc.group_completed_lessons(db, [g.id]) == {g.id: 2}


def test_other_group_lessons_do_not_leak(db):
    """Yangi qo'shilgan talabaning boshqa guruhdagi darslari bu guruhga ta'sir qilmaydi."""
    g1, g2 = _mk_group(db, "S002"), _mk_group(db, "S003")
    s = _mk_student(db, "Talaba", "+998900000004")
    db.add(GroupStudent(group_id=g1.id, student_id=s.id, joined_at=datetime(2026, 7, 1),
                        left_at=datetime(2026, 9, 1)))
    db.add(GroupStudent(group_id=g2.id, student_id=s.id, joined_at=datetime(2026, 9, 1)))
    db.commit()
    _mark(db, g1, s, [date(2026, 7, d) for d in (1, 3, 6, 8, 10)])
    _mark(db, g2, s, [date(2026, 9, 2)])

    assert core_calc.group_completed_lessons(db, [g1.id, g2.id]) == {g2.id: 1}
