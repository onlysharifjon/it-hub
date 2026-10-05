from decimal import Decimal

from backend.models import Group, GroupStudent, Student, Tariff, UserRole
from backend.tests.conftest import _create_user, _login


def _setup(db):
    g = Group(name="F-1", stage="foundation", course_price=Decimal("500000"))
    s = Student(full_name="Ali Valiyev", phone1="+998901112233")
    t1 = Tariff(name="Standart", price=Decimal("500000"))
    t2 = Tariff(name="Chegirma", price=Decimal("400000"))
    db.add_all([g, s, t1, t2])
    db.flush()
    db.add(GroupStudent(group_id=g.id, student_id=s.id, tariff_id=t1.id))
    db.commit()
    return g, s, t1, t2


def _token(client, db, username, role):
    _create_user(db, username, "Pass@12345", role)
    return {"Authorization": f"Bearer {_login(client, username, 'Pass@12345')}"}


def test_hunter_changes_tariff_and_admin_sees_history(client, db):
    g, s, t1, t2 = _setup(db)
    hunter = _token(client, db, "hunter1", UserRole.hunter)
    admin = _token(client, db, "admin1", UserRole.admin)

    r = client.put(f"/groups/{g.id}/students/{s.id}/tariff", json={"tariff_id": t2.id}, headers=hunter)
    assert r.status_code == 200, r.text
    gs = db.query(GroupStudent).filter_by(group_id=g.id, student_id=s.id).one()
    db.refresh(gs)
    assert gs.tariff_id == t2.id

    # Hunter tarixni ko'ra olmaydi — faqat admin
    assert client.get("/tariff-changes", headers=hunter).status_code == 403
    items = client.get("/tariff-changes", headers=admin).json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["changed_by_name"] == "hunter1" and it["changed_by_role"] == "hunter"
    assert it["student_name"] == "Ali Valiyev" and it["group_name"] == "F-1"
    assert it["old_tariff_name"] == "Standart" and it["new_tariff_name"] == "Chegirma"
    assert Decimal(it["new_tariff_price"]) == Decimal("400000")


def test_tariff_change_forbidden_for_other_roles(client, db):
    g, s, _t1, t2 = _setup(db)
    sales = _token(client, db, "sales1", UserRole.sales)
    r = client.put(f"/groups/{g.id}/students/{s.id}/tariff", json={"tariff_id": t2.id}, headers=sales)
    assert r.status_code == 403


def test_same_tariff_not_logged(client, db):
    g, s, t1, _t2 = _setup(db)
    admin = _token(client, db, "admin1", UserRole.admin)
    client.put(f"/groups/{g.id}/students/{s.id}/tariff", json={"tariff_id": t1.id}, headers=admin)
    assert client.get("/tariff-changes", headers=admin).json()["items"] == []
