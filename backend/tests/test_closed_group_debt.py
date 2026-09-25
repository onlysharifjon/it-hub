"""Arxivlangan guruh / o'chirilgan a'zolik — o'tgan oylar va to'lovlar qarz hisobidan unutilmaydi."""
from datetime import datetime
from decimal import Decimal

from backend import core_calc
from backend.main import _students_payment_map
from backend.models import Group, GroupStudent, Payment, Student


def _mk_student(db, name="Dekanov Amir"):
    s = Student(full_name=name, phone1="+998914498301", is_active=True,
                created_at=datetime(2026, 8, 7))
    db.add(s); db.commit(); db.refresh(s)
    return s


def _mk_group(db, name, start, is_active=True, closed_at=None):
    g = Group(name=name, stage="foundation", course_price=700000, start_date=start,
              is_active=is_active, closed_at=closed_at, created_at=start or datetime(2026, 9, 1))
    db.add(g); db.commit(); db.refresh(g)
    return g


def _pay(db, s, g, month, amount=700000):
    db.add(Payment(student_id=s.id, group_id=g.id, amount=amount, month=month, year=2026))
    db.commit()


def _status(db, s, month=9):
    db.expire_all()
    _owed, _paid, debt, status, _adv = _students_payment_map(db, [s], month, 2026)[s.id]
    return debt, status


def test_deleted_membership_payment_does_not_cover_next_month(db):
    """Dekanov Amir holati: S007 a'zoligi o'chirilgan, S007 arxivlangan, S003 ga o'tgan.
    Avgust to'lovi sentyabr qarzini yopmasligi kerak."""
    s = _mk_student(db)
    s007 = _mk_group(db, "S007", datetime(2026, 8, 3), is_active=False, closed_at=None)
    s003 = _mk_group(db, "S003", datetime(2026, 7, 9))
    db.add(GroupStudent(group_id=s003.id, student_id=s.id, joined_at=datetime(2026, 9, 2)))
    db.commit()
    _pay(db, s, s007, 8)

    assert _status(db, s) == (Decimal(700000), "debtor")
    _pay(db, s, s003, 9)
    assert _status(db, s) == (Decimal(0), "paid")


def test_mid_month_transfer_payment_covers_new_group(db):
    """Sentyabrda eski guruhga to'lab, sentyabr o'rtasida boshqa guruhga o'tkazilgan
    talaba — sentyabr ikki marta hisoblanmaydi."""
    s = _mk_student(db, "Qudratov Firdavs")
    old = _mk_group(db, "S002", datetime(2026, 7, 1))
    new = _mk_group(db, "P-006", None)
    db.add(GroupStudent(group_id=new.id, student_id=s.id, joined_at=datetime(2026, 9, 9)))
    db.commit()
    _pay(db, s, old, 8)
    _pay(db, s, old, 9)

    assert _status(db, s) == (Decimal(0), "paid")


def test_closed_group_counts_until_closed_month(db):
    """Arxivlangan guruhning o'tgan oylari qarz sifatida qoladi, keyingi oylar — yo'q."""
    s = _mk_student(db)
    g = _mk_group(db, "S007", datetime(2026, 7, 1), is_active=False,
                  closed_at=datetime(2026, 8, 20))
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(2026, 7, 1)))
    db.commit()
    _pay(db, s, g, 7)

    # Iyul to'langan, avgust (arxivlangan oy) to'lanmagan; sentyabr hisoblanmaydi.
    assert core_calc.student_cumulative_owed(db, s, 2026, 9) == Decimal(1400000)
    assert _status(db, s) == (Decimal(700000), "debtor")


def test_prepayment_before_group_start_stays_credit(db):
    """A'zoligi bor guruhga boshlanishidan oldingi oy uchun to'lov avans bo'lib qoladi."""
    s = _mk_student(db)
    g = _mk_group(db, "S010", datetime(2026, 9, 1))
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(2026, 8, 25)))
    db.commit()
    _pay(db, s, g, 8)

    assert _status(db, s) == (Decimal(0), "paid")


def test_archiving_group_sets_closed_at(client, metodist_token, db):
    headers = {"Authorization": f"Bearer {metodist_token}"}
    g = _mk_group(db, "S020", datetime(2026, 7, 1))
    r = client.put(f"/groups/{g.id}", json={"is_active": False}, headers=headers)
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Group, g.id).closed_at is not None
    client.put(f"/groups/{g.id}", json={"is_active": True}, headers=headers)
    db.expire_all()
    assert db.get(Group, g.id).closed_at is None


def test_mid_month_transfer_billed_once(db):
    """Oy o'rtasida boshqa guruhga o'tkazilgan talaba — shu oy faqat yangi guruhda."""
    s = _mk_student(db)
    a = _mk_group(db, "S007", datetime(2026, 8, 1))
    b = _mk_group(db, "S003", datetime(2026, 7, 1))
    db.add(GroupStudent(group_id=a.id, student_id=s.id, joined_at=datetime(2026, 8, 3),
                        left_at=datetime(2026, 9, 2, 10)))
    db.add(GroupStudent(group_id=b.id, student_id=s.id, joined_at=datetime(2026, 9, 2, 11)))
    db.commit()
    db.refresh(s)

    assert core_calc.student_cumulative_owed(db, s, 2026, 9) == Decimal(1400000)   # avg + sen
    assert core_calc.student_month_owed(db, s.id, a.id, 9, 2026) == 0
    assert core_calc.student_month_owed(db, s.id, b.id, 9, 2026) == Decimal(700000)
    _pay(db, s, a, 8)
    assert _status(db, s) == (Decimal(700000), "debtor")
    _pay(db, s, b, 9)
    assert _status(db, s) == (Decimal(0), "paid")


def test_rejoin_same_group_same_month_billed_once(db):
    s = _mk_student(db)
    g = _mk_group(db, "S003", datetime(2026, 9, 1))
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(2026, 9, 1),
                        left_at=datetime(2026, 9, 5)))
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(2026, 9, 6)))
    db.commit()
    db.refresh(s)

    assert core_calc.student_cumulative_owed(db, s, 2026, 9) == Decimal(700000)


def test_leaving_without_new_group_still_pays_that_month(db):
    s = _mk_student(db)
    g = _mk_group(db, "S003", datetime(2026, 8, 1))
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(2026, 8, 1),
                        left_at=datetime(2026, 9, 10)))
    db.commit()
    db.refresh(s)

    assert core_calc.student_cumulative_owed(db, s, 2026, 10) == Decimal(1400000)   # avg + sen
