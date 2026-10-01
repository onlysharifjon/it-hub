"""Space: QR orqali kirish (bir martalik token) va parolni almashtirish."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend import models
from backend.main import app
from backend.minar.models import MinarLoginToken, MinarSession
from backend.tests.test_minar import H, _minar_env, acct, login, new_account, post  # noqa: F401


def _qr(client, token, group_id=None, student_ids=None):
    body = {"group_id": group_id} if group_id else {"student_ids": student_ids}
    r = client.post("/space/admin/accounts/qr", json=body, headers=H(token))
    assert r.status_code == 200, r.text
    return r.json()


def _token(card):
    return card["url"].split("#qr=", 1)[1]


def test_issue_cards_for_group_skips_inactive(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    group = db.query(models.Group).join(models.GroupStudent).filter(models.GroupStudent.student_id == st.id).one()
    st2, _ = new_account(client, db, metodist_token, name="Arxiv Bola", group=group)   # o'sha guruhda
    st2.is_archived, st2.is_active = True, False
    db.commit()
    data = _qr(client, metodist_token, group_id=group.id)
    assert [c["login_id"] for c in data["cards"]] == [creds["login_id"]] and data["expires_days"] == 14
    card = data["cards"][0]
    assert card["url"].startswith("https://space.minaracademy.uz/#qr=") and card["svg"].startswith("<svg")
    assert db.query(MinarLoginToken).count() == 1 and len(_token(card)) >= 16
    assert db.query(MinarLoginToken).one().token_hash != _token(card)              # bazada xesh
    assert client.post("/space/admin/accounts/qr", json={}, headers=H(metodist_token)).status_code == 400


def test_qr_login_is_one_time_and_regeneration_revokes(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    old = _token(_qr(client, metodist_token, student_ids=[st.id])["cards"][0])
    new = _token(_qr(client, metodist_token, student_ids=[st.id])["cards"][0])
    assert post(client, "/auth/qr", {"token": old}).status_code == 401                # eski bekor
    r = post(client, "/auth/qr", {"token": new})
    assert r.status_code == 200 and r.json()["canSetWithoutCurrent"] is True
    assert client.get("/space/students/me/bootstrap").json()["profile"]["id"] == creds["login_id"]
    other = TestClient(app)
    other.headers.update({"Origin": "https://space.minaracademy.uz"})
    assert other.post("/space/auth/qr", json={"token": new}).status_code == 401       # ikkinchi marta yo'q


def test_qr_token_expires_and_rejects_garbage(client, db, metodist_token):
    st, _ = new_account(client, db, metodist_token)
    tok = _token(_qr(client, metodist_token, student_ids=[st.id])["cards"][0])
    row = db.query(MinarLoginToken).one()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert post(client, "/auth/qr", {"token": tok}).status_code == 401
    for bad in (None, 5, "short", "x" * 100):
        assert post(client, "/auth/qr", {"token": bad}).status_code == 401


def test_password_change_after_qr_without_current(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    login(client, creds)                                                         # boshqa qurilma sessiyasi
    tok = _token(_qr(client, metodist_token, student_ids=[st.id])["cards"][0])
    phone = TestClient(app)
    phone.headers.update({"Origin": "https://space.minaracademy.uz"})
    assert phone.post("/space/auth/qr", json={"token": tok}).status_code == 200
    assert phone.get("/space/auth/password").json() == {"canSetWithoutCurrent": True}
    assert phone.post("/space/auth/password", json={"new": "aaaaaa"}).status_code == 400    # juda oson
    assert phone.post("/space/auth/password", json={"new": "yangi-parol7"}).status_code == 200
    assert phone.get("/space/auth/password").json() == {"canSetWithoutCurrent": False}
    assert client.get("/space/students/me/bootstrap").status_code == 401         # boshqa sessiya yopildi
    assert phone.get("/space/students/me/bootstrap").status_code == 200          # joriy qoldi
    assert db.query(MinarSession).count() == 1
    assert post(client, "/auth/login", {"studentId": creds["login_id"], "password": creds["password"]}).status_code == 401
    assert post(client, "/auth/login", {"studentId": creds["login_id"], "password": "yangi-parol7"}).status_code == 200


def test_password_change_requires_current_after_normal_login(client, acct):
    _, creds = acct
    assert client.get("/space/auth/password").json() == {"canSetWithoutCurrent": False}
    assert post(client, "/auth/password", {"new": "yangi-parol7"}).status_code == 400
    assert post(client, "/auth/password", {"current": "xato", "new": "yangi-parol7"}).status_code == 400
    assert post(client, "/auth/password", {"current": creds["password"], "new": "123"}).status_code == 400
    assert post(client, "/auth/password", {"current": creds["password"], "new": "yangi-parol7"}).status_code == 200


def test_qr_requires_staff(client, db, teacher_token, metodist_token):
    st, _ = new_account(client, db, metodist_token)
    assert client.post("/space/admin/accounts/qr", json={"student_ids": [st.id]}).status_code in (401, 403)
