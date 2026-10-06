"""Telefon + Telegram Gateway OTP testlari. Haqiqiy Telegram API chaqirilmaydi:
unit — httpx.MockTransport, integration — FastAPI dependency override (FakeGateway)."""
import json
from datetime import datetime, timedelta

import httpx
import pytest

from backend import security
from backend.main import app
from backend.models import Parent, ParentChild, PhoneVerification, Student
from backend.parent.phone_auth.gateway import GatewayError, TelegramGatewayClient, get_gateway_client
from backend.parent.phone_auth.service import mask_phone

PHONE = "+998901234567"


# ── Unit: TelegramGatewayClient ──────────────────────────────────────────────

def _client(handler):
    return TelegramGatewayClient(token="tg-token", base_url="https://gw.test", transport=httpx.MockTransport(handler))


def test_gateway_send_success_sends_correct_request():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"ok": True, "result": {"request_id": "rid-1", "phone_number": PHONE}})

    assert _client(handler).send_verification_message(PHONE, 6, 120) == "rid-1"
    assert seen == {"url": "https://gw.test/sendVerificationMessage", "auth": "Bearer tg-token",
                    "body": {"phone_number": PHONE, "code_length": 6, "ttl": 120}}


def test_gateway_send_timeout_is_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(GatewayError) as e:
        _client(handler).send_verification_message(PHONE, 6, 120)
    assert e.value.kind == "unavailable" and len(calls) == 1


def test_gateway_error_mapping():
    def make(status, body):
        return lambda req: httpx.Response(status, json=body)

    cases = [
        (make(400, {"ok": False, "error": "PHONE_NUMBER_INVALID"}), "not_reachable"),
        (make(429, {"ok": False, "error": "FLOOD_WAIT"}), "rate_limited"),
        (make(401, {"ok": False, "error": "ACCESS_TOKEN_INVALID"}), "config"),
        (make(400, {"ok": False, "error": "SOMETHING_ELSE"}), "rejected"),
        (make(502, {"ok": False}), "unavailable"),
    ]
    for handler, kind in cases:
        with pytest.raises(GatewayError) as e:
            _client(handler).send_verification_message(PHONE, 6, 120)
        assert e.value.kind == kind


def test_gateway_check_retries_only_connect_error():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("down", request=req)
        return httpx.Response(200, json={"ok": True, "result": {
            "request_id": "rid", "verification_status": {"status": "code_valid", "updated_at": 1}}})

    assert _client(handler).check_verification_status("rid", "123456") == "code_valid"
    assert len(calls) == 2


def test_gateway_without_token_is_config_error():
    with pytest.raises(GatewayError) as e:
        TelegramGatewayClient(token="").send_verification_message(PHONE, 6, 120)
    assert e.value.kind == "config"


def test_mask_phone():
    assert mask_phone(PHONE) == "+998*******67"[:4] + "*" * 7 + "67"
    assert mask_phone(PHONE).startswith("+998") and mask_phone(PHONE).endswith("67") and "9012345" not in mask_phone(PHONE)


# ── Integration ──────────────────────────────────────────────────────────────

class FakeGateway:
    configured = True

    def __init__(self):
        self.sent, self.revoked, self.checks = [], [], []
        self.statuses = []            # check_verification_status navbatdagi javoblari
        self.send_error = None
        self.check_error = None

    def send_verification_message(self, phone, code_length, ttl):
        if self.send_error:
            raise self.send_error
        self.sent.append((phone, code_length, ttl))
        return f"rid-{len(self.sent)}"

    def check_verification_status(self, request_id, code):
        if self.check_error:
            raise self.check_error
        self.checks.append((request_id, code))
        return self.statuses.pop(0) if self.statuses else "code_invalid"

    def revoke_verification_message(self, request_id):
        self.revoked.append(request_id)


@pytest.fixture
def gw():
    fake = FakeGateway()
    app.dependency_overrides[get_gateway_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_gateway_client, None)


def _request(client, phone=PHONE):
    return client.post("/auth/phone/request-code", json={"phoneNumber": phone})


def _verify(client, vid, code="123456", phone=PHONE):
    return client.post("/auth/phone/verify-code", json={"verificationId": vid, "phoneNumber": phone, "code": code})


def _age(db, vid, seconds):
    row = db.query(PhoneVerification).filter_by(public_id=vid).one()
    row.last_sent_at -= timedelta(seconds=seconds)
    row.created_at -= timedelta(seconds=seconds)
    row.expires_at -= timedelta(seconds=seconds)
    db.commit()


def test_request_code_success_shape(client, db, gw):
    r = _request(client, "+998 90 123-45-67")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"success", "verificationId", "expiresIn", "message"}
    assert body["success"] is True and body["expiresIn"] == 120 and len(body["verificationId"]) >= 16
    assert gw.sent == [(PHONE, 6, 120)]
    row = db.query(PhoneVerification).one()
    assert row.gateway_request_id == "rid-1" and row.status == "pending" and row.public_id != row.gateway_request_id
    assert "rid-1" not in r.text


def test_request_code_same_response_for_existing_and_new_user(client, db, gw):
    db.add(Parent(full_name="Bor", phone=PHONE, username=PHONE, hashed_password="x", is_active=True))
    db.commit()
    a = _request(client).json()
    b = _request(client, "+998901234568").json()
    assert set(a) == set(b) and a["message"] == b["message"] and a["expiresIn"] == b["expiresIn"]


@pytest.mark.parametrize("phone", ["12345", "+99890123456", "+998 90 123 45 6789", "abc", "+12025550123"])
def test_invalid_phone_400(client, db, gw, phone):
    r = _request(client, phone)
    assert r.status_code == 400 and r.json()["code"] in ("invalid_phone_number", "phone_not_supported", "validation_error")
    assert gw.sent == []


def test_validation_errors_are_400(client, db, gw):
    assert client.post("/auth/phone/request-code", json={}).status_code == 400
    assert client.post("/auth/phone/request-code", json={"phoneNumber": PHONE, "x": 1}).status_code == 400
    assert _verify(client, "a" * 20, code="12ab56").status_code == 400
    r = client.post("/auth/phone/request-code", content=b"{bad", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["code"] == "invalid_json"


def test_verify_correct_code_registers_new_parent(client, db, gw):
    vid = _request(client).json()["verificationId"]
    gw.statuses = ["code_valid"]
    r = _verify(client, vid)
    assert r.status_code == 200 and set(r.json()) == {"access_token", "refresh_token"}
    assert gw.checks == [("rid-1", "123456")]
    p = db.query(Parent).one()
    assert p.phone == PHONE and p.phone_verified_at is not None and p.is_active
    prof = client.get("/parent/profile", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert prof.status_code == 200 and prof.json()["phone"] == PHONE
    assert client.get("/parent/children", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json() == []


def test_verify_logs_in_existing_parent_with_children(client, db, gw):
    s = Student(full_name="Alibek", phone1="+998900000001", is_active=True)
    p = Parent(full_name="Nodira", phone="+998 90 123 45 67", username="nodira", hashed_password="x", is_active=True)
    db.add_all([s, p]); db.flush()
    db.add(ParentChild(parent_id=p.id, student_id=s.id)); db.commit()
    vid = _request(client).json()["verificationId"]
    gw.statuses = ["code_valid"]
    tok = _verify(client, vid).json()["access_token"]
    assert db.query(Parent).count() == 1
    kids = client.get("/parent/children", headers={"Authorization": f"Bearer {tok}"}).json()
    assert [k["full_name"] for k in kids] == ["Alibek"]


def test_verify_disabled_parent_403(client, db, gw):
    db.add(Parent(full_name="X", phone=PHONE, username=PHONE, hashed_password="x", is_active=False)); db.commit()
    vid = _request(client).json()["verificationId"]
    gw.statuses = ["code_valid"]
    assert _verify(client, vid).status_code == 403


def test_verification_cannot_be_reused(client, db, gw):
    vid = _request(client).json()["verificationId"]
    gw.statuses = ["code_valid", "code_valid"]
    assert _verify(client, vid).status_code == 200
    r = _verify(client, vid)
    assert r.status_code == 409 and r.json()["code"] == "verification_already_used"
    assert len(gw.checks) == 1


def test_wrong_code_then_max_attempts(client, db, gw):
    vid = _request(client).json()["verificationId"]
    for left in (4, 3, 2, 1):
        r = _verify(client, vid, code="000000")
        assert r.status_code == 401 and r.json()["code"] == "code_invalid" and str(left) in r.json()["message"]
    r = _verify(client, vid, code="000000")
    assert r.status_code == 429 and r.json()["code"] == "code_max_attempts_exceeded"
    gw.statuses = ["code_valid"]
    r = _verify(client, vid)              # 6-urinish Gateway'ga umuman bormaydi
    assert r.status_code == 429 and len(gw.checks) == 5


def test_gateway_reports_max_attempts_and_expired(client, db, gw):
    vid = _request(client).json()["verificationId"]
    gw.statuses = ["code_max_attempts_exceeded"]
    assert _verify(client, vid).status_code == 429
    _age(db, vid, 61)
    vid2 = _request(client).json()["verificationId"]
    gw.statuses = ["expired"]
    r = _verify(client, vid2)
    assert r.status_code == 401 and r.json()["code"] == "code_expired"


def test_expired_locally_does_not_call_gateway(client, db, gw):
    vid = _request(client).json()["verificationId"]
    _age(db, vid, 121)
    r = _verify(client, vid)
    assert r.status_code == 401 and r.json()["code"] == "code_expired" and gw.checks == []


def test_not_found_and_phone_mismatch(client, db, gw):
    vid = _request(client).json()["verificationId"]
    r = _verify(client, "x" * 32)
    assert r.status_code == 404 and r.json()["code"] == "verification_not_found"
    r = _verify(client, vid, phone="+998901234568")
    assert r.status_code == 400 and r.json()["code"] == "phone_mismatch"


def test_resend_cooldown_and_replacement(client, db, gw):
    vid = _request(client).json()["verificationId"]
    body = {"verificationId": vid, "phoneNumber": PHONE}
    r = client.post("/auth/phone/resend-code", json=body)
    assert r.status_code == 429 and r.json()["code"] == "resend_cooldown" and int(r.headers["retry-after"]) > 0
    assert _request(client).status_code == 429          # request-code ham 60 s kutadi
    _age(db, vid, 61)
    r = client.post("/auth/phone/resend-code", json=body)
    assert r.status_code == 200
    new_vid = r.json()["verificationId"]
    assert new_vid != vid and gw.revoked == ["rid-1"] and len(gw.sent) == 2
    assert db.query(PhoneVerification).filter_by(status="pending").count() == 1
    old = _verify(client, vid)
    assert old.status_code == 409 and old.json()["code"] == "verification_superseded"
    gw.statuses = ["code_valid"]
    assert _verify(client, new_vid).status_code == 200
    assert gw.checks[-1][0] == "rid-2"


def test_resend_limit(client, db, gw):
    vid = _request(client).json()["verificationId"]
    for _ in range(3):
        _age(db, vid, 61)
        r = client.post("/auth/phone/resend-code", json={"verificationId": vid, "phoneNumber": PHONE})
        assert r.status_code == 200, r.text
        vid = r.json()["verificationId"]
    _age(db, vid, 61)
    r = client.post("/auth/phone/resend-code", json={"verificationId": vid, "phoneNumber": PHONE})
    assert r.status_code == 429 and r.json()["code"] == "too_many_resends"


def test_rate_limit_per_phone(client, db, gw):
    for i in range(5):
        r = _request(client)
        assert r.status_code == 200, r.text
        _age(db, r.json()["verificationId"], 61)
    r = _request(client)
    assert r.status_code == 429 and r.headers.get("retry-after")
    assert len(gw.sent) == 5


def test_gateway_timeout_and_errors_on_send(client, db, gw):
    gw.send_error = GatewayError("unavailable", "timeout")
    r = _request(client)
    assert r.status_code == 503 and r.json()["code"] == "gateway_unavailable"
    assert db.query(PhoneVerification).one().status == "failed"     # keyingi so'rovni bloklamaydi
    gw.send_error = GatewayError("not_reachable", "PHONE_NOT_ON_TELEGRAM")
    r = _request(client)
    assert r.status_code == 400 and r.json()["code"] == "telegram_not_available"
    assert "PHONE_NOT_ON_TELEGRAM" not in r.text
    gw.send_error = GatewayError("rejected", "WEIRD")
    assert _request(client).status_code == 502


def test_gateway_timeout_on_verify(client, db, gw):
    vid = _request(client).json()["verificationId"]
    gw.check_error = GatewayError("unavailable", "timeout")
    r = _verify(client, vid)
    assert r.status_code == 503 and r.json()["code"] == "gateway_unavailable"


def test_gateway_not_configured_503(client, db):
    class Unconfigured(FakeGateway):
        configured = False
    app.dependency_overrides[get_gateway_client] = lambda: Unconfigured()
    try:
        r = _request(client)
        assert r.status_code == 503 and r.json()["code"] == "gateway_unavailable"
    finally:
        app.dependency_overrides.pop(get_gateway_client, None)


def test_single_active_verification_per_phone(client, db, gw):
    _request(client)
    # Parallel so'rov: rezerv qatori bor (hali yuborilmagan) — unikal indeks ikkinchisini to'xtatadi
    db.add(PhoneVerification(public_id="p" * 20, phone="+998901234568", status="pending",
                             expires_at=datetime.utcnow() + timedelta(seconds=120)))
    db.commit()
    from sqlalchemy.exc import IntegrityError
    db.add(PhoneVerification(public_id="q" * 20, phone="+998901234568", status="pending",
                             expires_at=datetime.utcnow() + timedelta(seconds=120)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
