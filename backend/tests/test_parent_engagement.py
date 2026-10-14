"""Parent engagement contracts and ownership; never contacts payment/APNs providers."""
from datetime import datetime, timedelta
from decimal import Decimal

from pypdf import PdfReader
from io import BytesIO

from backend import tz
from backend.models import (
    Attendance, Grade, Homework, HomeworkSubmission, ParentInvoice, ParentNotification,
    ParentPushDevice, Payment, PaymentTransaction, UserRole,
)
from backend.parent.apns import activation_cutoff, dispatch_batch
from backend.parent.digests import run_daily
from .conftest import _create_user
from .test_parent import _enroll, _h, _mk_group, _mk_parent, _mk_student


def _staff_header(client, db, role=UserRole.hunter):
    _create_user(db, "staff-test", "staffpass", role)
    token = client.post("/auth/login", json={"username": "staff-test", "password": "staffpass"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_push_token_ownership_preferences_and_account_deletion(client, db):
    student = _mk_student(db)
    first = _mk_parent(db, [student])
    h1 = _h(client)
    second = _mk_parent(db, [student], phone="+998909990001")
    h2 = _h(client, second.phone)
    token = "a" * 64
    payload = {"token": token, "platform": "ios", "environment": "sandbox"}
    defaults = client.get("/parent/notification-preferences", headers=h1)
    assert defaults.status_code == 200
    assert all(defaults.json().values())
    assert client.post("/parent/push-devices", json=payload, headers=h1).status_code == 204
    assert db.query(ParentPushDevice).one().parent_id == first.id
    assert client.delete(f"/parent/push-devices/{token}", headers=h2).status_code == 204
    assert db.query(ParentPushDevice).count() == 1
    assert client.patch("/parent/notification-preferences", headers=h1,
                        json={"attendance": False, "teacher_messages": False}).json()["payments"] is True
    prefs = client.get("/parent/notification-preferences", headers=h1).json()
    assert prefs["attendance"] is False and prefs["teacher_messages"] is False
    assert client.patch("/parent/notification-preferences", headers=h1,
                        json={"attendance": None}).status_code == 422
    # Same physical device switched accounts: token now belongs only to new parent.
    assert client.post("/parent/push-devices", json=payload, headers=h2).status_code == 204
    assert db.query(ParentPushDevice).one().parent_id == second.id
    assert client.delete("/parent/account", headers=h2).status_code == 204
    assert db.query(ParentPushDevice).count() == 0


def test_absence_explanation_review_retry_and_child_ownership(client, db):
    child = _mk_student(db)
    other = _mk_student(db, "Other child", "+998900000002")
    _mk_parent(db, [child])
    parent_h = _h(client)
    _mk_parent(db, [other], phone="+998909990002")
    other_h = _h(client, "+998909990002")
    group = _mk_group(db)
    _enroll(db, group, child)
    lesson_date = tz.today() - timedelta(days=1)
    db.add(Attendance(group_id=group.id, student_id=child.id,
                      lesson_date=lesson_date, is_present=False))
    db.commit()
    url = f"/parent/children/{child.id}/absence-explanations"
    body = {"lesson_date": lesson_date.isoformat(), "group_name": group.name,
            "reason": "sick", "note": "Shifokorga bordi"}
    assert client.post(url, headers=other_h, json=body).status_code == 404
    created = client.post(url, headers=parent_h, json=body)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["status"] == "pending" and row["group_name"] == group.name
    assert client.post(url, headers=parent_h, json=body).status_code == 409
    staff_h = _staff_header(client, db)
    review = client.patch(f"/parent-engagement/absence-explanations/{row['id']}",
                          headers=staff_h, json={"status": "rejected", "staff_note": "Aniqlashtiring"})
    assert review.status_code == 200 and review.json()["status"] == "rejected"
    retry = client.post(url, headers=parent_h, json={**body, "note": "Ma'lumotnoma bor"})
    assert retry.status_code == 201 and retry.json()["status"] == "pending"
    assert retry.json()["id"] == row["id"]
    assert client.get(url, headers=other_h).status_code == 404


def test_two_guardians_do_not_read_each_others_private_requests(client, db):
    child = _mk_student(db)
    _mk_parent(db, [child])
    first_h = _h(client)
    _mk_parent(db, [child], phone="+998909990009")
    second_h = _h(client, "+998909990009")
    teacher = _create_user(db, "teacher-private", "teacherpass", UserRole.teacher)
    group = _mk_group(db, teacher=teacher)
    _enroll(db, group, child)
    yesterday = tz.today() - timedelta(days=1)
    db.add(Attendance(group_id=group.id, student_id=child.id,
                      lesson_date=yesterday, is_present=False)); db.commit()
    absence_path = f"/parent/children/{child.id}/absence-explanations"
    first = client.post(absence_path, headers=first_h, json={
        "lesson_date": str(yesterday), "reason": "family", "note": "Private family note",
    })
    assert first.status_code == 201
    assert client.get(absence_path, headers=second_h).json() == []
    second = client.post(absence_path, headers=second_h, json={
        "lesson_date": str(yesterday), "reason": "other", "note": "Second private note",
    })
    assert second.status_code == 201 and second.json()["id"] != first.json()["id"]
    assert len(client.get(absence_path, headers=first_h).json()) == 1
    question_path = f"/parent/children/{child.id}/teacher-questions"
    assert client.post(question_path, headers=first_h, json={
        "subject": "Private", "body": "My own question only",
    }).status_code == 201
    assert client.get(question_path, headers=second_h).json() == []


def test_weekly_summary_uses_real_records_and_staff_recommendation(client, db):
    child = _mk_student(db)
    _mk_parent(db, [child])
    h = _h(client)
    staff_h = _staff_header(client, db)
    group = _mk_group(db)
    _enroll(db, group, child, joined_at=datetime.utcnow() - timedelta(days=15))
    monday = tz.today() - timedelta(days=tz.today().weekday())
    db.add(Attendance(group_id=group.id, student_id=child.id, lesson_date=monday, is_present=True))
    hw = Homework(group_id=group.id, text="Masalalarni ishlang", lesson_date=monday,
                  created_at=datetime.utcnow())
    db.add(hw)
    db.flush()
    db.add(HomeworkSubmission(homework_id=hw.id, student_id=child.id, status="graded"))
    db.add(Grade(student_id=child.id, group_id=group.id, subject="Algebra", score=8,
                 max_score=10, exam_date=monday))
    db.commit()
    path = f"/parent/children/{child.id}/weekly-summary"
    result = client.get(path, headers=h).json()
    assert result["attended_lessons"] == result["scheduled_lessons"] == 1
    assert result["homework_completed"] == result["homework_total"] == 1
    assert result["average_grade"] == 80
    assert result["teacher_recommendation"] is None
    rec = client.put(f"/parent-engagement/students/{child.id}/weekly-recommendations/{monday}",
                     headers=staff_h, json={"text": "Har kuni 15 daqiqa algebra takrorlang."})
    assert rec.status_code == 200, rec.text
    assert "algebra" in client.get(path, headers=h).json()["teacher_recommendation"]


def test_teacher_question_reply_and_child_ownership(client, db):
    child = _mk_student(db)
    other = _mk_student(db, "Other", "+998900000003")
    _mk_parent(db, [child])
    h = _h(client)
    _mk_parent(db, [other], phone="+998909990003")
    other_h = _h(client, "+998909990003")
    teacher = _create_user(db, "teacher-engagement", "teacherpass", UserRole.teacher)
    group = _mk_group(db, teacher=teacher)
    _enroll(db, group, child)
    path = f"/parent/children/{child.id}/teacher-questions"
    body = {"subject": "Vazifa", "body": "Uy vazifasini qanday yuboramiz?"}
    assert client.post(path, headers=other_h, json=body).status_code == 404
    created = client.post(path, headers=h, json=body)
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]
    teacher_token = client.post("/auth/login", json={"username": "teacher-engagement", "password": "teacherpass"}).json()["access_token"]
    staff_h = {"Authorization": f"Bearer {teacher_token}"}
    answer = client.post(f"/parent-engagement/teacher-questions/{question_id}/replies",
                         headers=staff_h, json={"body": "Darsda topshiring."})
    assert answer.status_code == 201, answer.text
    assert answer.json()["status"] == "answered"
    assert answer.json()["replies"][0]["body"] == "Darsda topshiring."
    assert client.get(path, headers=other_h).status_code == 404


def test_unrelated_teacher_cannot_review_reply_or_publish_recommendation(client, db):
    child = _mk_student(db)
    _mk_parent(db, [child])
    parent_h = _h(client)
    first_teacher = _create_user(db, "teacher-allowed", "teacherpass", UserRole.teacher)
    other_teacher = _create_user(db, "teacher-unrelated", "teacherpass", UserRole.teacher)
    group = _mk_group(db, teacher=first_teacher)
    _enroll(db, group, child)
    yesterday = tz.today() - timedelta(days=1)
    db.add(Attendance(group_id=group.id, student_id=child.id,
                      lesson_date=yesterday, is_present=False)); db.commit()
    absence = client.post(f"/parent/children/{child.id}/absence-explanations",
                          headers=parent_h, json={"lesson_date": str(yesterday),
                                                  "reason": "sick", "note": "Shifokor ko‘rdi"})
    assert absence.status_code == 201
    question = client.post(f"/parent/children/{child.id}/teacher-questions",
                           headers=parent_h, json={"subject": "Dars", "body": "Savolim bor"})
    assert question.status_code == 201
    token = client.post("/auth/login", json={
        "username": other_teacher.username, "password": "teacherpass",
    }).json()["access_token"]
    other_h = {"Authorization": f"Bearer {token}"}
    assert client.get("/parent-engagement/students", headers=other_h).json() == []
    assert client.get("/parent-engagement/absence-explanations", headers=other_h).json() == []
    assert client.get("/parent-engagement/teacher-questions", headers=other_h).json() == []
    assert client.patch(f"/parent-engagement/absence-explanations/{absence.json()['id']}",
                        headers=other_h, json={"status": "approved"}).status_code == 403
    assert client.post(f"/parent-engagement/teacher-questions/{question.json()['id']}/replies",
                       headers=other_h, json={"body": "No access"}).status_code == 403
    monday = tz.today() - timedelta(days=tz.today().weekday())
    assert client.put(f"/parent-engagement/students/{child.id}/weekly-recommendations/{monday}",
                      headers=other_h, json={"text": "No access"}).status_code == 403


def test_receipt_requires_verified_invoice_and_same_payer(client, db):
    child = _mk_student(db, name="O‘g‘ilxon Ёқубова")
    _mk_parent(db, [child])
    h = _h(client)
    _mk_parent(db, [child], phone="+998909990004")
    other_h = _h(client, "+998909990004")
    group = _mk_group(db)
    _enroll(db, group, child)
    from backend.models import Parent
    payer = db.query(Parent).filter(Parent.phone == "+998901112233").one()
    now = datetime.utcnow()
    invoice = ParentInvoice(parent_id=payer.id, student_id=child.id, group_id=group.id,
                            amount=700000, provider="payme", status="paid", paid_at=now,
                            created_at=now)
    db.add(invoice)
    db.flush()
    db.add(PaymentTransaction(invoice_id=invoice.id, provider="payme", provider_txn_id="test-txn",
                              state="performed", amount=700000, create_time=1))
    payment = Payment(student_id=child.id, group_id=group.id, amount=700000,
                      month=now.month, year=now.year, paid_at=now, parent_invoice_id=invoice.id)
    manual = Payment(student_id=child.id, group_id=group.id, amount=100000,
                     month=now.month, year=now.year, paid_at=now)
    db.add_all([payment, manual]); db.commit()
    path = f"/parent/children/{child.id}/payment-summary?month={now.month}&year={now.year}"
    rows = client.get(path, headers=h).json()["recent_payments"]
    assert len(rows) == 2
    assert next(r for r in rows if r["amount"] == 700000)["payment_id"] == payment.id
    assert next(r for r in rows if r["amount"] == 100000)["payment_id"] is None
    assert all(r["payment_id"] is None for r in client.get(path, headers=other_h).json()["recent_payments"])
    receipt_path = f"/parent/children/{child.id}/payments/{payment.id}/receipt"
    pdf = client.get(receipt_path, headers=h)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-") and len(pdf.content) < 1_000_000
    extracted = " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "O‘g‘ilxon Ёқубова" in extracted
    assert "test-txn" in extracted
    assert "fiskal yoki soliq cheki emas" in extracted
    assert client.get(receipt_path, headers=other_h).status_code == 404
    assert client.get(f"/parent/children/{child.id}/payments/{manual.id}/receipt", headers=h).status_code == 404
    invoice.status = "refunded"; db.commit()
    assert client.get(receipt_path, headers=h).status_code == 404


def test_apns_payload_contains_no_private_student_details(client, db, monkeypatch):
    child = _mk_student(db, name="Very Private Name")
    parent = _mk_parent(db, [child])
    h = _h(client)
    assert client.post("/parent/push-devices", headers=h, json={
        "token": "b" * 64, "platform": "ios", "environment": "sandbox",
    }).status_code == 204
    db.add(ParentNotification(parent_id=parent.id, student_id=child.id, type="payment",
                              title="Debt 700000", body="Very Private Name owes 700000"))
    db.commit()
    monkeypatch.setenv("PARENT_APNS_TOPIC", "uz.minar.parents")

    class Client:
        payloads = []
        def post(self, url, json, headers):
            self.payloads.append(json)
            class Response:
                status_code = 200
            return Response()

    fake = Client()
    assert dispatch_batch(db, fake, {"sandbox": "test-bearer"}) == 1
    assert fake.payloads[0]["screen"] == "payments"
    assert fake.payloads[0]["child_id"] == child.id
    assert "Very Private Name" not in str(fake.payloads) and "700000" not in str(fake.payloads)


def test_apns_transient_error_retries_with_backoff(client, db, monkeypatch):
    child = _mk_student(db)
    parent = _mk_parent(db, [child])
    h = _h(client)
    client.post("/parent/push-devices", headers=h, json={
        "token": "c" * 64, "platform": "ios", "environment": "sandbox",
    })
    row = ParentNotification(parent_id=parent.id, student_id=child.id,
                             type="attendance", title="Absent", body="Private")
    db.add(row); db.commit()
    monkeypatch.setenv("PARENT_APNS_TOPIC", "uz.minar.parents")

    class Client:
        calls = 0
        def post(self, url, json, headers):
            self.calls += 1
            class Response:
                status_code = 503 if self.calls == 1 else 200
                def json(self): return {"reason": "ServiceUnavailable"}
            return Response()

    fake = Client()
    assert dispatch_batch(db, fake, {"sandbox": "token"}) == 0
    db.refresh(row)
    assert row.push_attempted_at is None and row.push_attempts == 1
    assert row.push_next_attempt_at > datetime.utcnow()
    row.push_next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert dispatch_batch(db, fake, {"sandbox": "token"}) == 1
    db.refresh(row)
    assert row.push_attempted_at is not None and row.push_attempts == 2


def test_apns_activation_cutoff_skips_old_events(client, db, monkeypatch):
    child = _mk_student(db)
    parent = _mk_parent(db, [child])
    h = _h(client)
    assert client.post("/parent/push-devices", headers=h, json={
        "token": "d" * 64, "platform": "ios", "environment": "production",
    }).status_code == 204
    old = ParentNotification(parent_id=parent.id, student_id=child.id,
                             type="attendance", title="Old", body="Old",
                             created_at=datetime.utcnow() - timedelta(minutes=5))
    new = ParentNotification(parent_id=parent.id, student_id=child.id,
                             type="attendance", title="New", body="New",
                             created_at=datetime.utcnow())
    db.add_all([old, new]); db.commit()
    cutoff = datetime.utcnow() - timedelta(minutes=1)
    monkeypatch.setenv("PARENT_PUSH_NOT_BEFORE_UTC", cutoff.isoformat() + "Z")
    monkeypatch.setenv("PARENT_APNS_TOPIC", "uz.minar.parents")
    assert activation_cutoff() == cutoff

    class Client:
        calls = 0
        def post(self, url, json, headers):
            self.calls += 1
            class Response:
                status_code = 200
            return Response()

    fake = Client()
    assert dispatch_batch(db, fake, {"production": "token"}) == 1
    db.refresh(old); db.refresh(new)
    assert fake.calls == 1 and old.push_attempted_at is None
    assert new.push_attempted_at is not None


def test_digest_events_are_opt_in_and_idempotent(client, db, monkeypatch):
    child = _mk_student(db)
    parent = _mk_parent(db, [child])
    group = _mk_group(db)
    _enroll(db, group, child, joined_at=datetime.utcnow() - timedelta(days=15))
    monday = tz.today() - timedelta(days=tz.today().weekday())
    last_monday = monday - timedelta(days=7)
    db.add(Attendance(group_id=group.id, student_id=child.id,
                      lesson_date=last_monday, is_present=True)); db.commit()

    def payment_map(_db, students, _month, _year):
        return {s.id: (Decimal(700000), Decimal(0), Decimal(700000),
                       "debtor", Decimal(0)) for s in students}

    from backend import work_center
    monkeypatch.delenv("PARENT_DIGESTS_ENABLED", raising=False)
    assert run_daily(db, payment_map, today=monday) == 0
    monkeypatch.setenv("PARENT_DIGESTS_ENABLED", "true")
    assert run_daily(db, payment_map, today=monday) == 1
    assert run_daily(db, payment_map, today=monday) == 0
    assert db.query(ParentNotification).filter(
        ParentNotification.parent_id == parent.id,
        ParentNotification.type == "weekly_summary",
    ).count() == 1
    day5 = monday.replace(day=work_center.DEBT_HIGH_DAY)
    assert run_daily(db, payment_map, today=day5) >= 1
    assert run_daily(db, payment_map, today=day5) == 0
    assert db.query(ParentNotification).filter(
        ParentNotification.parent_id == parent.id,
        ParentNotification.type == "payment",
    ).count() == 1
