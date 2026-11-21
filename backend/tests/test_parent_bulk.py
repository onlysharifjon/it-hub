"""CRM: ota-ona akkauntlarini ommaviy yaratish va login/parollarni Excel/PDF qilib yuklab olish."""
import io
from datetime import datetime

import pytest

from backend import security
from backend.models import AuditLog, Parent, ParentChild, Student, UserRole
from .conftest import _create_user


@pytest.fixture
def hunter(db):
    return _create_user(db, "hunter", "hunter123", UserRole.hunter)


def _h(client, username="hunter", password="hunter123"):
    t = client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def _student(db, name, mother=None, mphone=None, father=None, fphone=None):
    s = Student(full_name=name, phone1="+998900000000", is_active=True, created_at=datetime.utcnow(),
                mother_name=mother, mother_phone=mphone, father_name=father, father_phone=fphone)
    db.add(s); db.commit(); db.refresh(s)
    return s


def _bulk(client, h, items):
    return client.post("/parents/bulk", headers=h, json={"items": items})


def test_bulk_creates_accounts_with_name_last4_and_handles_siblings(client, db, hunter):
    a = _student(db, "Alibek Karimov", "nodira", "90 111 22 33")
    b = _student(db, "Bekzod Karimov", "Nodira", "+998901112233")          # aka-uka: o'sha ona
    c = _student(db, "Madina Yusupova", father="akmal yusupov", fphone="935554411")
    h = _h(client)
    r = _bulk(client, h, [{"student_id": a.id, "guardian": "mother"}, {"student_id": b.id, "guardian": "mother"},
                          {"student_id": c.id, "guardian": "father"}])
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert (body["created"], body["linked"], body["skipped"]) == (2, 1, 0)
    ra, rb, rc = body["rows"]
    assert ra["status"] == "created" and ra["password"] == "Nodira2233" and ra["username"] == "+998901112233"
    assert ra["full_name"] == "Nodira"
    assert rb["status"] == "linked" and rb["password"] is None and rb["parent_id"] == ra["parent_id"]
    assert rc["status"] == "created" and rc["full_name"] == "Akmal Yusupov" and rc["password"] == "Akmal4411"
    # Aka-uka bitta akkauntda
    links = {pc.student_id for pc in db.query(ParentChild).filter_by(parent_id=ra["parent_id"])}
    assert links == {a.id, b.id}
    # Ota-ona shu parol bilan kiradi
    login = client.post("/parent/auth/login", json={"username": "+998901112233", "password": "Nodira2233"})
    assert login.status_code == 200
    # Audit — parolsiz
    audits = db.query(AuditLog).filter(AuditLog.entity_type == "parent").all()
    assert {a_.action for a_ in audits} == {"create", "link_child"}
    assert all("Nodira2233" not in f"{x.old_value}{x.new_value}" for x in audits)


def test_bulk_existing_parent_is_linked_without_password_change(client, db, hunter):
    p = Parent(full_name="Nodira Karimova", phone="+998901112233", username="+998901112233",
               hashed_password=security.hash_password("Old-secret-1"), is_active=True, created_at=datetime.utcnow())
    db.add(p); db.commit()
    s = _student(db, "Alibek", "Nodira", "901112233")
    r = _bulk(client, _h(client), [{"student_id": s.id, "guardian": "mother"}]).json()
    assert r["linked"] == 1 and r["rows"][0]["password"] is None
    db.refresh(p)
    assert security.verify_password("Old-secret-1", p.hashed_password)
    again = _bulk(client, _h(client), [{"student_id": s.id, "guardian": "mother"}]).json()
    assert again["skipped"] == 1 and "Allaqachon" in again["rows"][0]["reason"]
    assert db.query(Parent).count() == 1


def test_bulk_skips_missing_name_or_phone(client, db, hunter):
    s1 = _student(db, "A", mother=None, mphone="901112233")
    s2 = _student(db, "B", mother="Nodira", mphone="123")
    r = _bulk(client, _h(client), [{"student_id": s1.id, "guardian": "mother"},
                                  {"student_id": s2.id, "guardian": "mother"},
                                  {"student_id": 99999, "guardian": "father"}]).json()
    assert (r["created"], r["skipped"]) == (0, 3)
    reasons = [row["reason"] for row in r["rows"]]
    assert "Ona ismi" in reasons[0] and "telefoni" in reasons[1] and "topilmadi" in reasons[2]
    assert db.query(Parent).count() == 0


def test_bulk_and_export_require_hunter_or_admin(client, db, hunter):
    _create_user(db, "teach", "teach123", UserRole.teacher)
    h = _h(client, "teach", "teach123")
    assert _bulk(client, h, [{"student_id": 1, "guardian": "mother"}]).status_code == 403
    assert client.post("/parents/credentials-export", headers=h,
                       json={"format": "xlsx", "rows": [{"full_name": "a", "username": "b", "password": "c"}]}).status_code == 403


ROWS = [{"full_name": "Nodira Karimova", "username": "+998901112233", "password": "Nodira2233",
         "children": "Alibek Karimov, Bekzod Karimov"},
        {"full_name": "Дилшод Каримов", "username": "+998935554411", "password": "Дилшод4411", "children": "Ғулом"}]


def test_export_xlsx(client, db, hunter):
    r = client.post("/parents/credentials-export", headers=_h(client), json={"format": "xlsx", "rows": ROWS})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert r.headers["cache-control"] == "no-store" and ".xlsx" in r.headers["content-disposition"]
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(r.content)).active
    values = [[c.value for c in row] for row in ws.iter_rows(min_row=4, max_row=6)]
    assert values[0][:5] == ["№", "Ota-ona", "Farzand(lar)", "Login (telefon)", "Parol"]
    assert values[1][1:5] == ["Nodira Karimova", "Alibek Karimov, Bekzod Karimov", "+998901112233", "Nodira2233"]
    assert values[2][4] == "Дилшод4411"


def test_export_pdf_has_unicode_text(client, db, hunter):
    r = client.post("/parents/credentials-export", headers=_h(client), json={"format": "pdf", "rows": ROWS})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    from pypdf import PdfReader
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(r.content)).pages)
    for needle in ("Nodira2233", "+998901112233", "Дилшод4411", "Karimova"):
        assert needle in text


def test_export_validates_rows(client, db, hunter):
    h = _h(client)
    assert client.post("/parents/credentials-export", headers=h, json={"format": "doc", "rows": ROWS}).status_code == 422
    assert client.post("/parents/credentials-export", headers=h, json={"format": "pdf", "rows": []}).status_code == 422


# ── CRM: ota-ona akkauntini o'chirish ───────────────────────────────────────
def _crm_parent(db, actor, phone="+998901112233", pwd="Nodira2233"):
    p = Parent(full_name="Nodira", phone=phone, username=phone, hashed_password=security.hash_password(pwd),
               is_active=True, created_by_id=actor.id if actor else None, created_at=datetime.utcnow())
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_hunter_deletes_crm_created_account(client, db, hunter):
    s = _student(db, "Alibek")
    p = _crm_parent(db, hunter)
    db.add(ParentChild(parent_id=p.id, student_id=s.id)); db.commit()
    tokens = client.post("/parent/auth/login", json={"username": p.phone, "password": "Nodira2233"}).json()
    h = _h(client)
    r = client.delete(f"/parents/{p.id}", headers=h)
    assert r.status_code == 204 and r.content == b""
    # Login, eski access va refresh — ishlamaydi
    assert client.post("/parent/auth/login", json={"username": "+998901112233", "password": "Nodira2233"}).status_code == 401
    assert client.get("/parent/profile", headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 401
    assert client.post("/parent/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    # CRM ro'yxatida yo'q, farzand bog'lanishi o'chgan, PII o'chirilgan
    assert all(x["id"] != p.id for x in client.get("/parents", headers=h).json())
    assert db.query(ParentChild).filter_by(parent_id=p.id).count() == 0
    db.refresh(p)
    assert p.deleted_at is not None and p.phone.startswith("deleted-") and p.full_name == "O'chirilgan akkaunt"
    audit = db.query(AuditLog).filter_by(entity_type="parent", entity_id=p.id, action="erase").one()
    assert audit.changed_by_id == hunter.id and "Nodira" not in f"{audit.old_value}{audit.new_value}"
    # Takroriy o'chirish — 404; shu raqamga yangi akkaunt ochiladi
    assert client.delete(f"/parents/{p.id}", headers=h).status_code == 404
    again = client.post("/parents", headers=h, json={"full_name": "Nodira", "phone": "+998901112233", "student_ids": [s.id]})
    assert again.status_code == 201 and again.json()["id"] != p.id


def test_hunter_cannot_delete_self_registered_parent_but_admin_can(client, db, hunter):
    p = _crm_parent(db, None)                                 # OTP orqali o'zi ro'yxatdan o'tgan
    assert client.delete(f"/parents/{p.id}", headers=_h(client)).status_code == 403
    _create_user(db, "boss", "boss123", UserRole.admin)
    assert client.delete(f"/parents/{p.id}", headers=_h(client, "boss", "boss123")).status_code == 204


def test_review_account_cannot_be_deleted(client, db, hunter, monkeypatch):
    monkeypatch.setenv("PARENT_REVIEW_PHONE", "+998901112233")
    p = _crm_parent(db, hunter)
    r = client.delete(f"/parents/{p.id}", headers=_h(client))
    assert r.status_code == 409
    db.refresh(p)
    assert p.deleted_at is None


def test_delete_requires_hunter_or_admin(client, db, hunter):
    p = _crm_parent(db, hunter)
    _create_user(db, "teach", "teach123", UserRole.teacher)
    assert client.delete(f"/parents/{p.id}", headers=_h(client, "teach", "teach123")).status_code == 403
    assert client.delete(f"/parents/{p.id}").status_code == 401
