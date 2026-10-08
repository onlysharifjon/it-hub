"""Payme Merchant API — /payme JSON-RPC va ota-ona checkout havolasi."""
import base64
from datetime import datetime

import pytest

from backend.models import Payment, ParentInvoice, PaymeTransaction, UserRole
from .conftest import _create_user
from .test_parent import _mk_student, _mk_group, _enroll, _create_parent, _hunter_token

KEY = "test-payme-key"


@pytest.fixture(autouse=True)
def payme_env(monkeypatch):
    monkeypatch.setenv("PAYME_MERCHANT_ID", "6a7b09f1182af99b930da429")
    monkeypatch.setenv("PAYME_KEY", KEY)
    monkeypatch.setenv("PAYME_TEST_MODE", "true")


@pytest.fixture
def invoice(client, db):
    _create_user(db, "hunter", "hunter123", UserRole.hunter)
    student = _mk_student(db)
    group = _mk_group(db, price=450000)
    _enroll(db, group, student)
    acct = _create_parent(client, _hunter_token(client), [student.id])
    ptoken = client.post("/parent/auth/login", json={
        "username": acct["username"], "password": acct["generated_password"]}).json()["access_token"]
    res = client.post(f"/parent/children/{student.id}/pay", headers={"Authorization": f"Bearer {ptoken}"},
                      json={"amount": 450000, "group_id": group.id, "provider": "payme"})
    assert res.status_code == 200, res.text
    url = res.json()["checkout_url"]
    assert url.startswith("https://checkout.test.paycom.uz/")
    inv = db.query(ParentInvoice).one()
    params = base64.b64decode(url.rsplit("/", 1)[1]).decode()
    assert params == f"m=6a7b09f1182af99b930da429;ac.order_id={inv.id};a=45000000"
    return inv


def rpc(client, method, params, key=KEY):
    auth = base64.b64encode(f"Paycom:{key}".encode()).decode()
    res = client.post("/payme", headers={"Authorization": f"Basic {auth}"},
                      json={"jsonrpc": "2.0", "id": 7, "method": method, "params": params})
    assert res.status_code == 200
    return res.json()


def test_wrong_key_rejected(client, invoice):
    r = rpc(client, "CheckPerformTransaction", {"amount": 45000000, "account": {"order_id": invoice.id}}, key="bad")
    assert r["error"]["code"] == -32504 and r["id"] == 7


def test_check_perform_validates_order_and_amount(client, invoice):
    ok = rpc(client, "CheckPerformTransaction", {"amount": 45000000, "account": {"order_id": invoice.id}})
    assert ok["result"] == {"allow": True}
    assert rpc(client, "CheckPerformTransaction",
               {"amount": 100, "account": {"order_id": invoice.id}})["error"]["code"] == -31001
    assert rpc(client, "CheckPerformTransaction",
               {"amount": 45000000, "account": {"order_id": 99999}})["error"]["code"] == -31050


def test_full_flow_records_payment_and_cancel_reverts(client, db, invoice):
    acc = {"amount": 45000000, "account": {"order_id": invoice.id}}
    t = int(datetime.utcnow().timestamp() * 1000)
    created = rpc(client, "CreateTransaction", {"id": "pay-1", "time": t, **acc})["result"]
    assert created["state"] == 1
    # takroriy Create — o'sha javob
    assert rpc(client, "CreateTransaction", {"id": "pay-1", "time": t, **acc})["result"] == created
    # boshqa tranzaksiya shu buyurtmaga — band
    assert rpc(client, "CreateTransaction", {"id": "pay-2", "time": t, **acc})["error"]["code"] == -31050

    performed = rpc(client, "PerformTransaction", {"id": "pay-1"})["result"]
    assert performed["state"] == 2 and performed["perform_time"] > 0
    assert rpc(client, "PerformTransaction", {"id": "pay-1"})["result"] == performed
    db.expire_all()
    pay = db.query(Payment).one()
    assert int(pay.amount) == 450000 and pay.student_id == invoice.student_id
    assert db.get(ParentInvoice, invoice.id).status == "paid"
    # to'langan buyurtmaga yangi to'lov yo'q
    assert rpc(client, "CheckPerformTransaction", acc)["error"]["code"] == -31051

    st = rpc(client, "CheckTransaction", {"id": "pay-1"})["result"]
    assert st["state"] == 2 and st["transaction"] == created["transaction"]
    stmt = rpc(client, "GetStatement", {"from": t - 1, "to": t + 1})["result"]["transactions"]
    assert [x["id"] for x in stmt] == ["pay-1"] and stmt[0]["account"] == {"order_id": str(invoice.id)}

    cancelled = rpc(client, "CancelTransaction", {"id": "pay-1", "reason": 5})["result"]
    assert cancelled["state"] == -2 and cancelled["cancel_time"] > 0
    db.expire_all()
    assert db.query(Payment).count() == 0
    assert db.query(PaymeTransaction).one().reason == 5


def test_cancel_created_and_unknown_tx(client, db, invoice):
    acc = {"amount": 45000000, "account": {"order_id": invoice.id}}
    rpc(client, "CreateTransaction", {"id": "pay-3", "time": 1, **acc})
    assert rpc(client, "CancelTransaction", {"id": "pay-3", "reason": 3})["result"]["state"] == -1
    assert rpc(client, "PerformTransaction", {"id": "pay-3"})["error"]["code"] == -31008
    assert rpc(client, "CheckTransaction", {"id": "nope"})["error"]["code"] == -31003
    assert rpc(client, "Nope", {})["error"]["code"] == -32601
