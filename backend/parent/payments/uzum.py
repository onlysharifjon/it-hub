"""Uzum Bank Merchant API (webhook) — check / create / confirm / reverse / status.

POST /payment-callbacks/uzum/{operation}, JSON, `Authorization: Basic base64(login:password)`.
`serviceId` sozlamadagi bilan mos bo'lishi shart. Summalar tiyinda, vaqtlar ms.
Muvaffaqiyat — HTTP 200; xato — HTTP 400 + {"status": "FAILED", "errorCode": "100xx"}.
Invoys ID'si `params.<UZUM_ACCOUNT_FIELD>` (standart: order_id) da keladi.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models
from . import config, core

log = logging.getLogger("ithub.payments.uzum")

E_ACCESS, E_JSON, E_OPERATION, E_MISSING, E_SERVICE, E_ACCOUNT = 10001, 10002, 10003, 10005, 10006, 10007
E_PROCESSED, E_CANCELLED, E_TRANS_EXISTS, E_AMOUNT = 10008, 10009, 10010, 10011
E_TRANS_NOT_FOUND, E_TRANS_CANCELLED, E_CANNOT_REVERSE, E_REVERSED, E_UNAVAILABLE = 10014, 10015, 10017, 10018, 99999

_STATUS = {"created": "CREATED", "performed": "CONFIRMED", "cancelled": "FAILED", "reversed": "REVERSED"}


class UzumError(Exception):
    def __init__(self, code: int):
        self.code = code


def checkout_url(inv: models.ParentInvoice) -> str:
    q = {"serviceId": config.uzum_service_id(), config.uzum_account_field(): inv.id,
         "amount": core.invoice_amount(inv) * 100}
    ret = config.return_url()
    if ret:
        q["redirectUrl"] = ret
    return f"{config.uzum_checkout_base()}?{urlencode(q)}"


def _auth_ok(request: Request) -> bool:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return False
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return False
    login, _, pwd = raw.partition(":")
    return hmac.compare_digest(login, config.uzum_login()) and hmac.compare_digest(pwd, config.uzum_password())


def _fail(service_id, code: int) -> JSONResponse:
    return JSONResponse(status_code=400, content={
        "serviceId": service_id, "timestamp": core.now_ms(), "status": "FAILED", "errorCode": str(code)})


def _account_value(body: dict) -> Optional[str]:
    params = body.get("params") or {}
    if not isinstance(params, dict):
        return None
    for key in (config.uzum_account_field(), "order_id", "invoice_id", "account"):
        if key in params:
            v = params[key]
            return str(v.get("value") if isinstance(v, dict) else v)
    return None


def _account_data(inv: models.ParentInvoice) -> dict:
    return {"account": {"value": str(inv.id)}}


def _payable(db: Session, body: dict) -> models.ParentInvoice:
    inv = core.lock_invoice(db, _account_value(body))
    if not inv or inv.provider != "uzum":
        raise UzumError(E_ACCOUNT)
    if inv.status == "paid":
        raise UzumError(E_PROCESSED)
    if inv.status != "pending" or core.invoice_expired(inv):
        raise UzumError(E_CANCELLED)
    return inv


def _txn(db: Session, body: dict) -> models.PaymentTransaction:
    tid = str(body.get("transId") or "")
    if not tid:
        raise UzumError(E_MISSING)
    txn = core.lock_txn(db, "uzum", tid)
    if not txn:
        raise UzumError(E_TRANS_NOT_FOUND)
    return txn


def _op_check(db, body, sid):
    inv = _payable(db, body)
    return {"serviceId": sid, "timestamp": core.now_ms(), "status": "OK", "data": _account_data(inv)}


def _op_create(db, body, sid):
    tid = str(body.get("transId") or "")
    if not tid or body.get("amount") is None:
        raise UzumError(E_MISSING)
    if core.lock_txn(db, "uzum", tid) is not None:
        raise UzumError(E_TRANS_EXISTS)
    inv = _payable(db, body)
    try:
        amount = int(body["amount"])
    except (TypeError, ValueError):
        raise UzumError(E_AMOUNT)
    if amount != core.invoice_amount(inv) * 100:
        raise UzumError(E_AMOUNT)
    if core.active_txn(inv) is not None:
        raise UzumError(E_PROCESSED)
    txn = models.PaymentTransaction(
        invoice_id=inv.id, provider="uzum", provider_txn_id=tid, state="created",
        amount=inv.amount, provider_time=int(body.get("timestamp") or 0) or None, create_time=core.now_ms(),
    )
    db.add(txn)
    db.flush()
    return {"serviceId": sid, "transId": tid, "status": "CREATED", "transTime": txn.create_time,
            "data": _account_data(inv), "amount": amount}


def _op_confirm(db, body, sid):
    txn = _txn(db, body)
    inv = core.lock_invoice(db, txn.invoice_id)
    if txn.state in ("cancelled", "reversed"):
        raise UzumError(E_TRANS_CANCELLED)
    if txn.state == "created":
        if inv.status != "pending":
            raise UzumError(E_PROCESSED if inv.status == "paid" else E_CANCELLED)
        core.perform(db, inv, txn)
    return {"serviceId": sid, "transId": txn.provider_txn_id, "status": "CONFIRMED",
            "confirmTime": txn.perform_time, "data": _account_data(inv),
            "amount": int(Decimal(str(txn.amount)) * 100)}


def _op_reverse(db, body, sid):
    txn = _txn(db, body)
    inv = core.lock_invoice(db, txn.invoice_id)
    if txn.state in ("cancelled", "reversed"):
        raise UzumError(E_REVERSED)
    if txn.state == "performed" and not config.allow_refund():
        raise UzumError(E_CANNOT_REVERSE)
    core.cancel(db, inv, txn)
    return {"serviceId": sid, "transId": txn.provider_txn_id, "status": "REVERSED",
            "reverseTime": txn.cancel_time, "data": _account_data(inv),
            "amount": int(Decimal(str(txn.amount)) * 100)}


def _op_status(db, body, sid):
    txn = _txn(db, body)
    return {"serviceId": sid, "transId": txn.provider_txn_id, "status": _STATUS[txn.state],
            "transTime": txn.create_time, "confirmTime": txn.perform_time, "reverseTime": txn.cancel_time,
            "data": _account_data(txn.invoice), "amount": int(Decimal(str(txn.amount)) * 100)}


_OPS = {"check": _op_check, "create": _op_create, "confirm": _op_confirm,
        "reverse": _op_reverse, "status": _op_status}


async def handle(request: Request, db: Session, operation: str) -> JSONResponse:
    try:
        body = json.loads(await request.body())
        if not isinstance(body, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return _fail(None, E_JSON)
    sid = body.get("serviceId")
    if not config.is_configured("uzum") or not _auth_ok(request):
        return _fail(sid, E_ACCESS)
    if str(sid) != config.uzum_service_id():
        return _fail(sid, E_SERVICE)
    fn = _OPS.get(operation)
    if fn is None:
        return _fail(sid, E_OPERATION)
    try:
        result = fn(db, body, sid)
        db.commit()
    except UzumError as e:
        db.rollback()
        return _fail(sid, e.code)
    except IntegrityError:
        db.rollback()
        return _fail(sid, E_TRANS_EXISTS)
    except Exception:
        db.rollback()
        log.exception("uzum %s failed", operation)
        return _fail(sid, E_UNAVAILABLE)
    return JSONResponse(result)
