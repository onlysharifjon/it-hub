"""Tashqi xarajatlarni alohida Excel'ga eksport qilish."""
import io
from datetime import datetime

import openpyxl
import pytest

from backend import tz
from backend.models import UserRole
from backend.tests.conftest import _create_user, _login


@pytest.fixture
def admin_token(client, db):
    _create_user(db, "admin", "admin12345", UserRole.admin)
    return _login(client, "admin", "admin12345")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _rows(res):
    ws = openpyxl.load_workbook(io.BytesIO(res.content)).active
    return [[c.value for c in row] for row in ws.iter_rows()]


def _create_on(client, h, monkeypatch, month, payload):
    """Xarajat oyi kiritilgan sanadan olinadi — sanani shu oyga qotiramiz."""
    monkeypatch.setattr(tz, "now", lambda: datetime(2026, month, 15, 12, 0))
    res = client.post("/expenses", headers=h, json=payload)
    assert res.status_code == 201
    return res.json()


def test_expenses_export_filters_and_totals(client, db, admin_token, monkeypatch):
    staff = _create_user(db, "hunter1", "hunter12345", UserRole.hunter)
    h = _h(admin_token)
    for month, payload in (
        (9, {"name": "Ijara", "amount": 3000000, "category": "other"}),
        (9, {"name": "=1+1", "amount": 500000, "category": "other"}),
        (9, {"name": "Oylik", "amount": 2000000, "category": "salary", "staff_id": staff.id}),
        (8, {"name": "Reklama", "amount": 700000, "category": "other"}),
    ):
        _create_on(client, h, monkeypatch, month, payload)

    res = client.get("/expenses/export/excel?month=9&year=2026", headers=h)
    assert res.status_code == 200
    assert "expenses_all_2026_9.xlsx" in res.headers["content-disposition"]
    rows = _rows(res)
    assert rows[0][1] == "Nomi / Sabab"
    assert {r[1] for r in rows[1:4]} == {"Ijara", "=1+1", "Oylik"}   # '=' formula emas, matn
    assert rows[-1][0] == "JAMI:" and rows[-1][4] == 5500000

    # Faqat oddiy (tashqi) xarajatlar — oylik kirmaydi
    rows = _rows(client.get("/expenses/export/excel?month=9&year=2026&category=other", headers=h))
    assert {r[1] for r in rows[1:3]} == {"Ijara", "=1+1"}
    assert rows[-1][4] == 3500000

    rows = _rows(client.get("/expenses/export/excel?month=9&year=2026&category=salary", headers=h))
    assert rows[1][1:4] == ["Oylik", "Xodim oyligi", "hunter1"]
    assert rows[-1][4] == 2000000

    assert client.get("/expenses/export/excel?category=xyz", headers=h).status_code == 400


def test_expenses_export_auth(client, db, admin_token, teacher_token):
    assert client.get("/expenses/export/excel").status_code == 401
    assert client.get("/expenses/export/excel", headers=_h(teacher_token)).status_code == 403
    dl = client.get("/auth/download-token", headers=_h(admin_token)).json()["token"]
    assert client.get(f"/expenses/export/excel?_token={dl}").status_code == 200


def test_expense_month_follows_created_date(client, db, admin_token, monkeypatch):
    """Sentyabr oyligi oktyabrda berilsa — oktyabr xarajati; oyni qo'lda o'zgartirib bo'lmaydi."""
    staff = _create_user(db, "hunter1", "hunter12345", UserRole.hunter)
    h = _h(admin_token)
    exp = _create_on(client, h, monkeypatch, 10, {"name": "Sentyabr oyligi", "amount": 900000,
                                                  "month": 9, "year": 2026,
                                                  "category": "salary", "staff_id": staff.id})
    assert (exp["month"], exp["year"]) == (10, 2026)
    res = client.put(f"/expenses/{exp['id']}", headers=h, json={"month": 9, "amount": 950000})
    assert res.status_code == 200
    assert (res.json()["month"], res.json()["amount"]) == (10, 950000)
