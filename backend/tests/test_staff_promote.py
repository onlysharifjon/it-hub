"""Xodimlar: Support Teacher → O'qituvchi rolini o'zgartirish."""
from backend.models import AuditLog, User, UserRole

from .conftest import _create_user, _login


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_audit_promotes_support_teacher_to_teacher(client, db, metodist_user):
    _create_user(db, "auditor", "auditor123", UserRole.audit)
    token = _login(client, "auditor", "auditor123")

    res = client.post(f"/staff-options/{metodist_user.id}/promote-to-teacher", headers=_h(token))
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "teacher"

    db.expire_all()
    assert db.get(User, metodist_user.id).role == "teacher"
    log = db.query(AuditLog).filter(AuditLog.action == "promote_to_teacher").one()
    assert log.entity_id == metodist_user.id

    # Xodim yangi rol bilan ishlaydi — qayta login shart emas
    me = client.get("/auth/me", headers=_h(_login(client, "metodist", "metodist123")))
    assert me.status_code == 200 and me.json()["role"] == "teacher"


def test_admin_can_promote(client, db, metodist_user):
    _create_user(db, "boss", "boss12345", UserRole.admin)
    token = _login(client, "boss", "boss12345")
    res = client.post(f"/staff-options/{metodist_user.id}/promote-to-teacher", headers=_h(token))
    assert res.status_code == 200 and res.json()["role"] == "teacher"


def test_only_support_teacher_can_be_promoted(client, db, teacher_user):
    hunter = _create_user(db, "hunter1", "hunter123", UserRole.hunter)
    _create_user(db, "auditor", "auditor123", UserRole.audit)
    token = _login(client, "auditor", "auditor123")
    for target in (teacher_user, hunter):
        res = client.post(f"/staff-options/{target.id}/promote-to-teacher", headers=_h(token))
        assert res.status_code == 400
    db.expire_all()
    assert db.get(User, hunter.id).role == "hunter"


def test_promote_forbidden_for_non_audit(client, metodist_user, teacher_token, metodist_token):
    for token in (teacher_token, metodist_token):
        res = client.post(f"/staff-options/{metodist_user.id}/promote-to-teacher", headers=_h(token))
        assert res.status_code == 403


def test_promote_missing_user(client, db):
    _create_user(db, "auditor", "auditor123", UserRole.audit)
    token = _login(client, "auditor", "auditor123")
    assert client.post("/staff-options/999999/promote-to-teacher", headers=_h(token)).status_code == 404
