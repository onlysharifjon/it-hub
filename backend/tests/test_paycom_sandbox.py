"""Disposable Paycom cashbox and credential rotation stay outside live CRM."""

import base64
import importlib
import time

from fastapi.testclient import TestClient

from backend import models
from backend.parent.payments import core, payme


def _auth(key):
    token = base64.b64encode(f"Paycom:{key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_sandbox_fixture_and_credential_rotation(monkeypatch, db, client):
    # The global pytest database is temporary SQLite. The URL below is only a
    # sandbox configuration guard value and is never used for a connection.
    monkeypatch.setenv("PAYCOM_SANDBOX_MODE", "enabled")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test@localhost/paycom_sandbox")
    monkeypatch.setenv("PAYME_ACCOUNT_FIELD", "order_id")
    monkeypatch.setenv("PAYME_MERCHANT_ID", "test-merchant")
    monkeypatch.setenv("PAYME_KEY", "initial-test-key")
    sandbox = importlib.import_module("backend.paycom_sandbox_app")
    seed = importlib.import_module("backend.scripts.create_paycom_sandbox_invoices")
    sandbox.ensure_auth_table()

    ids = seed.create_invoices(7000, 3, 24)
    assert len(ids) == 3
    assert db.query(models.ParentInvoice).filter_by(id=ids[0]).one().status == "pending"
    assert db.query(models.Parent).filter_by(username="paycom_sandbox_parent").one().is_active is False

    with TestClient(sandbox.app) as api:
        body = {"jsonrpc": "2.0", "id": 1, "method": "CheckPerformTransaction",
                "params": {"account": {"order_id": str(ids[0])}, "amount": 700000}}
        assert api.post("/payme", json=body, headers=_auth("initial-test-key")).json()["result"] == {"allow": True}

        # Paycom's three-step ChangePassword sandbox scenario.
        change = {"jsonrpc": "2.0", "id": 2, "method": "ChangePassword",
                  "params": {"password": "rotated-test-key"}}
        assert api.post("/payme", json=change, headers=_auth("initial-test-key")).json()["result"] == {"success": True}
        change["id"] = 3
        change["params"]["password"] = "second-rotated-key"
        assert api.post("/payme", json=change, headers=_auth("initial-test-key")).json()["error"]["code"] == -32504
        change["id"] = 4
        assert api.post("/payme", json=change, headers=_auth("rotated-test-key")).json()["result"] == {"success": True}
        body["id"] = 5
        assert api.post("/payme", json=body, headers=_auth("second-rotated-key")).json()["result"] == {"allow": True}
        assert api.post("/payme", json=body, headers=_auth("initial-test-key")).json()["error"]["code"] == -32504

    # Production dispatch remains without a credential rotation method.
    assert "ChangePassword" not in payme._METHODS
    assert client.post("/payme", json=change, headers=_auth("initial-test-key")).json()["error"]["code"] == -32601

    # Synthetic account can complete and refund a payment on its own DB.
    created = payme._create(db, {"id": f"sandbox-{time.time_ns()}", "time": core.now_ms(),
                                 "account": {"order_id": str(ids[0])}, "amount": 700000})
    db.commit()
    assert created["state"] == 1
    txn = db.query(models.PaymentTransaction).filter_by(invoice_id=ids[0]).one()
    assert payme._perform(db, {"id": txn.provider_txn_id})["state"] == 2
    db.commit()
    assert db.query(models.Payment).filter_by(parent_invoice_id=ids[0]).count() == 1
    assert payme._cancel(db, {"id": txn.provider_txn_id, "reason": 5})["state"] == -2
    db.commit()
    assert db.query(models.Payment).filter_by(parent_invoice_id=ids[0]).count() == 0


def test_sandbox_guard_rejects_live_db(monkeypatch):
    monkeypatch.setenv("PAYCOM_SANDBOX_MODE", "enabled")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test@localhost/ithub_db")
    monkeypatch.setenv("PAYME_ACCOUNT_FIELD", "order_id")
    from backend.paycom_sandbox_app import require_sandbox_database
    try:
        require_sandbox_database()
        assert False, "live CRM database was accepted"
    except RuntimeError:
        pass
