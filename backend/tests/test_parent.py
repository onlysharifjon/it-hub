"""Ota-ona API testlari — auth, ownership, to'lov hisobi, bildirishnoma, akademik."""
from datetime import datetime, date, timedelta

import pytest

from backend.models import (
    Student, Group, GroupStudent, Payment, UserRole,
    Grade, Homework, HomeworkSubmission, TeacherFeedback, Event, Certificate,
)
from .conftest import _create_user


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return _create_user(db, "admin", "admin123", UserRole.admin)


@pytest.fixture
def hunter_user(db):
    return _create_user(db, "hunter", "hunter123", UserRole.hunter)


def _mk_student(db, name="Alibek Mominov", phone="+998900000001"):
    s = Student(full_name=name, phone1=phone, is_active=True, created_at=datetime.utcnow())
    db.add(s); db.commit(); db.refresh(s)
    return s


def _mk_group(db, name="Frontend G-101", price=450000):
    g = Group(name=name, stage="frontend", course_price=price, is_active=True, created_at=datetime.utcnow())
    db.add(g); db.commit(); db.refresh(g)
    return g


def _enroll(db, group, student):
    db.add(GroupStudent(group_id=group.id, student_id=student.id, joined_at=datetime.utcnow()))
    db.commit()


def _admin_token(client):
    return client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]


def _hunter_token(client):
    return client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]


def _create_parent(client, hunter_token, student_ids, phone="+998901112233"):
    res = client.post(
        "/parents",
        headers={"Authorization": f"Bearer {hunter_token}"},
        json={"full_name": "Nodira Mominova", "phone": phone, "student_ids": student_ids},
    )
    assert res.status_code == 201, res.text
    return res.json()


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_hunter_creates_parent_and_parent_logs_in(client, db, hunter_user):
    student = _mk_student(db)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    assert acct["username"] == "+998901112233"
    assert acct["generated_password"]
    assert [c["student_id"] for c in acct["children"]] == [student.id]

    res = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]})
    assert res.status_code == 200
    assert res.json()["access_token"] and res.json()["refresh_token"]


def test_parent_login_wrong_password(client, db, hunter_user):
    student = _mk_student(db)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    res = client.post("/parent/auth/login", json={"username": acct["username"], "password": "wrong"})
    assert res.status_code == 401


def test_refresh_rotation_and_reuse_detection(client, db, hunter_user):
    student = _mk_student(db)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    login = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()
    old_refresh = login["refresh_token"]

    # Rotatsiya: eski token yangi juftga almashadi
    r1 = client.post("/parent/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]

    # Eski tokenni qayta ishlatish -> 401 (o'g'irlik alomati)
    reuse = client.post("/parent/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401

    # Oila bekor qilingani uchun rotatsiyalangan token ham ishlamaydi
    after = client.post("/parent/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


# ── Ownership (kritik) ───────────────────────────────────────────────────────

def test_parent_cannot_access_unlinked_child(client, db, hunter_user):
    mine = _mk_student(db, "Mening bolam", "+998900000010")
    other = _mk_student(db, "Begona bola", "+998900000011")
    acct = _create_parent(client, _hunter_token(client), [mine.id])
    token = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/parent/children/{mine.id}/payment-summary", headers=h).status_code == 200
    # Begona bola -> 404 (403 emas — enumeration'dan himoya)
    assert client.get(f"/parent/children/{other.id}/payment-summary", headers=h).status_code == 404
    assert client.get(f"/parent/children/{other.id}/attendance", headers=h).status_code == 404
    assert client.get(f"/parent/children/{other.id}/schedule", headers=h).status_code == 404


# ── Akademik endpointlar ─────────────────────────────────────────────────────

def _parent_headers(client, db, hunter_user, student):
    acct = _create_parent(client, _hunter_token(client), [student.id])
    token = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_grades_homework_feedback_certificates(client, db, hunter_user):
    teacher = _create_user(db, "ustoz", "ustoz123", UserRole.teacher)
    teacher.full_name = "Asilbek Omonov"
    student = _mk_student(db)
    group = _mk_group(db)
    group.teacher_id = teacher.id
    _enroll(db, group, student)

    db.add(Grade(student_id=student.id, group_id=group.id, subject="Dart Basics",
                 score=85, max_score=100, exam_type="exam", exam_date=date(2026, 7, 1)))
    hw = Homework(group_id=group.id, lesson_title="Todo App", text="Todo ilova yasang",
                  lesson_date=date(2026, 7, 5), due_date=date(2026, 7, 8))
    db.add(hw); db.flush()
    db.add(HomeworkSubmission(homework_id=hw.id, student_id=student.id,
                              status="graded", grade=90, submitted_at=datetime.utcnow()))
    db.add(TeacherFeedback(student_id=student.id, group_id=group.id, teacher_id=teacher.id,
                           comment="Yaxshi o'zlashtiryapti"))
    db.add(Certificate(student_id=student.id, title="Foundation sertifikati",
                       file_url="https://example.com/cert.pdf", issued_at=date(2026, 6, 1)))
    db.commit()

    h = _parent_headers(client, db, hunter_user, student)

    grades = client.get(f"/parent/children/{student.id}/grades", headers=h).json()
    assert len(grades) == 1
    assert grades[0]["subject"] == "Dart Basics" and grades[0]["score"] == 85
    assert grades[0]["date"] == "2026-07-01"

    hws = client.get(f"/parent/children/{student.id}/homework", headers=h).json()
    assert len(hws) == 1
    assert hws[0]["title"] == "Todo App" and hws[0]["status"] == "graded"
    assert hws[0]["grade"] == 90 and hws[0]["due_date"] == "2026-07-08"

    fb = client.get(f"/parent/children/{student.id}/feedback", headers=h).json()
    assert len(fb) == 1
    assert fb[0]["teacher_name"] == "Asilbek Omonov"
    assert fb[0]["comment"] == "Yaxshi o'zlashtiryapti"

    certs = client.get(f"/parent/children/{student.id}/certificates", headers=h).json()
    assert len(certs) == 1
    assert certs[0]["file_url"].endswith(".pdf")


def test_homework_without_submission_is_pending(client, db, hunter_user):
    student = _mk_student(db)
    group = _mk_group(db)
    _enroll(db, group, student)
    db.add(Homework(group_id=group.id, lesson_title="Kalkulyator", text="Kalkulyator yasang",
                    lesson_date=date(2026, 7, 6)))
    db.commit()

    h = _parent_headers(client, db, hunter_user, student)
    hws = client.get(f"/parent/children/{student.id}/homework", headers=h).json()
    assert hws[0]["status"] == "pending" and hws[0]["grade"] is None


def test_teacher_contact(client, db, hunter_user):
    teacher = _create_user(db, "ustoz2", "ustoz123", UserRole.teacher)
    teacher.full_name = "Asilbek Omonov"
    teacher.phone = "+998935551122"
    teacher.telegram = "@asilbek"
    student = _mk_student(db)
    group = _mk_group(db)
    group.teacher_id = teacher.id
    _enroll(db, group, student)
    db.commit()

    h = _parent_headers(client, db, hunter_user, student)
    t = client.get(f"/parent/children/{student.id}/teacher", headers=h)
    assert t.status_code == 200
    body = t.json()
    assert body["name"] == "Asilbek Omonov"
    assert body["phone"] == "+998935551122" and body["telegram"] == "@asilbek"


def test_teacher_contact_missing_returns_404(client, db, hunter_user):
    student = _mk_student(db)
    group = _mk_group(db)   # o'qituvchisiz guruh
    _enroll(db, group, student)
    h = _parent_headers(client, db, hunter_user, student)
    assert client.get(f"/parent/children/{student.id}/teacher", headers=h).status_code == 404


def test_events_visible_to_parent(client, db, hunter_user):
    student = _mk_student(db)
    db.add(Event(title="Ochiq eshiklar kuni", description="Tanishuv",
                 event_date=datetime.utcnow() + timedelta(days=5), location="Asosiy bino"))
    db.add(Event(title="Yashirin", event_date=datetime.utcnow(), is_active=False))
    db.commit()

    h = _parent_headers(client, db, hunter_user, student)
    events = client.get("/parent/events", headers=h).json()
    assert [e["title"] for e in events] == ["Ochiq eshiklar kuni"]


def test_academic_endpoints_ownership(client, db, hunter_user):
    mine = _mk_student(db, "Mening bolam", "+998900000020")
    other = _mk_student(db, "Begona bola", "+998900000021")
    h = _parent_headers(client, db, hunter_user, mine)
    for path in ("grades", "homework", "feedback", "teacher", "certificates"):
        assert client.get(f"/parent/children/{other.id}/{path}", headers=h).status_code == 404


def test_patch_profile(client, db, hunter_user):
    student = _mk_student(db)
    h = _parent_headers(client, db, hunter_user, student)

    res = client.patch("/parent/profile", headers=h,
                       json={"display_name": "Nodira xonim", "avatar_base64": "aGVsbG8="})
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == "Nodira xonim" and body["avatar"] == "aGVsbG8="

    # GET /profile ham yangilangan qiymatlarni qaytaradi
    prof = client.get("/parent/profile", headers=h).json()
    assert prof["display_name"] == "Nodira xonim" and prof["avatar"] == "aGVsbG8="

    # Bo'sh ism — 422
    assert client.patch("/parent/profile", headers=h,
                        json={"display_name": "   "}).status_code == 422


# ── To'lov hisobi ────────────────────────────────────────────────────────────

def test_payment_summary_debtor_partial_paid(client, db, admin_user, hunter_user):
    student = _mk_student(db)
    group = _mk_group(db, price=450000)
    _enroll(db, group, student)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    ph = {"Authorization": f"Bearer {ptoken}"}
    now = datetime.utcnow()

    # Boshida: qarzdor
    s = client.get(f"/parent/children/{student.id}/payment-summary?month={now.month}&year={now.year}", headers=ph).json()
    assert s["total_owed"] == 450000 and s["debt"] == 450000
    assert s["payment_status"] == "debtor"

    # Qisman to'lov (hunter orqali)
    htoken = _hunter_token(client)
    client.post("/payments", headers={"Authorization": f"Bearer {htoken}"},
                json={"student_id": student.id, "group_id": group.id,
                      "amount": 200000, "month": now.month, "year": now.year, "notes": "Naqd"})
    s = client.get(f"/parent/children/{student.id}/payment-summary?month={now.month}&year={now.year}", headers=ph).json()
    assert s["debt"] == 250000 and s["payment_status"] == "partial"
    assert s["recent_payments"][0]["notes"] == "Naqd"

    # To'liq to'lov
    client.post("/payments", headers={"Authorization": f"Bearer {htoken}"},
                json={"student_id": student.id, "group_id": group.id,
                      "amount": 250000, "month": now.month, "year": now.year})
    s = client.get(f"/parent/children/{student.id}/payment-summary?month={now.month}&year={now.year}", headers=ph).json()
    assert s["debt"] == 0 and s["payment_status"] == "paid"


def test_advance_reduces_debt(client, db, admin_user, hunter_user):
    student = _mk_student(db)
    student.advance_balance = 450000
    db.commit()
    group = _mk_group(db, price=450000)
    _enroll(db, group, student)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    s = client.get(f"/parent/children/{student.id}/payment-summary",
                   headers={"Authorization": f"Bearer {ptoken}"}).json()
    # Avans qarzni to'liq qoplaydi -> paid
    assert s["advance_applied"] == 450000 and s["debt"] == 0
    assert s["payment_status"] == "paid"


# ── Bildirishnoma triggeri ───────────────────────────────────────────────────

def test_payment_creates_parent_notification(client, db, admin_user, hunter_user):
    student = _mk_student(db)
    group = _mk_group(db)
    _enroll(db, group, student)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    now = datetime.utcnow()

    client.post("/payments", headers={"Authorization": f"Bearer {_hunter_token(client)}"},
                json={"student_id": student.id, "group_id": group.id,
                      "amount": 450000, "month": now.month, "year": now.year})

    notifs = client.get("/parent/notifications", headers={"Authorization": f"Bearer {ptoken}"}).json()
    assert len(notifs) == 1
    assert notifs[0]["type"] == "payment"
    assert notifs[0]["is_read"] is False

    # O'qildi deb belgilash
    nid = notifs[0]["id"]
    assert client.post(f"/parent/notifications/{nid}/read",
                       headers={"Authorization": f"Bearer {ptoken}"}).status_code == 204
    notifs = client.get("/parent/notifications", headers={"Authorization": f"Bearer {ptoken}"}).json()
    assert notifs[0]["is_read"] is True
