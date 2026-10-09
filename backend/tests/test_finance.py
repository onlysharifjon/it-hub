"""Moliya bo'limi (Finans roli): huquqlar, to'lovlar, xarajatlar, qaytarim,
tuzatish, o'tkazma, valyuta, qarzdorlik, hisobot va audit."""
import json
from datetime import datetime
from decimal import Decimal

import pytest

from backend import core_calc, tz
from backend.models import (AuditLog, Expense, FinanceTransaction, Group, GroupStudent, Payment, Student,
                            User, UserRole)
from backend.tests.conftest import _create_user, _login

PRICE = 500000


def _months_back(n):
    t = tz.today()
    y, m = t.year, t.month - n
    while m < 1:
        m += 12
        y -= 1
    return y, m


@pytest.fixture
def setup(db, client):
    admin = _create_user(db, "boss", "boss12345", UserRole.admin)
    fin = _create_user(db, "fin", "fin12345", UserRole.finance)
    appr = _create_user(db, "appr", "appr12345", UserRole.finance)
    hunter = _create_user(db, "hunt", "hunt12345", UserRole.hunter)
    y0, m0 = _months_back(2)
    g = Group(name="F-01", stage="foundation", course_price=PRICE, start_date=datetime(y0, m0, 1),
              is_active=True, created_at=datetime(y0, m0, 1))
    s = Student(full_name="Aliyev Vali", phone1="+998901112233", is_active=True, created_at=datetime(y0, m0, 1))
    db.add_all([g, s]); db.commit()
    db.add(GroupStudent(group_id=g.id, student_id=s.id, joined_at=datetime(y0, m0, 1))); db.commit()
    tok = {k: _login(client, u, p) for k, (u, p) in {
        "admin": ("boss", "boss12345"), "fin": ("fin", "fin12345"),
        "appr": ("appr", "appr12345"), "hunter": ("hunt", "hunt12345")}.items()}
    H = {k: {"Authorization": f"Bearer {v}"} for k, v in tok.items()}
    full = ["finance.dashboard", "finance.clients", "finance.income", "finance.expense", "finance.debts",
            "finance.reports", "finance.export", "finance.audit", "finance.approve", "finance.refund",
            "finance.transfer", "finance.categories"]
    r = client.put(f"/finance/users/{appr.id}/permissions", json={"permissions": full}, headers=H["admin"])
    assert r.status_code == 200, r.text
    accs = client.get("/finance/accounts", headers=H["admin"]).json()
    cash = next(a for a in accs if a["code"] == "main_cash")
    return {"H": H, "g": g, "s": s, "fin": fin, "appr": appr, "admin": admin, "cash": cash, "y0": y0, "m0": m0}


def _income(client, ctx, amount, *, who="appr", month=None, year=None, confirm=True, key=None, account=None, **kw):
    y, m = (year, month) if month else (ctx["y0"], ctx["m0"])
    body = {"student_id": ctx["s"].id, "group_id": ctx["g"].id, "amount": amount, "method": "cash",
            "account_id": account or ctx["cash"]["id"], "period_month": m, "period_year": y,
            "confirm": confirm, **kw}
    if key:
        body["idempotency_key"] = key
    return client.post("/finance/income", json=body, headers=ctx["H"][who])


def _balance(client, ctx, account_id=None):
    accs = client.get("/finance/accounts", headers=ctx["H"]["admin"]).json()
    a = next(a for a in accs if a["id"] == (account_id or ctx["cash"]["id"]))
    assert a["in_sync"], a
    return Decimal(str(a["balance"]))


def _student(client, ctx):
    return client.get(f"/finance/students/{ctx['s'].id}", headers=ctx["H"]["appr"]).json()


def _reconciled(client, ctx):
    r = client.get("/finance/reconcile", headers=ctx["H"]["admin"]).json()
    assert r["payments"]["in_sync"], r
    assert r["expenses"]["in_sync"], r
    assert all(a["in_sync"] for a in r["accounts"]), r


# ── Huquqlar ─────────────────────────────────────────────────────────────────

def test_permissions(client, setup, db):
    H = setup["H"]
    me = client.get("/finance/me", headers=H["fin"]).json()
    assert "finance.dashboard" in me["permissions"] and "finance.approve" not in me["permissions"]
    # ruxsat berilgan
    for url in ("/finance/dashboard", "/finance/debts", "/finance/transactions", "/finance/reports/income",
                "/finance/audit", "/finance/accounts", "/finance/categories"):
        assert client.get(url, headers=H["fin"]).status_code == 200, url
    # taqiqlangan: rollar, sozlamalar, o'z huquqlari, hisob yaratish, tasdiqlash, qaytarim
    fin_id = setup["fin"].id
    assert client.put(f"/users/{fin_id}", json={"role": "admin"}, headers=H["fin"]).status_code == 403
    assert client.post("/users", json={"username": "x1234", "password": "12345678x", "role": "admin"},
                       headers=H["fin"]).status_code == 403
    assert client.put(f"/finance/users/{fin_id}/permissions", json={"permissions": list(me["permissions"]) + ["finance.approve"]},
                      headers=H["fin"]).status_code == 403
    assert client.put("/finance/settings", json={"due_day": 5}, headers=H["fin"]).status_code == 403
    assert client.post("/finance/accounts", json={"name": "Bank"}, headers=H["fin"]).status_code == 403
    assert client.post("/finance/categories", json={"name": "Yangi"}, headers=H["fin"]).status_code == 403
    assert _income(client, setup, 1000, who="fin", confirm=True).status_code == 403
    draft = _income(client, setup, 1000, who="fin", confirm=False)
    assert draft.status_code == 201 and draft.json()["status"] == "draft"
    tid = draft.json()["id"]
    assert client.post(f"/finance/transactions/{tid}/confirm", headers=H["fin"]).status_code == 403
    assert client.post(f"/finance/transactions/{tid}/refund", json={"amount": 1, "reason": "test"},
                       headers=H["fin"]).status_code == 403
    # boshqa rollar moliya bo'limiga kira olmaydi
    assert client.get("/finance/dashboard", headers=H["hunter"]).status_code == 403
    # admin huquqni olib qo'ysa — darhol kuchga kiradi
    client.put(f"/finance/users/{fin_id}/permissions", json={"permissions": ["finance.dashboard"]}, headers=H["admin"])
    assert client.get("/finance/debts", headers=H["fin"]).status_code == 403
    assert client.get("/finance/reports/income/export", headers=H["fin"]).status_code == 403
    # audit: huquq o'zgarishi yozilgan, o'zgartirish endpoint'i yo'q
    assert db.query(AuditLog).filter(AuditLog.entity_type == "user_permissions").count() >= 2
    assert client.delete("/finance/audit", headers=H["admin"]).status_code in (404, 405)


# ── To'lovlar ────────────────────────────────────────────────────────────────

def test_full_partial_and_over_payment(client, setup, db):
    st = _student(client, setup)["totals"]
    owed = Decimal(str(st["net_total"]))
    assert owed == Decimal(PRICE * 3)            # 3 oy (2 oy oldin, o'tgan oy, joriy oy)
    assert Decimal(str(st["debt"])) == owed

    assert _income(client, setup, PRICE).status_code == 201                      # to'liq (1-oy)
    y1, m1 = _months_back(1)
    assert _income(client, setup, 200000, month=m1, year=y1).status_code == 201  # qisman (2-oy)
    t = _student(client, setup)["totals"]
    assert Decimal(str(t["debt"])) == owed - PRICE - 200000
    inst = _student(client, setup)["installments"]
    assert inst[0]["status"] == "paid" and Decimal(str(inst[1]["remaining"])) == PRICE - 200000

    over = owed - PRICE - 200000 + 150000                                        # ortiqcha → avans
    assert _income(client, setup, str(over), month=m1, year=y1).status_code == 201
    t = _student(client, setup)["totals"]
    assert Decimal(str(t["debt"])) == 0 and Decimal(str(t["advance"])) == 150000
    # core_calc (CRM'ning qolgan qismi) bilan bir xil
    db.expire_all()
    s = db.query(Student).get(setup["s"].id)
    assert core_calc.student_cumulative_balance(db, s) == Decimal(150000)
    assert _balance(client, setup) == owed + 150000
    _reconciled(client, setup)


def test_duplicate_request_creates_one_payment(client, setup, db):
    r1 = _income(client, setup, PRICE, key="req-abc-123456")
    r2 = _income(client, setup, PRICE, key="req-abc-123456")
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"] and r2.json()["duplicate"] is True
    assert db.query(Payment).count() == 1
    assert db.query(FinanceTransaction).filter(FinanceTransaction.kind == "income").count() == 1
    assert _balance(client, setup) == PRICE


def test_draft_and_cancelled_not_in_totals(client, setup, db):
    H = setup["H"]
    d = _income(client, setup, PRICE, who="fin", confirm=False).json()
    d2 = _income(client, setup, 300000, who="fin", confirm=False).json()
    assert db.query(Payment).count() == 0 and _balance(client, setup) == 0
    dash = client.get("/finance/dashboard", headers=H["appr"]).json()
    assert Decimal(str(dash["period"].get("UZS", {}).get("income", 0))) == 0
    assert dash["drafts"]["income"] == 2
    # bekor qilish (sabab bilan) va tasdiqlash
    assert client.post(f"/finance/transactions/{d2['id']}/cancel", json={"reason": "xato kiritildi"},
                       headers=H["fin"]).status_code == 200
    r = client.post(f"/finance/transactions/{d['id']}/confirm", headers=H["appr"])
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert client.post(f"/finance/transactions/{d['id']}/confirm", headers=H["appr"]).status_code == 200  # idempotent
    assert db.query(Payment).count() == 1 and _balance(client, setup) == PRICE
    assert client.post(f"/finance/transactions/{d2['id']}/confirm", headers=H["appr"]).status_code == 409
    assert client.post(f"/finance/transactions/{d['id']}/cancel", json={"reason": "bekor"},
                       headers=H["appr"]).status_code == 409
    dash = client.get("/finance/dashboard", headers=H["appr"]).json()
    assert Decimal(str(dash["period"]["UZS"]["income"])) == PRICE


# ── Xarajatlar ───────────────────────────────────────────────────────────────

def _cat(client, ctx, code):
    return next(c for c in client.get("/finance/categories", headers=ctx["H"]["admin"]).json() if c["code"] == code)


def test_expense_approval(client, setup, db):
    H = setup["H"]
    other = _cat(client, setup, "other")
    body = {"category_id": other["id"], "amount": 120000, "account_id": setup["cash"]["id"],
            "counterparty": "Elektr tarmoqlari", "responsible_id": setup["fin"].id, "notes": "Sentyabr"}
    e = client.post("/finance/expenses", json=body, headers=H["fin"])
    assert e.status_code == 201 and e.json()["status"] == "draft"
    assert db.query(Expense).count() == 0
    # o'z xarajatini tasdiqlay olmaydi (appr o'zi yaratgan bo'lsa)
    own = client.post("/finance/expenses", json={**body, "confirm": False}, headers=H["appr"]).json()
    assert client.post(f"/finance/transactions/{own['id']}/confirm", headers=H["appr"]).status_code == 403
    # boshqa vakolatli xodim tasdiqlaydi
    r = client.post(f"/finance/transactions/{e.json()['id']}/confirm", headers=H["appr"])
    assert r.status_code == 200
    assert db.query(Expense).count() == 1 and _balance(client, setup) == -120000
    # ish haqi — xodim majburiy
    sal = _cat(client, setup, "salary")
    bad = client.post("/finance/expenses", json={**body, "category_id": sal["id"]}, headers=H["fin"])
    assert bad.status_code == 400
    # kategoriya boshqaruvi
    assert client.post("/finance/categories", json={"name": "Internet"}, headers=H["appr"]).status_code == 201
    _reconciled(client, setup)


# ── Qaytarim va tuzatish ─────────────────────────────────────────────────────

def test_refund_and_adjustment(client, setup, db):
    H = setup["H"]
    inc = _income(client, setup, PRICE).json()
    debt0 = Decimal(str(_student(client, setup)["totals"]["debt"]))
    url = f"/finance/transactions/{inc['id']}"
    assert client.post(f"{url}/refund", json={"amount": PRICE + 1, "reason": "ko'p"}, headers=H["appr"]).status_code == 400
    assert client.post(f"{url}/refund", json={"amount": 100}, headers=H["appr"]).status_code == 422  # sabab majburiy
    r = client.post(f"{url}/refund", json={"amount": 200000, "reason": "Talaba kursni tark etdi",
                                           "idempotency_key": "refund-key-0001"}, headers=H["appr"])
    assert r.status_code == 201 and r.json()["origin"]["id"] == inc["id"]
    assert client.post(f"{url}/refund", json={"amount": 200000, "reason": "Talaba kursni tark etdi",
                                              "idempotency_key": "refund-key-0001"}, headers=H["appr"]).status_code == 200
    assert Decimal(str(_student(client, setup)["totals"]["debt"])) == debt0 + 200000
    assert _balance(client, setup) == PRICE - 200000
    assert client.post(f"{url}/refund", json={"amount": 300001, "reason": "qolgan"}, headers=H["appr"]).status_code == 400
    # tuzatish: +50 000 (kassir kam kiritgan)
    a = client.post(f"{url}/adjust", json={"amount": 50000, "reason": "Summa kam kiritilgan"}, headers=H["appr"])
    assert a.status_code == 201 and a.json()["kind"] == "adjustment"
    assert client.post(f"{url}/adjust", json={"amount": -400000, "reason": "manfiy"}, headers=H["appr"]).status_code == 400
    detail = client.get(url, headers=H["appr"]).json()
    assert Decimal(str(detail["net_amount"])) == PRICE - 200000 + 50000
    assert {c["kind"] for c in detail["children"]} == {"refund", "adjustment"}
    assert any(h["reason"] == "Talaba kursni tark etdi" for h in
               client.get("/finance/audit?action=refund", headers=H["appr"]).json()["items"])
    # asl to'lov o'zgarmagan
    assert Decimal(str(detail["amount"])) == PRICE and detail["status"] == "confirmed"
    _reconciled(client, setup)


# ── O'tkazma va valyuta ──────────────────────────────────────────────────────

def test_transfer_and_currency_rules(client, setup):
    H = setup["H"]
    _income(client, setup, PRICE)
    bank = client.post("/finance/accounts", json={"name": "Kapitalbank", "kind": "bank"}, headers=H["admin"]).json()
    usd = client.post("/finance/accounts", json={"name": "Valyuta kassa", "kind": "cash", "currency": "USD"},
                      headers=H["admin"]).json()
    before = client.get("/finance/dashboard", headers=H["appr"]).json()["period"]["UZS"]
    t = client.post("/finance/transfers", json={"account_id": setup["cash"]["id"], "to_account_id": bank["id"],
                                                "amount": 300000}, headers=H["appr"])
    assert t.status_code == 201
    after = client.get("/finance/dashboard", headers=H["appr"]).json()["period"]["UZS"]
    assert after == before                                                    # tushum/xarajat sun'iy oshmadi
    assert _balance(client, setup) == PRICE - 300000 and _balance(client, setup, bank["id"]) == 300000
    assert client.post("/finance/transfers", json={"account_id": bank["id"], "to_account_id": usd["id"],
                                                   "amount": 10}, headers=H["appr"]).status_code == 400
    other = _cat(client, setup, "other")
    body = {"category_id": other["id"], "amount": 100, "account_id": usd["id"], "confirm": False}
    assert client.post("/finance/expenses", json=body, headers=H["fin"]).status_code == 400   # kurs yo'q
    e = client.post("/finance/expenses", json={**body, "fx_rate": 12700}, headers=H["fin"]).json()
    client.post(f"/finance/transactions/{e['id']}/confirm", headers=H["appr"])
    period = client.get("/finance/dashboard", headers=H["appr"]).json()["period"]
    assert Decimal(str(period["USD"]["expense"])) == 100
    assert Decimal(str(period["UZS"]["expense"])) == 0                         # valyutalar qo'shilmadi
    _reconciled(client, setup)


# ── Eski sahifalar bilan integratsiya ────────────────────────────────────────

def test_legacy_payment_and_expense_are_journaled(client, setup, db):
    H = setup["H"]
    r = client.post("/payments", json={"student_id": setup["s"].id, "group_id": setup["g"].id, "amount": PRICE,
                                       "month": setup["m0"], "year": setup["y0"], "method": "card"}, headers=H["hunter"])
    assert r.status_code == 201, r.text
    tx = db.query(FinanceTransaction).filter(FinanceTransaction.payment_id == r.json()["id"]).one()
    assert tx.status == "confirmed" and tx.method == "card" and _balance(client, setup) == PRICE
    assert client.put(f"/payments/{r.json()['id']}", json={"amount": 400000}, headers=H["admin"]).status_code == 200
    assert _balance(client, setup) == 400000
    assert client.delete(f"/payments/{r.json()['id']}", headers=H["admin"]).status_code == 204
    assert _balance(client, setup) == 0
    kinds = [t.kind for t in db.query(FinanceTransaction).order_by(FinanceTransaction.id)]
    assert kinds == ["income", "adjustment", "adjustment"]       # asl yozuv o'chmagan
    e = client.post("/expenses", json={"name": "Suv", "amount": 30000}, headers=H["hunter"])
    assert e.status_code == 201 and _balance(client, setup) == -30000
    _reconciled(client, setup)


# ── Hisobotlar ───────────────────────────────────────────────────────────────

def test_reports_match_dashboard_and_export(client, setup):
    H = setup["H"]
    inc = _income(client, setup, PRICE).json()
    client.post(f"/finance/transactions/{inc['id']}/refund", json={"amount": 100000, "reason": "qaytarim"},
                headers=H["appr"])
    other = _cat(client, setup, "other")
    e = client.post("/finance/expenses", json={"category_id": other["id"], "amount": 70000,
                                               "account_id": setup["cash"]["id"]}, headers=H["fin"]).json()
    client.post(f"/finance/transactions/{e['id']}/confirm", headers=H["appr"])
    dash = client.get("/finance/dashboard", headers=H["appr"]).json()["period"]["UZS"]
    inc_rep = client.get("/finance/reports/income", headers=H["appr"]).json()["totals"]["UZS"]
    exp_rep = client.get("/finance/reports/expenses", headers=H["appr"]).json()
    flow = client.get("/finance/reports/cashflow", headers=H["appr"]).json()["totals"]["UZS"]
    assert Decimal(str(inc_rep["income"])) == Decimal(str(dash["income"])) == PRICE
    assert Decimal(str(inc_rep["refunds"])) == Decimal(str(dash["refunds"])) == 100000
    assert Decimal(str(exp_rep["totals"]["UZS"]["expense"])) == Decimal(str(dash["expense"])) == 70000
    assert exp_rep["breakdown"][0]["category"] == "Boshqa"
    assert Decimal(str(flow["net"])) == Decimal(str(dash["net"])) == PRICE - 100000 - 70000
    acc = client.get("/finance/reports/accounts", headers=H["appr"]).json()
    cash_row = next(r for r in acc["rows"] if r["account"] == "Asosiy kassa")
    assert Decimal(str(cash_row["closing"])) == _balance(client, setup)
    debts = client.get("/finance/reports/debts", headers=H["appr"]).json()
    st = _student(client, setup)["totals"]
    assert Decimal(str(debts["totals"]["UZS"]["debt"])) == Decimal(str(st["debt"]))
    hist = client.get(f"/finance/reports/history?student_id={setup['s'].id}", headers=H["appr"]).json()
    assert len(hist["rows"]) == 2
    x = client.get("/finance/reports/income/export?format=xlsx", headers=H["fin"])
    assert x.status_code == 200 and x.content[:2] == b"PK"
    c = client.get("/finance/reports/expenses/export?format=csv", headers=H["fin"])
    assert c.status_code == 200 and "Boshqa" in c.content.decode("utf-8-sig")


def test_overdue_vs_not_due(client, setup):
    H = setup["H"]
    client.put("/finance/settings", json={"due_day": 28}, headers=H["admin"])
    st = _student(client, setup)
    t = st["totals"]
    # 2 ta o'tgan oy muddati o'tgan; joriy oy — bugun 28-dan oldin bo'lsa muddati kelmagan
    today = tz.today()
    expected_overdue = PRICE * (3 if today.day > 28 else 2)
    assert Decimal(str(t["overdue_debt"])) == expected_overdue
    assert Decimal(str(t["not_due_debt"])) == PRICE * 3 - expected_overdue
    assert any(i["status"] == "upcoming" for i in st["installments"])            # keyingi oy bosqichi
    od = client.get("/finance/reports/overdue", headers=H["appr"]).json()
    assert Decimal(str(od["totals"]["UZS"]["remaining"])) == expected_overdue
