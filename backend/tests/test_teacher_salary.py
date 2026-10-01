"""O'qituvchi "talaba ulushi" — dars sanasidagi o'qituvchiga yoziladi, barcha sahifalar bir xil."""
from datetime import date, datetime
from decimal import Decimal

from backend.main import _teacher_bonus_items, _teacher_salary_breakdown, teacher_salaries_breakdown
from backend.models import Attendance, Group, GroupTeacherHistory, Student, User


def _mk_teacher(db, username):
    u = User(username=username, full_name=username, role="teacher", hashed_password="x", is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _setup(db):
    a, b = _mk_teacher(db, "ramazonbek"), _mk_teacher(db, "sharifjon")
    g = Group(name="S002", stage="foundation", course_price=700000, teacher_id=b.id,
              start_date=datetime(2026, 7, 1))
    db.add(g); db.commit(); db.refresh(g)
    # A boshidan, 2026-09-10 dan B
    db.add_all([
        GroupTeacherHistory(group_id=g.id, teacher_id=a.id, started_at=datetime(2000, 1, 1)),
        GroupTeacherHistory(group_id=g.id, teacher_id=b.id, started_at=datetime(2026, 9, 10, 6, 0)),
    ])
    # A'zolik yozuvi yo'q talaba (eski usulda o'chirilgan) — davomati baribir hisoblanadi
    s = Student(full_name="Qudratov Firdavs", phone1="+998900000001", is_active=True)
    db.add(s); db.commit(); db.refresh(s)
    return a, b, g, s


def _attend(db, g, s, days, month):
    for d in days:
        db.add(Attendance(group_id=g.id, student_id=s.id, lesson_date=date(2026, month, d), is_present=True))
    db.commit()


def test_past_month_stays_with_previous_teacher(db):
    a, b, g, s = _setup(db)
    _attend(db, g, s, [4, 6, 8, 11], 8)
    bd = _teacher_salary_breakdown(db, 8, 2026)
    assert bd[a.id]["total"] == Decimal(50000)
    assert b.id not in bd


def test_mid_month_change_splits_by_lesson_date(db):
    a, b, g, s = _setup(db)
    _attend(db, g, s, [2, 4, 10, 12], 9)   # 2 ta dars A, 2 ta dars B
    bd = _teacher_salary_breakdown(db, 9, 2026)
    assert bd[a.id]["total"] == Decimal(25000)
    assert bd[b.id]["total"] == Decimal(25000)


def test_stats_page_matches_salary_page(db):
    a, b, g, s = _setup(db)
    g.is_active = False   # arxivlangan guruh ham hisoblanadi
    db.commit()
    _attend(db, g, s, [2, 4, 10, 12], 9)
    stats = teacher_salaries_breakdown(month=9, year=2026, db=db, _=None)
    by_teacher = {t["teacher_id"]: t["total_salary"] for t in stats["teachers"]}
    bd = _teacher_salary_breakdown(db, 9, 2026)
    assert by_teacher == {tid: float(e["total"]) for tid, e in bd.items()}
    assert sum(it["share"] for it in _teacher_bonus_items(db, 9, 2026)) == Decimal(50000)


def test_salary_exempt_teacher_gets_no_fix_and_no_kpi(db):
    from backend.main import _teacher_auto_salary
    a, b, g, s = _setup(db)
    b.salary_exempt = True
    db.commit()
    _attend(db, g, s, [2, 4, 10, 12], 9)
    bd = _teacher_salary_breakdown(db, 9, 2026)
    assert bd[a.id]["total"] == Decimal(25000)
    assert bd[b.id]["total"] == Decimal(0)
    assert _teacher_auto_salary(db, b.id, 9, 2026)[0] == Decimal(0)
    assert _teacher_auto_salary(db, a.id, 9, 2026)[0] == Decimal(5000000) + Decimal(25000)
