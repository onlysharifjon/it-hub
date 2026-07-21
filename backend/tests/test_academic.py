"""Akademik CRM testlari — baholar, izohlar, sertifikatlar, tadbirlar (rol va scoping)."""
from datetime import datetime

import pytest

from backend.models import Student, Group, GroupStudent, UserRole
from .conftest import _create_user


@pytest.fixture
def admin_user(db):
    return _create_user(db, "admin", "admin123", UserRole.admin)


@pytest.fixture
def teacher_user(db):
    return _create_user(db, "ustoz", "ustoz123", UserRole.teacher)


@pytest.fixture
def hunter_user(db):
    return _create_user(db, "hunter", "hunter123", UserRole.hunter)


def _token(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]


def _h(client, username, password):
    return {"Authorization": f"Bearer {_token(client, username, password)}"}


def _mk_student(db, name="Alibek Mominov", phone="+998900000001"):
    s = Student(full_name=name, phone1=phone, is_active=True, created_at=datetime.utcnow())
    db.add(s); db.commit(); db.refresh(s)
    return s


def _mk_group(db, name="Frontend G-101", teacher_id=None):
    g = Group(name=name, stage="frontend", course_price=450000, teacher_id=teacher_id,
              is_active=True, created_at=datetime.utcnow())
    db.add(g); db.commit(); db.refresh(g)
    return g


def _enroll(db, group, student):
    db.add(GroupStudent(group_id=group.id, student_id=student.id, joined_at=datetime.utcnow()))
    db.commit()


# ── Baholar ──────────────────────────────────────────────────────────────────

def test_teacher_creates_grade_own_group(client, db, teacher_user):
    student = _mk_student(db)
    group = _mk_group(db, teacher_id=teacher_user.id)
    _enroll(db, group, student)
    h = _h(client, "ustoz", "ustoz123")

    res = client.post("/grades", headers=h, json={
        "student_id": student.id, "group_id": group.id,
        "subject": "JavaScript Basics", "score": 85, "max_score": 100, "exam_type": "test",
    })
    assert res.status_code == 201, res.text
    assert res.json()["score"] == 85 and res.json()["student_name"] == student.full_name

    rows = client.get("/grades", headers=h).json()
    assert len(rows) == 1


def test_teacher_cannot_grade_foreign_group(client, db, teacher_user):
    other_teacher = _create_user(db, "ustoz2", "ustoz123", UserRole.teacher)
    student = _mk_student(db)
    foreign = _mk_group(db, name="Begona guruh", teacher_id=other_teacher.id)
    _enroll(db, foreign, student)
    h = _h(client, "ustoz", "ustoz123")

    # Begona guruhga baho qo'yish — 403
    res = client.post("/grades", headers=h, json={
        "student_id": student.id, "group_id": foreign.id, "subject": "X", "score": 50})
    assert res.status_code == 403

    # Guruhsiz baho — teacher uchun 400
    res = client.post("/grades", headers=h, json={
        "student_id": student.id, "subject": "X", "score": 50})
    assert res.status_code == 400

    # Boshqa o'qituvchi qo'ygan baho teacher ro'yxatida ko'rinmaydi
    h2 = _h(client, "ustoz2", "ustoz123")
    client.post("/grades", headers=h2, json={
        "student_id": student.id, "group_id": foreign.id, "subject": "Dart", "score": 90})
    assert client.get("/grades", headers=h).json() == []
    assert len(client.get("/grades", headers=h2).json()) == 1


def test_grade_score_validation_and_update(client, db, admin_user):
    student = _mk_student(db)
    h = _h(client, "admin", "admin123")

    assert client.post("/grades", headers=h, json={
        "student_id": student.id, "subject": "X", "score": 120, "max_score": 100}).status_code == 400

    gid = client.post("/grades", headers=h, json={
        "student_id": student.id, "subject": "X", "score": 70}).json()["id"]
    res = client.patch(f"/grades/{gid}", headers=h, json={"score": 95, "comment": "Qayta topshirdi"})
    assert res.status_code == 200 and res.json()["score"] == 95

    assert client.delete(f"/grades/{gid}", headers=h).status_code == 204
    assert client.get("/grades", headers=h).json() == []


def test_grade_creates_parent_notification(client, db, admin_user, hunter_user):
    student = _mk_student(db)
    acct = client.post("/parents", headers=_h(client, "hunter", "hunter123"),
                       json={"full_name": "Ona", "phone": "+998901112233", "student_ids": [student.id]}).json()
    client.post("/grades", headers=_h(client, "admin", "admin123"), json={
        "student_id": student.id, "subject": "Dart Basics", "score": 85})

    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    notifs = client.get("/parent/notifications", headers={"Authorization": f"Bearer {ptoken}"}).json()
    assert any("Dart Basics" in n["title"] for n in notifs)
    # Ota-ona ilovasida baho ko'rinadi
    grades = client.get(f"/parent/children/{student.id}/grades",
                        headers={"Authorization": f"Bearer {ptoken}"}).json()
    assert grades[0]["subject"] == "Dart Basics"


# ── Izohlar ──────────────────────────────────────────────────────────────────

def test_feedback_crud_and_teacher_ownership(client, db, admin_user, teacher_user):
    student = _mk_student(db)
    group = _mk_group(db, teacher_id=teacher_user.id)
    _enroll(db, group, student)
    th = _h(client, "ustoz", "ustoz123")
    ah = _h(client, "admin", "admin123")

    fid = client.post("/teacher-feedbacks", headers=th, json={
        "student_id": student.id, "group_id": group.id, "comment": "Yaxshi o'zlashtiryapti"}).json()["id"]

    # Admin izohi — teacher uni tahrirlay olmaydi
    fid_admin = client.post("/teacher-feedbacks", headers=ah, json={
        "student_id": student.id, "group_id": group.id, "comment": "Admin izohi"}).json()["id"]
    assert client.patch(f"/teacher-feedbacks/{fid_admin}", headers=th,
                        json={"comment": "hack"}).status_code == 403
    assert client.delete(f"/teacher-feedbacks/{fid_admin}", headers=th).status_code == 403

    # O'zinikini tahrirlaydi va o'chiradi
    res = client.patch(f"/teacher-feedbacks/{fid}", headers=th, json={"comment": "Yangilangan izoh"})
    assert res.status_code == 200 and res.json()["comment"] == "Yangilangan izoh"
    assert client.delete(f"/teacher-feedbacks/{fid}", headers=th).status_code == 204


# ── Sertifikatlar ────────────────────────────────────────────────────────────

def test_certificates_lms_write_only(client, db, admin_user, teacher_user):
    student = _mk_student(db)
    ah = _h(client, "admin", "admin123")
    th = _h(client, "ustoz", "ustoz123")

    # Teacher sertifikat bera olmaydi
    assert client.post("/certificates", headers=th, json={
        "student_id": student.id, "title": "Sertifikat", "file_url": "https://x.uz/c.pdf"}).status_code == 403

    cid = client.post("/certificates", headers=ah, json={
        "student_id": student.id, "title": "Foundation sertifikati",
        "file_url": "https://x.uz/c.pdf", "issued_at": "2026-06-01"}).json()["id"]
    res = client.patch(f"/certificates/{cid}", headers=ah, json={"title": "Frontend sertifikati"})
    assert res.status_code == 200 and res.json()["title"] == "Frontend sertifikati"
    assert client.delete(f"/certificates/{cid}", headers=ah).status_code == 204


def test_certificate_pdf_upload_and_file_cleanup(client, db, admin_user):
    import os
    from backend.main import CERTIFICATES_DIR

    student = _mk_student(db)
    h = _h(client, "admin", "admin123")
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    # Yuklash
    res = client.post("/certificates/upload", headers=h,
                      files={"file": ("cert.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    file_url = res.json()["file_url"]
    assert file_url.startswith("https://") and "/uploads/certificates/" in file_url
    filename = file_url.rsplit("/", 1)[-1]
    assert os.path.exists(os.path.join(CERTIFICATES_DIR, filename))

    # PDF bo'lmagan fayl — 400 (content-type application/pdf bo'lsa ham)
    res = client.post("/certificates/upload", headers=h,
                      files={"file": ("fake.pdf", b"<html>xss</html>", "application/pdf")})
    assert res.status_code == 400

    # Sertifikat yaratamiz, o'chirsak fayl ham o'chadi
    cid = client.post("/certificates", headers=h, json={
        "student_id": student.id, "title": "Foundation", "file_url": file_url}).json()["id"]
    assert client.delete(f"/certificates/{cid}", headers=h).status_code == 204
    assert not os.path.exists(os.path.join(CERTIFICATES_DIR, filename))


def test_certificate_upload_forbidden_for_teacher(client, db, teacher_user):
    res = client.post("/certificates/upload", headers=_h(client, "ustoz", "ustoz123"),
                      files={"file": ("c.pdf", b"%PDF-1.4", "application/pdf")})
    assert res.status_code == 403


def test_certificate_update_replaces_local_file(client, db, admin_user):
    import os
    from backend.main import CERTIFICATES_DIR

    student = _mk_student(db)
    h = _h(client, "admin", "admin123")
    up = lambda: client.post("/certificates/upload", headers=h,
                             files={"file": ("c.pdf", b"%PDF-1.4 test", "application/pdf")}).json()["file_url"]
    url1, url2 = up(), up()
    f1, f2 = url1.rsplit("/", 1)[-1], url2.rsplit("/", 1)[-1]

    cid = client.post("/certificates", headers=h, json={
        "student_id": student.id, "title": "Cert", "file_url": url1}).json()["id"]
    client.patch(f"/certificates/{cid}", headers=h, json={"file_url": url2})

    # Eski fayl o'chirilgan, yangisi joyida
    assert not os.path.exists(os.path.join(CERTIFICATES_DIR, f1))
    assert os.path.exists(os.path.join(CERTIFICATES_DIR, f2))
    # Toza qoldiramiz
    client.delete(f"/certificates/{cid}", headers=h)


# ── Tadbirlar ────────────────────────────────────────────────────────────────

def test_events_admin_writes_others_read(client, db, admin_user, teacher_user):
    ah = _h(client, "admin", "admin123")
    th = _h(client, "ustoz", "ustoz123")

    assert client.post("/events", headers=th, json={
        "title": "Tadbir", "event_date": "2026-08-01T10:00:00"}).status_code == 403

    eid = client.post("/events", headers=ah, json={
        "title": "Ochiq eshiklar kuni", "event_date": "2026-08-01T10:00:00",
        "location": "Asosiy bino"}).json()["id"]

    # Teacher o'qiy oladi
    events = client.get("/events", headers=th).json()
    assert events[0]["title"] == "Ochiq eshiklar kuni"

    # Yashirish → ota-ona ilovasida ko'rinmaydi
    client.patch(f"/events/{eid}", headers=ah, json={"is_active": False})
    assert client.get("/events", headers=ah).json()[0]["is_active"] is False

    assert client.delete(f"/events/{eid}", headers=ah).status_code == 204


# ── Options ──────────────────────────────────────────────────────────────────

def test_academic_options_scoped_for_teacher(client, db, admin_user, teacher_user):
    other_teacher = _create_user(db, "ustoz2", "ustoz123", UserRole.teacher)
    s1 = _mk_student(db, "Birinchi", "+998900000031")
    s2 = _mk_student(db, "Ikkinchi", "+998900000032")
    mine = _mk_group(db, name="Mening guruhim", teacher_id=teacher_user.id)
    foreign = _mk_group(db, name="Begona", teacher_id=other_teacher.id)
    _enroll(db, mine, s1)
    _enroll(db, foreign, s2)

    opts = client.get("/academic/options", headers=_h(client, "ustoz", "ustoz123")).json()
    assert [o["group_name"] for o in opts] == ["Mening guruhim"]
    assert [s["full_name"] for s in opts[0]["students"]] == ["Birinchi"]

    opts_admin = client.get("/academic/options", headers=_h(client, "admin", "admin123")).json()
    assert len(opts_admin) == 2


# ── Coinlar ──────────────────────────────────────────────────────────────────

def test_teacher_coin_budget_50_per_student(client, db, teacher_user):
    group = _mk_group(db, teacher_id=teacher_user.id)
    s1 = _mk_student(db, "Birinchi bola", "+998900000041")
    s2 = _mk_student(db, "Ikkinchi bola", "+998900000042")
    _enroll(db, group, s1); _enroll(db, group, s2)
    h = _h(client, "ustoz", "ustoz123")

    # Budjet = 2 talaba × 50 = 100
    s = client.get("/coins/summary", headers=h).json()
    assert s["budget"] == 100 and s["spent"] == 0 and s["remaining"] == 100

    # 60 coin beramiz — qoldiq 40
    res = client.post("/coins/give", headers=h, json={
        "student_id": s1.id, "group_id": group.id, "amount": 60, "reason": "Faol qatnashdi"})
    assert res.status_code == 201, res.text
    s = client.get("/coins/summary", headers=h).json()
    assert s["spent"] == 60 and s["remaining"] == 40

    # 41 coin — budjetdan oshadi -> 400
    res = client.post("/coins/give", headers=h, json={
        "student_id": s2.id, "group_id": group.id, "amount": 41})
    assert res.status_code == 400
    assert "qoldiq 40" in res.json()["detail"]

    # 40 coin — bo'ladi, qoldiq 0
    assert client.post("/coins/give", headers=h, json={
        "student_id": s2.id, "group_id": group.id, "amount": 40}).status_code == 201
    assert client.get("/coins/summary", headers=h).json()["remaining"] == 0


def test_coin_budget_resets_next_month(client, db, teacher_user):
    from datetime import timedelta
    from backend.models import CoinTransaction

    group = _mk_group(db, teacher_id=teacher_user.id)
    s1 = _mk_student(db, "Bola", "+998900000043")
    _enroll(db, group, s1)

    # O'tgan oyda budjet to'liq sarflangan deb yozamiz
    now = datetime.utcnow()
    prev = now.replace(day=1) - timedelta(days=1)
    db.add(CoinTransaction(student_id=s1.id, teacher_id=teacher_user.id,
                           group_id=group.id, amount=50, created_at=prev))
    db.commit()

    # Joriy oy — qoldiq to'liq (1 talaba × 50)
    h = _h(client, "ustoz", "ustoz123")
    s = client.get("/coins/summary", headers=h).json()
    assert s["spent"] == 0 and s["remaining"] == 50


def test_coin_teacher_foreign_group_forbidden(client, db, teacher_user):
    other = _create_user(db, "ustoz3", "ustoz123", UserRole.teacher)
    group = _mk_group(db, name="Begona", teacher_id=other.id)
    s1 = _mk_student(db, "Bola", "+998900000044")
    _enroll(db, group, s1)
    res = client.post("/coins/give", headers=_h(client, "ustoz", "ustoz123"),
                      json={"student_id": s1.id, "group_id": group.id, "amount": 10})
    assert res.status_code == 403


def test_admin_coins_unlimited_and_parent_sees(client, db, admin_user, hunter_user):
    student = _mk_student(db, "Bola", "+998900000045")
    ah = _h(client, "admin", "admin123")

    # Admin uchun budjet cheksiz
    s = client.get("/coins/summary", headers=ah).json()
    assert s["budget"] is None and s["remaining"] is None

    acct = client.post("/parents", headers=_h(client, "hunter", "hunter123"),
                       json={"full_name": "Ona", "phone": "+998901112255",
                             "student_ids": [student.id]}).json()

    client.post("/coins/give", headers=ah, json={
        "student_id": student.id, "amount": 500, "reason": "Olimpiada g'olibi"})

    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    ph = {"Authorization": f"Bearer {ptoken}"}

    coins = client.get(f"/parent/children/{student.id}/coins", headers=ph).json()
    assert coins["total"] == 500
    assert coins["recent"][0]["reason"] == "Olimpiada g'olibi"

    notifs = client.get("/parent/notifications", headers=ph).json()
    assert any("coin" in n["title"] for n in notifs)

    # Reyting
    totals = client.get("/coins/totals", headers=ah).json()
    assert totals[0]["student_name"] == "Bola" and totals[0]["total"] == 500


def test_admin_deduct_coins(client, db, admin_user, teacher_user, hunter_user):
    student = _mk_student(db, "Bola", "+998900000046")
    ah = _h(client, "admin", "admin123")

    client.post("/coins/give", headers=ah, json={"student_id": student.id, "amount": 100})

    # Teacher yechay olmaydi
    assert client.post("/coins/deduct", headers=_h(client, "ustoz", "ustoz123"),
                       json={"student_id": student.id, "amount": 10}).status_code == 403

    # Balansdan ko'p yechib bo'lmaydi
    res = client.post("/coins/deduct", headers=ah, json={"student_id": student.id, "amount": 101})
    assert res.status_code == 400 and "100 coin bor" in res.json()["detail"]

    # 30 yechamiz — jami 70
    res = client.post("/coins/deduct", headers=ah, json={
        "student_id": student.id, "amount": 30, "reason": "Intizom"})
    assert res.status_code == 201 and res.json()["amount"] == -30
    totals = client.get("/coins/totals", headers=ah).json()
    row = next(t for t in totals if t["student_id"] == student.id)
    assert row["total"] == 70

    # Ota-ona ilovasida ham 70 va yechilgan yozuv ko'rinadi
    acct = client.post("/parents", headers=_h(client, "hunter", "hunter123"),
                       json={"full_name": "Ona", "phone": "+998901112266",
                             "student_ids": [student.id]}).json()
    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    coins = client.get(f"/parent/children/{student.id}/coins",
                       headers={"Authorization": f"Bearer {ptoken}"}).json()
    assert coins["total"] == 70
    assert coins["recent"][0]["amount"] == -30
