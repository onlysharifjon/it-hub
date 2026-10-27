"""Guruhi almashtirilgan talabaning chegirmasi eski guruhdagi o'tgan oylarga ham
qo'llanishi kerak (aks holda soxta qarz chiqadi — qarzdorlar ro'yxatida ko'rinib qoladi).
"""
from datetime import datetime
from decimal import Decimal

import pytest

from backend import core_calc, main, models


def _setup(db, discount_group: str):
    a = models.Group(name="A", course_price=700000, start_date=datetime(2026, 8, 1))
    b = models.Group(name="B", course_price=700000, start_date=datetime(2026, 8, 1))
    s = models.Student(full_name="Test Talaba", phone1="+998900000000")
    db.add_all([a, b, s])
    db.flush()
    db.add_all([
        models.GroupStudent(group_id=a.id, student_id=s.id, joined_at=datetime(2026, 9, 7),
                            left_at=datetime(2026, 10, 14)),
        models.GroupStudent(group_id=b.id, student_id=s.id, joined_at=datetime(2026, 10, 14)),
        models.SpecialDiscount(student_id=s.id, kind="monthly", amount=250000, is_active=True,
                               group_id={"none": None, "old": a.id, "new": b.id}[discount_group]),
        models.Payment(student_id=s.id, group_id=a.id, amount=450000, month=9, year=2026),
        models.Payment(student_id=s.id, group_id=a.id, amount=450000, month=10, year=2026),
    ])
    db.commit()
    db.refresh(s)
    return s, a, b


@pytest.mark.parametrize("discount_group", ["none", "old", "new"])
def test_transferred_student_keeps_discount_in_old_group_months(db, discount_group):
    s, a, b = _setup(db, discount_group)

    assert core_calc.student_month_owed(db, s.id, a.id, 9, 2026) == Decimal("450000")
    assert core_calc.student_month_owed(db, s.id, b.id, 10, 2026) == Decimal("450000")
    assert core_calc.student_cumulative_owed(db, s, upto_year=2026, upto_month=10) == Decimal("900000")
    assert core_calc.student_cumulative_balance(db, s, upto_year=2026, upto_month=10) == 0

    discounts = core_calc.active_special_discounts(db, s.id)
    assert main._student_owed_total(db, s, 9, 2026, discounts, []) == Decimal("450000")

    sept = main._finance_month(db, 9, 2026)
    row = next(st for g in sept["groups"] if g["group_id"] == a.id
               for st in g["all_students"] if st["student_id"] == s.id)
    assert row["owed"] == 450000


def test_global_discount_applied_once_for_two_simultaneous_groups(db):
    a = models.Group(name="A", course_price=700000, start_date=datetime(2026, 8, 1))
    b = models.Group(name="B", course_price=500000, start_date=datetime(2026, 8, 1))
    s = models.Student(full_name="Ikki Guruh", phone1="+998900000001")
    db.add_all([a, b, s])
    db.flush()
    db.add_all([
        models.GroupStudent(group_id=a.id, student_id=s.id, joined_at=datetime(2026, 9, 1)),
        models.GroupStudent(group_id=b.id, student_id=s.id, joined_at=datetime(2026, 9, 1)),
        models.SpecialDiscount(student_id=s.id, kind="monthly", amount=100000, is_active=True),
    ])
    db.commit()
    db.refresh(s)

    owed = core_calc.student_month_owed(db, s.id, a.id, 9, 2026) + \
        core_calc.student_month_owed(db, s.id, b.id, 9, 2026)
    assert owed == Decimal("1100000")
