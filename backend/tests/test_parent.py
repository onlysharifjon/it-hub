"""Ota-ona API testlari — Flutter shartnomasi (docs/parent-api) bo'yicha.

Auth/refresh, ownership, xom JSON shakllari va turlari, moliyaviy holatlar,
akademik ro'yxatlar, bildirishnomalar va to'lov provayderlari (Payme/Click/Uzum
mock credential'lar bilan — haqiqiy pul ko'chirilmaydi).
"""
import base64
import hashlib
import json
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from jose import jwt

from backend import security, tz
from backend.models import (
    Attendance, Certificate, Event, Grade, Group, GroupStudent, Homework, HomeworkSubmission,
    Parent, ParentChild, ParentInvoice, ParentNotification, ParentRefreshToken, Payment,
    PaymentTransaction, PhoneVerification, ScheduleSlot, SpecialDiscount, Student, TeacherFeedback, UserRole,
)
from .conftest import _create_user

PASSWORD = "S3cret-pass"


# ── Fixtures / yordamchilar ──────────────────────────────────────────────────

@pytest.fixture
def hunter_user(db):
    return _create_user(db, "hunter", "hunter123", UserRole.hunter)


def _mk_student(db, name="Alibek Mominov", phone="+998900000001"):
    s = Student(full_name=name, phone1=phone, is_active=True, created_at=datetime.utcnow())
    db.add(s); db.commit(); db.refresh(s)
    return s


def _mk_group(db, name="Frontend G-101", price=450000, teacher=None, **kw):
    g = Group(name=name, stage="frontend", course_price=price, is_active=True,
              teacher_id=teacher.id if teacher else None, created_at=datetime.utcnow(), **kw)
    db.add(g); db.commit(); db.refresh(g)
    return g


def _enroll(db, group, student, joined_at=None):
    db.add(GroupStudent(group_id=group.id, student_id=student.id, joined_at=joined_at or datetime.utcnow()))
    db.commit()


def _mk_parent(db, children, phone="+998901112233", active=True, display_name=None):
    p = Parent(full_name="Nodira Mominova", display_name=display_name, phone=phone, username=phone,
               hashed_password=security.hash_password(PASSWORD), is_active=active)
    db.add(p); db.flush()
    for c in children:
        db.add(ParentChild(parent_id=p.id, student_id=c.id))
    db.commit(); db.refresh(p)
    return p


def _login(client, username="+998901112233", password=PASSWORD):
    return client.post("/parent/auth/login", json={"username": username, "password": password})


def _h(client, username="+998901112233"):
    res = _login(client, username)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _now():
    t = tz.today()
    return t.month, t.year


def _summary(client, h, sid, month=None, year=None):
    m, y = _now()
    return client.get(f"/parent/children/{sid}/payment-summary?month={month or m}&year={year or y}", headers=h)


def _months_ago(n):
    t = tz.today().replace(day=1)
    for _ in range(n):
        t = (t - timedelta(days=1)).replace(day=1)
    return datetime(t.year, t.month, 1, 6, 0)


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_hunter_created_parent_logs_in(client, db, hunter_user):
    student = _mk_student(db)
    htoken = client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]
    acct = client.post("/parents", headers={"Authorization": f"Bearer {htoken}"},
                       json={"full_name": "Nodira", "phone": "+998901112233", "student_ids": [student.id]}).json()
    res = _login(client, "+998901112233", acct["generated_password"])
    assert res.status_code == 200
    assert set(res.json()) == {"access_token", "refresh_token"}


@pytest.mark.parametrize("username", ["+998901112233", "+998 90 111 22 33", "998901112233", "901112233"])
def test_login_phone_normalization(client, db, username):
    _mk_parent(db, [], phone="+998 90 111-22-33")
    assert _login(client, username).status_code == 200


def test_login_failures_are_uniform_401(client, db):
    _mk_parent(db, [])
    _mk_parent(db, [], phone="+998901110000", active=False)
    wrong = _login(client, password="wrong")
    unknown = _login(client, username="+998909999999")
    inactive = _login(client, username="+998901110000")
    trimmed = _login(client, password=PASSWORD + " ")       # parol trim qilinmaydi
    for r in (wrong, unknown, inactive, trimmed):
        assert r.status_code == 401
        assert r.json()["code"] == "invalid_credentials"
        assert r.json()["request_id"] and r.headers["x-request-id"] == r.json()["request_id"]


def test_login_rate_limited_with_retry_after(client, db):
    _mk_parent(db, [])
    codes = [_login(client, password="bad").status_code for _ in range(7)]
    assert codes[-1] == 429
    r = _login(client, password="bad")
    assert r.status_code == 429 and r.headers.get("retry-after") and r.json()["code"] == "rate_limited"


def test_staff_token_is_not_parent_token(client, db, hunter_user):
    staff = client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]
    r = client.get("/parent/profile", headers={"Authorization": f"Bearer {staff}"})
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    assert client.get("/parent/profile").status_code == 401


def test_expired_access_token_401(client, db):
    p = _mk_parent(db, [])
    expired = jwt.encode({"sub": str(p.id), "role": "parent", "exp": datetime.utcnow() - timedelta(minutes=1)},
                         security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert client.get("/parent/profile", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_refresh_rotation_grace_and_reuse_detection(client, db):
    _mk_parent(db, [])
    first = _login(client).json()
    r1 = client.post("/parent/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r1.status_code == 200 and set(r1.json()) == {"access_token", "refresh_token"}
    second = r1.json()["refresh_token"]
    assert second != first["refresh_token"]

    # Darhol qayta ishlatish (parallel so'rov) — 401, lekin yangi sessiya saqlanadi
    assert client.post("/parent/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    r2 = client.post("/parent/auth/refresh", json={"refresh_token": second})
    assert r2.status_code == 200
    third = r2.json()["refresh_token"]

    # Grace'dan keyin eski token qayta ishlatilsa — barcha sessiyalar bekor
    row = db.query(ParentRefreshToken).filter(
        ParentRefreshToken.token_hash == security.hash_token(second)).first()
    row.revoked_at = datetime.utcnow() - timedelta(minutes=5)
    db.commit()
    reuse = client.post("/parent/auth/refresh", json={"refresh_token": second})
    assert reuse.status_code == 401 and reuse.json()["code"] == "token_reuse"
    assert client.post("/parent/auth/refresh", json={"refresh_token": third}).status_code == 401


def test_refresh_expired_and_unknown(client, db):
    _mk_parent(db, [])
    tok = _login(client).json()["refresh_token"]
    db.query(ParentRefreshToken).update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
    db.commit()
    assert client.post("/parent/auth/refresh", json={"refresh_token": tok}).status_code == 401
    assert client.post("/parent/auth/refresh", json={"refresh_token": "nope"}).status_code == 401


def test_error_envelope_for_bad_json_and_validation(client, db):
    r = client.post("/parent/auth/login", content=b"{bad json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["code"] == "invalid_json"
    r = client.post("/parent/auth/login", json={"username": "+998901112233"})
    body = r.json()
    assert r.status_code == 422 and body["code"] == "validation_error" and "password" in body["errors"]
    assert set(body) == {"code", "message", "errors", "request_id"}


# ── Profil ───────────────────────────────────────────────────────────────────

def test_profile_get_and_patch(client, db):
    _mk_parent(db, [], phone="+998 90 111 22 33")
    h = _h(client, "+998901112233")
    prof = client.get("/parent/profile", headers=h).json()
    assert prof == {"display_name": "Nodira Mominova", "full_name": "Nodira Mominova", "phone": "+998901112233"}

    r = client.patch("/parent/profile", headers=h, json={"display_name": "  Nodira xonim  "})
    assert r.status_code == 204 and r.content == b""
    assert client.get("/parent/profile", headers=h).json()["display_name"] == "Nodira xonim"

    for bad in ({"display_name": "   "}, {"display_name": "x" * 101}, {"display_name": None},
                {"phone": "+998900000000"}, {"child_ids": [1]}, {"role": "admin"},
                {"avatar_base64": "not-base64!!"}, {"avatar_base64": base64.b64encode(b"GIF89a....").decode()}):
        assert client.patch("/parent/profile", headers=h, json=bad).status_code == 422, bad
    assert client.get("/parent/profile", headers=h).json()["phone"] == "+998901112233"

    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
    assert client.patch("/parent/profile", headers=h, json={"avatar_base64": png}).status_code == 204
    assert db.query(Parent).first().avatar == png


# ── Farzandlar ───────────────────────────────────────────────────────────────

def test_children_empty_and_shapes(client, db):
    teacher = _create_user(db, "ustoz", "x" * 8, UserRole.teacher)
    teacher.full_name = "Jasur Karimov"; db.commit()
    a = _mk_student(db, "Alibek")
    b = _mk_student(db, "Bekzod", "+998900000002")
    g = _mk_group(db, teacher=teacher, schedule="Toq kunlar", lesson_time="14:00")
    _enroll(db, g, a)
    db.add(SpecialDiscount(student_id=a.id, kind="monthly", amount=45000, is_active=True))
    db.commit()

    _mk_parent(db, [], phone="+998901110001")
    assert client.get("/parent/children", headers=_h(client, "+998901110001")).json() == []

    _mk_parent(db, [a, b])
    kids = client.get("/parent/children", headers=_h(client)).json()
    assert [k["full_name"] for k in kids] == ["Alibek", "Bekzod"]
    ka, kb = kids
    assert ka == {
        "id": a.id, "full_name": "Alibek", "group_name": "Frontend G-101", "stage": "Frontend",
        "teacher_name": "Jasur Karimov", "schedule": "Du · Chor · Ju, 14:00", "tariff": 450000,
        "start_date": tz.today().isoformat(), "discount_percent": 10, "avatar": None,
    }
    assert kb["group_name"] == "" and kb["teacher_name"] == "" and kb["schedule"] == ""
    assert kb["tariff"] == 0 and kb["discount_percent"] == 0 and kb["start_date"] is None


def test_ownership_on_every_child_endpoint(client, db):
    mine = _mk_student(db, "Mening bolam")
    other = _mk_student(db, "Begona bola", "+998900000011")
    g = _mk_group(db)
    _enroll(db, g, other)
    _mk_parent(db, [mine])
    h = _h(client)
    m, y = _now()
    for path in ("payment-summary", "attendance"):
        assert client.get(f"/parent/children/{other.id}/{path}?month={m}&year={y}", headers=h).status_code == 404
    for path in ("schedule", "grades", "homework", "feedback", "certificates", "teacher"):
        r = client.get(f"/parent/children/{other.id}/{path}", headers=h)
        assert r.status_code == 404 and r.json()["code"] == "child_not_found", path
    r = client.post(f"/parent/children/{other.id}/pay", headers=h,
                    json={"amount": 100000, "group_id": g.id, "provider": "payme"})
    assert r.status_code == 404


def test_empty_lists_for_child_without_data(client, db):
    s = _mk_student(db)
    _mk_parent(db, [s])
    h = _h(client)
    for path in ("schedule", "grades", "homework", "feedback", "certificates"):
        r = client.get(f"/parent/children/{s.id}/{path}", headers=h)
        assert r.status_code == 200 and r.json() == [], path
    assert client.get("/parent/notifications", headers=h).json() == []
    m, y = _now()
    att = client.get(f"/parent/children/{s.id}/attendance?month={m}&year={y}", headers=h).json()
    assert att == {"percent": 0, "records": []}
    summ = _summary(client, h, s.id).json()
    assert summ == {"month": m, "year": y, "total_owed": 0, "total_paid": 0, "advance_balance": 0,
                    "advance_applied": 0, "debt": 0, "payment_status": "paid",
                    "groups": [], "recent_payments": []}
    t = client.get(f"/parent/children/{s.id}/teacher", headers=h)
    assert t.status_code == 404 and t.json()["code"] == "teacher_not_assigned"


# ── To'lov hisobi ────────────────────────────────────────────────────────────

def test_payment_summary_query_validation(client, db):
    s = _mk_student(db)
    _mk_parent(db, [s])
    h = _h(client)
    base = f"/parent/children/{s.id}/payment-summary"
    assert client.get(base, headers=h).status_code == 422
    assert client.get(base + "?month=13&year=2026", headers=h).status_code == 422
    assert client.get(base + "?month=1&year=1999", headers=h).status_code == 422
    assert client.get(base + "?month=a&year=2026", headers=h).status_code == 422


def test_payment_summary_debtor_partial_paid_overpaid(client, db, hunter_user):
    s = _mk_student(db)
    g = _mk_group(db, price=450000)
    _enroll(db, g, s)
    _mk_parent(db, [s])
    h = _h(client)
    m, y = _now()
    htoken = client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]
    hh = {"Authorization": f"Bearer {htoken}"}

    r = _summary(client, h, s.id).json()
    assert (r["total_owed"], r["total_paid"], r["debt"], r["payment_status"]) == (450000, 0, 450000, "debtor")
    assert r["groups"] == [{"group_id": g.id, "group_name": g.name, "owed": 450000, "paid": 0, "remaining": 450000}]

    client.post("/payments", headers=hh, json={"student_id": s.id, "group_id": g.id, "amount": 200000,
                                               "month": m, "year": y, "notes": "Naqd"})
    r = _summary(client, h, s.id).json()
    assert (r["total_paid"], r["debt"], r["payment_status"]) == (200000, 250000, "partial")
    p = r["recent_payments"][0]
    assert p["amount"] == 200000 and p["notes"] == "Naqd" and p["recorded_by_name"] == "hunter"
    assert p["paid_at"].endswith("+05:00") and isinstance(p["amount"], int)

    client.post("/payments", headers=hh, json={"student_id": s.id, "group_id": g.id, "amount": 300000,
                                               "month": m, "year": y})
    r = _summary(client, h, s.id).json()
    assert (r["debt"], r["payment_status"], r["advance_balance"]) == (0, "paid", 50000)
    assert r["groups"][0]["remaining"] == 0
    assert [x["amount"] for x in r["recent_payments"]] == [300000, 200000]


def test_payment_summary_multi_group_and_prepaid_advance(client, db):
    s = _mk_student(db)
    s.advance_balance = 100000
    db.commit()
    g1 = _mk_group(db, "G1", price=400000)
    g2 = _mk_group(db, "G2", price=300000)
    _enroll(db, g1, s); _enroll(db, g2, s)
    _mk_parent(db, [s])
    r = _summary(client, _h(client), s.id).json()
    assert r["total_owed"] == 700000 and len(r["groups"]) == 2
    assert r["advance_applied"] == 100000 and r["debt"] == 600000
    assert r["payment_status"] == "partial" and r["advance_balance"] == 0


def test_payment_summary_free_month_is_paid_not_debtor(client, db):
    s = _mk_student(db)
    g = _mk_group(db, price=450000)
    _enroll(db, g, s)
    m, y = _now()
    db.add(SpecialDiscount(student_id=s.id, kind="free_month", month=m, year=y, is_active=True))
    db.commit()
    _mk_parent(db, [s])
    r = _summary(client, _h(client), s.id).json()
    assert r["total_owed"] == 0 and r["debt"] == 0 and r["payment_status"] == "paid"


# ── Davomat ──────────────────────────────────────────────────────────────────

def test_attendance_two_lessons_same_day_and_filters(client, db):
    s = _mk_student(db)
    g1 = _mk_group(db, "Frontend G-101")
    g2 = _mk_group(db, "English A-2")
    today = tz.today()
    g3 = _mk_group(db, "Tekshirilmagan")
    db.add_all([
        Attendance(group_id=g1.id, student_id=s.id, lesson_date=today, is_present=True),
        Attendance(group_id=g2.id, student_id=s.id, lesson_date=today, is_present=False),
        Attendance(group_id=g3.id, student_id=s.id, lesson_date=today, is_present=None),  # belgilanmagan
    ])
    future = today + timedelta(days=1)
    if future.month == today.month:
        db.add(Attendance(group_id=g2.id, student_id=s.id, lesson_date=future, is_present=False))
    db.commit()
    _mk_parent(db, [s])
    r = client.get(f"/parent/children/{s.id}/attendance?month={today.month}&year={today.year}",
                   headers=_h(client)).json()
    assert r["percent"] == 50
    assert sorted((x["group_name"], x["is_present"]) for x in r["records"]) == [
        ("English A-2", False), ("Frontend G-101", True)]
    assert all(x["lesson_date"] == today.isoformat() for x in r["records"])


# ── Jadval ───────────────────────────────────────────────────────────────────

def test_schedule_slots_text_fallback_and_sorting(client, db):
    teacher = _create_user(db, "ustoz", "x" * 8, UserRole.teacher)
    s = _mk_student(db)
    g1 = _mk_group(db, "Slotli", teacher=teacher)
    g2 = _mk_group(db, "Matnli", schedule="Juft kunlar", lesson_time="9:30")
    g3 = _mk_group(db, "Vaqtsiz", schedule="Toq kunlar")
    for g in (g1, g2, g3):
        _enroll(db, g, s)
    db.add_all([ScheduleSlot(group_id=g1.id, day_of_week=3, start_time="16:00", end_time="18:00", room="204"),
                ScheduleSlot(group_id=g1.id, day_of_week=1, start_time="14:00", end_time="16:00")])
    db.commit()
    _mk_parent(db, [s])
    rows = client.get(f"/parent/children/{s.id}/schedule", headers=_h(client)).json()
    assert [(r["day_of_week"], r["start_time"], r["end_time"], r["group_name"]) for r in rows] == [
        (1, "14:00", "16:00", "Slotli"), (2, "09:30", "11:30", "Matnli"), (3, "16:00", "18:00", "Slotli"),
        (4, "09:30", "11:30", "Matnli"), (6, "09:30", "11:30", "Matnli")]
    assert rows[0] == {"day_of_week": 1, "start_time": "14:00", "end_time": "16:00", "group_name": "Slotli",
                       "teacher_name": "ustoz", "stage": "Frontend", "room": None}
    assert rows[2]["room"] == "204" and rows[1]["teacher_name"] == ""


# ── Bildirishnomalar ─────────────────────────────────────────────────────────

def test_notifications_read_per_parent_403_404_idempotent(client, db, hunter_user):
    s = _mk_student(db)
    g = _mk_group(db)
    _enroll(db, g, s)
    _mk_parent(db, [s], phone="+998901110001")
    _mk_parent(db, [s], phone="+998901110002")
    m, y = _now()
    htoken = client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]
    client.post("/payments", headers={"Authorization": f"Bearer {htoken}"},
                json={"student_id": s.id, "group_id": g.id, "amount": 450000, "month": m, "year": y})
    ha, hb = _h(client, "+998901110001"), _h(client, "+998901110002")
    na = client.get("/parent/notifications", headers=ha).json()
    nb = client.get("/parent/notifications", headers=hb).json()
    assert len(na) == len(nb) == 1 and na[0]["id"] != nb[0]["id"]
    n = na[0]
    assert set(n) == {"id", "type", "title", "body", "created_at", "is_read"}
    assert n["type"] == "payment" and n["is_read"] is False and n["created_at"].endswith("+05:00")

    assert client.post(f"/parent/notifications/{nb[0]['id']}/read", headers=ha).status_code == 403
    assert client.post("/parent/notifications/999999/read", headers=ha).status_code == 404
    for _ in range(2):
        assert client.post(f"/parent/notifications/{n['id']}/read", headers=ha).status_code == 204
    assert client.get("/parent/notifications", headers=ha).json()[0]["is_read"] is True
    assert client.get("/parent/notifications", headers=hb).json()[0]["is_read"] is False


def test_notifications_order_and_type_fallback(client, db):
    p = _mk_parent(db, [])
    now = datetime.utcnow()
    db.add_all([ParentNotification(parent_id=p.id, type="weird", title="Eski", body=None, created_at=now - timedelta(days=1)),
                ParentNotification(parent_id=p.id, type="attendance", title="Yangi", body="b", created_at=now)])
    db.commit()
    rows = client.get("/parent/notifications", headers=_h(client)).json()
    assert [r["title"] for r in rows] == ["Yangi", "Eski"]
    assert rows[1]["type"] == "announcement" and rows[1]["body"] == ""


# ── Akademik ─────────────────────────────────────────────────────────────────

def test_grades_homework_feedback(client, db):
    teacher = _create_user(db, "ustoz", "x" * 8, UserRole.teacher)
    teacher.full_name = "Asilbek Omonov"
    s = _mk_student(db)
    g = _mk_group(db, teacher=teacher)
    db.add(ScheduleSlot(group_id=g.id, day_of_week=3, start_time="14:00", end_time="16:00"))
    _enroll(db, g, s, joined_at=datetime(2026, 7, 1))
    db.add_all([
        Grade(student_id=s.id, group_id=g.id, subject="JS Basics", score=41, max_score=50, exam_date=date(2026, 7, 5)),
        Grade(student_id=s.id, group_id=g.id, subject="HTML", score=85, max_score=100, exam_date=date(2026, 7, 1)),
    ])
    old = Homework(group_id=g.id, lesson_title="Qo'shilishdan oldin", text="x", lesson_date=date(2026, 6, 1))
    hw1 = Homework(group_id=g.id, lesson_title="Todo App", text="Todo", lesson_date=date(2026, 7, 5),
                   due_date=date(2026, 7, 8))
    hw2 = Homework(group_id=g.id, lesson_title=None, text="Kalkulyator yasang\nbatafsil",
                   lesson_date=date(2026, 7, 6))   # 2026-07-06 Dushanba → keyingi dars Chorshanba 14:00
    db.add_all([old, hw1, hw2]); db.flush()
    db.add(HomeworkSubmission(homework_id=hw1.id, student_id=s.id, status="done"))
    db.add(TeacherFeedback(student_id=s.id, group_id=g.id, teacher_id=teacher.id, comment="Yaxshi",
                           created_at=datetime(2026, 7, 4, 20, 0)))
    db.commit()
    _mk_parent(db, [s])
    h = _h(client)

    grades = client.get(f"/parent/children/{s.id}/grades", headers=h).json()
    assert grades == [{"subject": "JS Basics", "score": 41, "max_score": 50, "date": "2026-07-05"},
                      {"subject": "HTML", "score": 85, "max_score": 100, "date": "2026-07-01"}]

    hws = client.get(f"/parent/children/{s.id}/homework", headers=h).json()
    assert [x["title"] for x in hws] == ["Kalkulyator yasang", "Todo App"]
    assert hws[0] == {"id": hw2.id, "title": "Kalkulyator yasang", "due_date": "2026-07-08T14:00:00+05:00",
                      "status": "pending"}
    assert hws[1]["due_date"] == "2026-07-08T23:59:59+05:00" and hws[1]["status"] == "submitted"

    fb = client.get(f"/parent/children/{s.id}/feedback", headers=h).json()
    assert fb == [{"teacher_name": "Asilbek Omonov", "comment": "Yaxshi", "date": "2026-07-05"}]


def test_teacher_contact_strings(client, db):
    teacher = _create_user(db, "ustoz", "x" * 8, UserRole.teacher)
    teacher.full_name = "Jasur Karimov"
    teacher.phone = "+998 93 555 11 22"
    teacher.telegram = "https://t.me/jasur_teacher"
    s = _mk_student(db)
    _enroll(db, _mk_group(db, teacher=teacher), s)
    _mk_parent(db, [s])
    h = _h(client)
    assert client.get(f"/parent/children/{s.id}/teacher", headers=h).json() == {
        "name": "Jasur Karimov", "phone": "+998935551122", "telegram": "@jasur_teacher"}
    teacher.phone = None; teacher.telegram = None
    db.commit()
    assert client.get(f"/parent/children/{s.id}/teacher", headers=h).json() == {
        "name": "Jasur Karimov", "phone": "", "telegram": ""}


def test_certificates_signed_url_without_bearer(client, db, tmp_path, monkeypatch):
    import os
    s = _mk_student(db)
    cert_dir = os.path.join(os.environ["UPLOAD_DIR"], "certificates")
    os.makedirs(cert_dir, exist_ok=True)
    with open(os.path.join(cert_dir, "abc123.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 test")
    db.add_all([
        Certificate(student_id=s.id, title="Foundation", issued_at=date(2026, 6, 1),
                    file_url="https://crm.minaracademy.uz/api/uploads/certificates/abc123.pdf"),
        Certificate(student_id=s.id, title="Frontend", issued_at=date(2026, 9, 30),
                    file_url="https://files.example.com/x.pdf"),
        Certificate(student_id=s.id, title="Eski http", file_url="http://insecure.example.com/x.pdf"),
    ])
    db.commit()
    _mk_parent(db, [s])
    certs = client.get(f"/parent/children/{s.id}/certificates", headers=_h(client)).json()
    assert [c["title"] for c in certs] == ["Frontend", "Foundation"]
    assert set(certs[0]) == {"id", "title", "issue_date", "url"} and certs[0]["issue_date"] == "2026-09-30"
    for c in certs:
        assert c["url"].startswith("https://") and "sig=" in c["url"] and "exp=" in c["url"]

    local = urlparse(certs[1]["url"])
    path = local.path.removeprefix("/api")
    r = client.get(f"{path}?{local.query}")                 # Authorization yo'q
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    ext = urlparse(certs[0]["url"])
    r = client.get(f"{ext.path.removeprefix('/api')}?{ext.query}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://files.example.com/x.pdf"
    assert client.get(f"{path}?exp=9999999999&sig=bad").status_code == 403
    assert client.get(path).status_code == 403


# ── Onlayn to'lov: /pay ──────────────────────────────────────────────────────

PAYME_KEY = "test-payme-key"
CLICK_SECRET = "test-click-secret"


@pytest.fixture
def providers(monkeypatch):
    for k, v in {"PAYME_MERCHANT_ID": "merchant123", "PAYME_KEY": PAYME_KEY,
                 "CLICK_SERVICE_ID": "111", "CLICK_MERCHANT_ID": "222", "CLICK_SECRET_KEY": CLICK_SECRET,
                 "UZUM_SERVICE_ID": "333", "UZUM_LOGIN": "uzum", "UZUM_PASSWORD": "uzum-pass",
                 "PAYMENT_RETURN_URL": "https://crm.minaracademy.uz/pay/return",
                 "PARENT_PAYMENTS_ENABLED": "true"}.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def debtor(db):
    s = _mk_student(db)
    g = _mk_group(db, price=450000)
    _enroll(db, g, s, joined_at=_months_ago(1))
    _mk_parent(db, [s])
    return s, g


def _pay(client, h, sid, gid, amount=250000, provider="payme"):
    return client.post(f"/parent/children/{sid}/pay", headers=h,
                       json={"amount": amount, "group_id": gid, "provider": provider})


def test_pay_provider_not_configured_503(client, db, debtor, monkeypatch):
    for k in ("PAYME_KEY", "PAYME_MERCHANT_ID"):
        monkeypatch.delenv(k, raising=False)
    s, g = debtor
    r = _pay(client, _h(client), s.id, g.id)
    assert r.status_code == 503 and r.json()["code"] == "payment_provider_unavailable"
    assert db.query(ParentInvoice).count() == 0


def test_pay_validation(client, db, debtor, providers):
    s, g = debtor
    other_group = _mk_group(db, "Begona")
    h = _h(client)
    assert _pay(client, h, s.id, other_group.id).status_code == 404
    assert _pay(client, h, s.id, g.id, amount=0).status_code == 422
    assert _pay(client, h, s.id, g.id, amount=999).status_code == 422          # < PAYMENT_MIN_AMOUNT
    assert _pay(client, h, s.id, g.id, amount=50_000_000).status_code == 422
    assert _pay(client, h, s.id, g.id, provider="paypal").status_code == 422
    r = client.post(f"/parent/children/{s.id}/pay", headers=h,
                    json={"amount": 2500.5, "group_id": g.id, "provider": "payme"})
    assert r.status_code == 422
    # Raqamli string ID ham qabul qilinadi (client raqamli bo'lmagan ID'ni string yuboradi)
    r = client.post(f"/parent/children/{s.id}/pay", headers=h,
                    json={"amount": 250000, "group_id": str(g.id), "provider": "payme"})
    assert r.status_code == 200


def test_pay_creates_checkout_but_not_payment(client, db, debtor, providers):
    s, g = debtor
    h = _h(client)
    r = _pay(client, h, s.id, g.id)
    assert r.status_code == 200 and set(r.json()) == {"checkout_url"}
    url = urlparse(r.json()["checkout_url"])
    assert url.scheme == "https" and url.hostname == "checkout.paycom.uz"
    params = base64.b64decode(url.path.strip("/")).decode()
    inv = db.query(ParentInvoice).one()
    assert params == f"m=merchant123;ac.invoice_id={inv.id};a=25000000;c=https://crm.minaracademy.uz/pay/return"
    assert (inv.parent_id, inv.student_id, inv.group_id, inv.provider, inv.status) == (
        inv.parent_id, s.id, g.id, "payme", "pending")
    # Takroriy bosish — xuddi shu invoys
    assert _pay(client, h, s.id, g.id).json()["checkout_url"] == r.json()["checkout_url"]
    assert db.query(ParentInvoice).count() == 1
    # Checkout ochilishi to'lov emas
    summ = _summary(client, h, s.id).json()
    assert summ["recent_payments"] == [] and summ["payment_status"] == "debtor"

    click = urlparse(_pay(client, h, s.id, g.id, provider="click").json()["checkout_url"])
    q = parse_qs(click.query)
    assert click.hostname == "my.click.uz" and q["service_id"] == ["111"] and q["amount"] == ["250000"]
    uz = urlparse(_pay(client, h, s.id, g.id, provider="uzum").json()["checkout_url"])
    q = parse_qs(uz.query)
    assert uz.hostname == "www.uzumbank.uz" and q["serviceId"] == ["333"] and q["amount"] == ["25000000"]


# ── Payme ────────────────────────────────────────────────────────────────────

def _payme(client, method, params, key=PAYME_KEY, rid=1):
    auth = base64.b64encode(f"Paycom:{key}".encode()).decode()
    return client.post("/payment-callbacks/payme", headers={"Authorization": f"Basic {auth}"},
                       json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params})


def _new_invoice(client, db, s, g, amount=250000, provider="payme"):
    assert _pay(client, _h(client), s.id, g.id, amount=amount, provider=provider).status_code == 200
    return db.query(ParentInvoice).filter(ParentInvoice.provider == provider).order_by(ParentInvoice.id.desc()).first()


def test_payme_full_flow_and_idempotency(client, db, debtor, providers):
    s, g = debtor
    inv = _new_invoice(client, db, s, g, amount=600000)
    acc = {"invoice_id": str(inv.id)}

    assert _payme(client, "CheckPerformTransaction", {"amount": 60000000, "account": acc}, key="bad").json()["error"]["code"] == -32504
    assert _payme(client, "CheckPerformTransaction", {"amount": 100, "account": acc}).json()["error"]["code"] == -31001
    assert _payme(client, "CheckPerformTransaction", {"amount": 60000000, "account": {"invoice_id": "999"}}).json()["error"]["code"] == -31050
    assert _payme(client, "CheckPerformTransaction", {"amount": 60000000, "account": acc}).json()["result"] == {"allow": True}

    created = _payme(client, "CreateTransaction", {"id": "pm-1", "time": 1, "amount": 60000000, "account": acc}).json()
    assert created["result"]["state"] == 1
    again = _payme(client, "CreateTransaction", {"id": "pm-1", "time": 1, "amount": 60000000, "account": acc}).json()
    assert again["result"]["transaction"] == created["result"]["transaction"]
    busy = _payme(client, "CreateTransaction", {"id": "pm-2", "time": 1, "amount": 60000000, "account": acc}).json()
    assert busy["error"]["code"] == -31099

    # Hali tasdiqlanmagan — tarixda yo'q
    h = _h(client)
    assert _summary(client, h, s.id).json()["recent_payments"] == []

    for _ in range(2):   # takroriy Perform ikki marta yozmaydi
        res = _payme(client, "PerformTransaction", {"id": "pm-1"}).json()
        assert res["result"]["state"] == 2
    rows = db.query(Payment).filter(Payment.parent_invoice_id == inv.id).all()
    assert sum(int(p.amount) for p in rows) == 600000
    # Taqsimot: eng eski qarz (o'tgan oy 450 000) avval, qolgani joriy oyga
    m, y = _now()
    prev = _months_ago(1)
    assert sorted((p.year, p.month, int(p.amount)) for p in rows) == sorted(
        [(prev.year, prev.month, 450000), (y, m, 150000)])
    summ = _summary(client, h, s.id).json()
    assert summ["debt"] == 300000 and summ["payment_status"] == "partial"
    assert summ["recent_payments"][0]["notes"].startswith("Payme")
    assert summ["recent_payments"][0]["recorded_by_name"] == ""
    notifs = client.get("/parent/notifications", headers=h).json()
    assert len(notifs) == 1 and notifs[0]["type"] == "payment"

    chk = _payme(client, "CheckTransaction", {"id": "pm-1"}).json()["result"]
    assert chk["state"] == 2 and chk["perform_time"] > 0
    stmt = _payme(client, "GetStatement", {"from": 0, "to": 10 ** 14}).json()["result"]["transactions"]
    assert [t["id"] for t in stmt] == ["pm-1"] and stmt[0]["amount"] == 60000000

    # Refund: Payment qatorlari o'chadi
    cancel = _payme(client, "CancelTransaction", {"id": "pm-1", "reason": 5}).json()["result"]
    assert cancel["state"] == -2
    db.expire_all()
    assert db.query(Payment).filter(Payment.parent_invoice_id == inv.id).count() == 0
    assert db.query(ParentInvoice).get(inv.id).status == "refunded"
    assert _payme(client, "PerformTransaction", {"id": "pm-1"}).json()["error"]["code"] == -31008
    assert _payme(client, "CheckTransaction", {"id": "nope"}).json()["error"]["code"] == -31003


def test_payme_cancel_before_perform_and_timeout(client, db, debtor, providers):
    s, g = debtor
    inv = _new_invoice(client, db, s, g)
    acc = {"invoice_id": str(inv.id)}
    _payme(client, "CreateTransaction", {"id": "pm-x", "time": 1, "amount": 25000000, "account": acc})
    assert _payme(client, "CancelTransaction", {"id": "pm-x", "reason": 3}).json()["result"]["state"] == -1
    assert _payme(client, "PerformTransaction", {"id": "pm-x"}).json()["error"]["code"] == -31008
    assert db.query(Payment).count() == 0

    inv2 = _new_invoice(client, db, s, g, amount=260000)
    acc2 = {"invoice_id": str(inv2.id)}
    _payme(client, "CreateTransaction", {"id": "pm-y", "time": 1, "amount": 26000000, "account": acc2})
    db.query(PaymentTransaction).filter(PaymentTransaction.provider_txn_id == "pm-y").update(
        {"create_time": 0})
    db.commit()
    assert _payme(client, "PerformTransaction", {"id": "pm-y"}).json()["error"]["code"] == -31008
    assert _payme(client, "CheckTransaction", {"id": "pm-y"}).json()["result"]["reason"] == 4
    assert db.query(Payment).count() == 0


def test_payme_non_json_and_unknown_method(client, db, providers):
    auth = base64.b64encode(f"Paycom:{PAYME_KEY}".encode()).decode()
    r = client.post("/payment-callbacks/payme", headers={"Authorization": f"Basic {auth}"}, content=b"nope")
    assert r.status_code == 200 and r.json()["error"]["code"] == -32700
    assert _payme(client, "Hack", {}).json()["error"]["code"] == -32601


# ── Click ────────────────────────────────────────────────────────────────────

def _click(client, path, inv_id, amount, action, ctid="ck-1", prepare_id=None, error=0, secret=CLICK_SECRET):
    form = {"click_trans_id": ctid, "service_id": "111", "click_paydoc_id": "9", "merchant_trans_id": str(inv_id),
            "amount": str(amount), "action": str(action), "error": str(error), "error_note": "",
            "sign_time": "2026-10-06 10:00:00"}
    if prepare_id is not None:
        form["merchant_prepare_id"] = str(prepare_id)
    raw = (form["click_trans_id"] + form["service_id"] + secret + form["merchant_trans_id"]
           + (form.get("merchant_prepare_id", "")) + form["amount"] + form["action"] + form["sign_time"])
    form["sign_string"] = hashlib.md5(raw.encode()).hexdigest()
    return client.post(f"/payment-callbacks/click/{path}", data=form).json()


def test_click_prepare_complete(client, db, debtor, providers):
    s, g = debtor
    inv = _new_invoice(client, db, s, g, provider="click")
    assert _click(client, "prepare", inv.id, "250000.00", 0, secret="bad")["error"] == -1
    assert _click(client, "prepare", inv.id, "1000", 0)["error"] == -2
    assert _click(client, "prepare", 999999, "250000", 0)["error"] == -5
    prep = _click(client, "prepare", inv.id, "250000.00", 0)
    assert prep["error"] == 0 and prep["merchant_prepare_id"]
    assert db.query(Payment).count() == 0
    for _ in range(2):
        done = _click(client, "complete", inv.id, "250000.00", 1, prepare_id=prep["merchant_prepare_id"])
        assert done["error"] == 0 and done["merchant_confirm_id"] == prep["merchant_prepare_id"]
    assert sum(int(p.amount) for p in db.query(Payment).all()) == 250000
    assert _click(client, "prepare", inv.id, "250000", 0, ctid="ck-2")["error"] == -4


def test_click_complete_with_error_cancels(client, db, debtor, providers):
    s, g = debtor
    inv = _new_invoice(client, db, s, g, provider="click")
    prep = _click(client, "prepare", inv.id, "250000", 0)
    res = _click(client, "complete", inv.id, "250000", 1, prepare_id=prep["merchant_prepare_id"], error=-5017)
    assert res["error"] == -9
    db.expire_all()
    assert db.query(ParentInvoice).get(inv.id).status == "cancelled" and db.query(Payment).count() == 0


# ── Uzum ─────────────────────────────────────────────────────────────────────

def _uzum(client, op, body, login="uzum", pwd="uzum-pass"):
    auth = base64.b64encode(f"{login}:{pwd}".encode()).decode()
    payload = {"serviceId": 333, "timestamp": 1, **body}
    return client.post(f"/payment-callbacks/uzum/{op}", headers={"Authorization": f"Basic {auth}"}, json=payload)


def test_uzum_flow(client, db, debtor, providers):
    s, g = debtor
    inv = _new_invoice(client, db, s, g, provider="uzum")
    params = {"order_id": str(inv.id)}
    bad = _uzum(client, "check", {"params": params}, pwd="wrong")
    assert bad.status_code == 400 and bad.json()["errorCode"] == "10001"
    assert _uzum(client, "check", {"params": params}).json()["status"] == "OK"
    assert _uzum(client, "create", {"transId": "uz-1", "params": params, "amount": 100}).json()["errorCode"] == "10011"
    c = _uzum(client, "create", {"transId": "uz-1", "params": params, "amount": 25000000})
    assert c.status_code == 200 and c.json()["status"] == "CREATED"
    assert _uzum(client, "create", {"transId": "uz-1", "params": params, "amount": 25000000}).json()["errorCode"] == "10010"
    for _ in range(2):
        assert _uzum(client, "confirm", {"transId": "uz-1"}).json()["status"] == "CONFIRMED"
    assert db.query(Payment).count() == 1
    assert _uzum(client, "status", {"transId": "uz-1"}).json()["status"] == "CONFIRMED"
    assert _uzum(client, "reverse", {"transId": "uz-1"}).json()["status"] == "REVERSED"
    assert db.query(Payment).count() == 0
    assert _uzum(client, "reverse", {"transId": "uz-1"}).json()["errorCode"] == "10018"
    assert _uzum(client, "status", {"transId": "nope"}).json()["errorCode"] == "10014"


def test_callbacks_reject_when_provider_unconfigured(client, db, monkeypatch):
    for k in ("PAYME_KEY", "UZUM_LOGIN", "CLICK_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert _payme(client, "CheckPerformTransaction", {}).json()["error"]["code"] == -32504
    assert _uzum(client, "check", {"params": {}}).status_code == 400
    assert _click(client, "prepare", 1, "1000", 0)["error"] == -8


def test_db_outage_is_503_not_401(client, db, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from backend.parent import router_parent

    def boom(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("db down"))
    monkeypatch.setattr(router_parent, "_find_parent", boom)
    r = _login(client)
    assert r.status_code == 503 and r.json()["code"] == "service_unavailable"


# ── Parent account deletion / App Store privacy ──────────────────────────────

def test_parent_delete_account_requires_authentication(client):
    res = client.delete("/parent/account")
    assert res.status_code == 401


def test_parent_deletion_closes_login_but_keeps_data(client, db, hunter_user):
    student = _mk_student(db, "Alibek Mominov", "+998900000041")
    parent = _mk_parent(db, [student], phone="+998900000042")
    login = _login(client, "+998900000042").json()
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    parent_id = parent.id
    db.add(ParentNotification(parent_id=parent_id, student_id=student.id, type="attendance",
                              title="T", body="B", created_at=datetime.utcnow()))
    db.commit()

    deleted = client.delete("/parent/account", headers=auth)
    assert deleted.status_code == 204, deleted.text

    db.expire_all()
    p = db.query(Parent).filter(Parent.id == parent_id).one()               # ma'lumot saqlanadi
    assert p.is_active is False and p.deleted_at is not None and p.phone == "+998900000042"
    assert db.query(ParentChild).filter(ParentChild.parent_id == parent_id).count() == 1
    assert db.query(ParentNotification).filter(ParentNotification.parent_id == parent_id).count() == 1
    assert db.query(ParentRefreshToken).filter(ParentRefreshToken.parent_id == parent_id).count() == 0
    # Sessiyalar bekor
    assert client.get("/parent/profile", headers=auth).status_code == 401
    assert client.post("/parent/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401
    assert client.delete("/parent/account", headers=auth).status_code == 401
    # Kirish: "mavjud emas" xabari
    r = _login(client, "+998900000042")
    assert r.status_code == 401 and r.json()["code"] == "account_not_found"
    assert "administrator" in r.json()["message"]
    # Boshqa ota-onalarga ta'sir yo'q
    other = _mk_parent(db, [_mk_student(db, "Boshqa", "+998900000043")], phone="+998900000044")
    assert _login(client, "+998900000044").status_code == 200


def test_admin_recreate_restores_deleted_parent(client, db, hunter_user):
    student = _mk_student(db, "Malika Mominova", "+998900000051")
    parent = _mk_parent(db, [student], phone="+998900000052")
    h = _h(client, "+998900000052")
    assert client.delete("/parent/account", headers=h).status_code == 204
    htoken = client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]
    res = client.post("/parents", headers={"Authorization": f"Bearer {htoken}"},
                      json={"full_name": "Malika onasi", "phone": "+998900000052", "student_ids": [student.id]})
    assert res.status_code == 201, res.text
    assert res.json()["id"] == parent.id                                      # yangi emas — tiklangan
    assert len(res.json()["children"]) == 1
    r = _login(client, "+998900000052", res.json()["generated_password"])
    assert r.status_code == 200, r.text


# ── Swift/CRM wire contract and public App Store privacy URL ──────────────────

def test_public_parent_privacy_html_needs_no_login(client):
    res = client.get("/parent/privacy.html")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Minar Parents" in res.text
    assert 'lang="uz"' in res.text
    assert 'lang="ru"' in res.text
    assert 'lang="en"' in res.text
    assert "minaracademy.uz" in res.text


def test_parent_app_capabilities_fail_closed_until_payments_ready(client, db, monkeypatch):
    for k in ("PAYME_MERCHANT_ID", "PAYME_KEY", "CLICK_SERVICE_ID", "CLICK_MERCHANT_ID",
              "CLICK_SECRET_KEY", "UZUM_SERVICE_ID", "UZUM_LOGIN", "UZUM_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert client.get("/parent/app-config").status_code == 401
    student = _mk_student(db, "Config student", "+998900000071")
    _mk_parent(db, [student])
    h = _h(client)
    res = client.get("/parent/app-config", headers=h)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "payments_enabled": False,
        "payment_providers": [],
        "account_deletion_enabled": False,
        "privacy_policy_url": "https://crm.minaracademy.uz/api/parent/privacy.html",
    }


def test_parent_app_capabilities_list_configured_providers(client, db, providers):
    student = _mk_student(db, "Config student", "+998900000071")
    _mk_parent(db, [student])
    flags = client.get("/parent/app-config", headers=_h(client)).json()
    assert flags["payments_enabled"] is True
    assert flags["payment_providers"] == ["payme", "click", "uzum"]


def test_payments_master_switch_off_closes_checkout(client, db, providers, monkeypatch):
    monkeypatch.setenv("PARENT_PAYMENTS_ENABLED", "false")
    s = _mk_student(db, "Switch student", "+998900000074")
    g = _mk_group(db, "Switch G-1")
    _enroll(db, g, s)
    _mk_parent(db, [s])
    h = _h(client)
    flags = client.get("/parent/app-config", headers=h).json()
    assert flags["payments_enabled"] is False and flags["payment_providers"] == []
    r = _pay(client, h, s.id, g.id)
    assert r.status_code == 503 and r.json()["code"] == "payment_provider_unavailable"
    assert db.query(ParentInvoice).count() == 0


def test_account_deletion_flag_follows_env(client, db, monkeypatch):
    from backend.parent import router_parent
    monkeypatch.setattr(router_parent, "ACCOUNT_DELETION_ENABLED", True)
    s = _mk_student(db, "Flag student", "+998900000075")
    _mk_parent(db, [s])
    assert client.get("/parent/app-config", headers=_h(client)).json()["account_deletion_enabled"] is True


def test_unmarked_attendance_not_counted_as_absence(client, db, hunter_user):
    student = _mk_student(db, "Attend student", "+998900000072")
    group = _mk_group(db, "Attendance G-17")
    _enroll(db, group, student)
    db.add(Attendance(group_id=group.id, student_id=student.id,
                      lesson_date=date(2026, 10, 1), is_present=None))
    db.add(Attendance(group_id=group.id, student_id=student.id,
                      lesson_date=date(2026, 10, 2), is_present=True))
    db.commit()
    _mk_parent(db, [student], phone="+998901112233")
    h = _h(client)
    result = client.get(
        f"/parent/children/{student.id}/attendance?month=10&year=2026",
        headers=h,
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["percent"] == 100
    assert len(payload["records"]) == 1
    assert payload["records"][0]["is_present"] is True


# ── App Store review akkaunti: seed → 700 000 qarz → Payme → yangilangan balans ──

def test_review_account_seed_and_payme_flow(client, db, providers, monkeypatch):
    from backend.scripts.seed_review_account import seed
    for k, v in {"PARENT_REVIEW_PHONE": "+998900000777", "PARENT_REVIEW_OTP": "4321",
                 "PARENT_REVIEW_PAYMENT_PROVIDERS": "payme", "PARENT_PAYMENTS_ENABLED": "false"}.items():
        monkeypatch.setenv(k, v)
    assert seed(db, "+998900000777").startswith("CREATED")
    assert seed(db, "+998900000777").startswith("EXISTS")          # idempotent

    r = client.post("/parent/auth/login", json={"username": "900000777", "password": "4321"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cfg = client.get("/parent/app-config", headers=h).json()
    assert cfg["payments_enabled"] is True and cfg["payment_providers"] == ["payme"]

    kids = client.get("/parent/children", headers=h).json()
    assert len(kids) == 1 and kids[0]["full_name"].startswith("TEST — App Review")
    sid = kids[0]["id"]
    m, y = _now()
    for part in ("attendance", "schedule", "grades", "homework", "feedback", "certificates", "teacher"):
        q = f"?month={m}&year={y}" if part == "attendance" else ""
        assert client.get(f"/parent/children/{sid}/{part}{q}", headers=h).status_code == 200, part
    summ = _summary(client, h, sid).json()
    assert summ["debt"] == 700000 and summ["payment_status"] == "debtor", summ
    gid = summ["groups"][0]["group_id"]

    assert _pay(client, h, sid, gid, amount=700000, provider="click").status_code == 503
    res = _pay(client, h, sid, gid, amount=700000)
    assert res.status_code == 200, res.text
    inv = db.query(ParentInvoice).filter_by(student_id=sid).one()
    acc = {"invoice_id": str(inv.id)}
    assert _payme(client, "CheckPerformTransaction", {"amount": 70000000, "account": acc}).json()["result"] == {"allow": True}
    created = _payme(client, "CreateTransaction", {"id": "rv-1", "time": 1, "amount": 70000000, "account": acc}).json()
    assert created["result"]["state"] == 1
    assert _summary(client, h, sid).json()["debt"] == 700000      # callback'siz qarz o'zgarmaydi
    assert _payme(client, "PerformTransaction", {"id": "rv-1"}).json()["result"]["state"] == 2
    summ = _summary(client, h, sid).json()
    assert summ["debt"] == 0 and summ["payment_status"] == "paid"
    assert summ["recent_payments"][0]["amount"] == 700000

    # Oddiy ota-onalar uchun to'lov hali ham o'chiq
    other = _mk_student(db, "Oddiy", "+998900000779")
    _mk_parent(db, [other])
    assert client.get("/parent/app-config", headers=_h(client)).json()["payment_providers"] == []

