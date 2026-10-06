"""Click SHOP API — Prepare (action=0) va Complete (action=1).

POST /payment-callbacks/click/prepare  va  /payment-callbacks/click/complete
(application/x-www-form-urlencoded). Imzo:
  prepare : md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time)
  complete: md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + merchant_prepare_id
                + amount + action + sign_time)
merchant_trans_id = bizning invoys ID'si. Summalar so'mda.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models
from . import config, core

log = logging.getLogger("ithub.payments.click")

OK, E_SIGN, E_AMOUNT, E_ACTION, E_PAID, E_ORDER, E_TXN, E_UPDATE, E_REQUEST, E_CANCELLED = (
    0, -1, -2, -3, -4, -5, -6, -7, -8, -9)
_NOTE = {
    OK: "Success", E_SIGN: "SIGN CHECK FAILED!", E_AMOUNT: "Incorrect parameter amount",
    E_ACTION: "Action not found", E_PAID: "Already paid", E_ORDER: "User does not exist",
    E_TXN: "Transaction does not exist", E_UPDATE: "Failed to update user",
    E_REQUEST: "Error in request from click", E_CANCELLED: "Transaction cancelled",
}


def checkout_url(inv: models.ParentInvoice) -> str:
    q = {
        "service_id": config.click_service_id(),
        "merchant_id": config.click_merchant_id(),
        "amount": core.invoice_amount(inv),
        "transaction_param": inv.id,
    }
    ret = config.return_url()
    if ret:
        q["return_url"] = ret
    return f"{config.click_checkout_base()}?{urlencode(q)}"


def _sign_ok(f: dict, with_prepare_id: bool) -> bool:
    parts = [f.get("click_trans_id", ""), f.get("service_id", ""), config.click_secret_key(),
             f.get("merchant_trans_id", "")]
    if with_prepare_id:
        parts.append(f.get("merchant_prepare_id", ""))
    parts += [f.get("amount", ""), f.get("action", ""), f.get("sign_time", "")]
    expected = hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()
    return hmac.compare_digest(expected, str(f.get("sign_string", "")).lower())


def _resp(f: dict, error: int, **extra) -> JSONResponse:
    body = {"click_trans_id": f.get("click_trans_id"), "merchant_trans_id": f.get("merchant_trans_id"),
            "error": error, "error_note": _NOTE.get(error, "Error")}
    body.update(extra)
    return JSONResponse(body)


def _amount(f: dict):
    try:
        return Decimal(str(f.get("amount")))
    except (InvalidOperation, TypeError):
        return None


async def handle(request: Request, db: Session, action: int) -> JSONResponse:
    form = dict(await request.form())
    if not config.is_configured("click"):
        return _resp(form, E_REQUEST)
    required = ["click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time", "sign_string"]
    if action == 1:
        required.append("merchant_prepare_id")
    if any(not str(form.get(k, "")).strip() for k in required):
        return _resp(form, E_REQUEST)
    if not _sign_ok(form, with_prepare_id=(action == 1)):
        return _resp(form, E_SIGN)
    if str(form.get("service_id")) != config.click_service_id():
        return _resp(form, E_REQUEST)
    if str(form.get("action")) != str(action):
        return _resp(form, E_ACTION)
    try:
        if action == 0:
            res = _prepare(db, form)
        else:
            res = _complete(db, form)
        db.commit()
        return res
    except IntegrityError:
        db.rollback()
        return _resp(form, E_UPDATE)
    except Exception:
        db.rollback()
        log.exception("click action=%s failed", action)
        return _resp(form, E_UPDATE)


def _prepare(db: Session, f: dict) -> JSONResponse:
    inv = core.lock_invoice(db, f.get("merchant_trans_id"))
    if not inv or inv.provider != "click":
        return _resp(f, E_ORDER)
    amount = _amount(f)
    if amount is None or amount != Decimal(core.invoice_amount(inv)):
        return _resp(f, E_AMOUNT)
    if inv.status == "paid":
        return _resp(f, E_PAID)
    if inv.status != "pending" or core.invoice_expired(inv):
        return _resp(f, E_CANCELLED)
    ctid = str(f["click_trans_id"])
    txn = core.lock_txn(db, "click", ctid)
    if txn is None:
        if core.active_txn(inv, exclude_id=ctid) is not None:
            return _resp(f, E_PAID)
        txn = models.PaymentTransaction(
            invoice_id=inv.id, provider="click", provider_txn_id=ctid, state="created",
            amount=inv.amount, create_time=core.now_ms(),
        )
        db.add(txn)
        db.flush()
    elif txn.invoice_id != inv.id or txn.state != "created":
        return _resp(f, E_TXN)
    return _resp(f, OK, merchant_prepare_id=txn.id)


def _complete(db: Session, f: dict) -> JSONResponse:
    ctid = str(f["click_trans_id"])
    txn = core.lock_txn(db, "click", ctid)
    if txn is None or str(txn.id) != str(f.get("merchant_prepare_id")):
        return _resp(f, E_TXN)
    inv = core.lock_invoice(db, txn.invoice_id)
    if inv is None or str(inv.id) != str(f.get("merchant_trans_id")):
        return _resp(f, E_ORDER)
    amount = _amount(f)
    if amount is None or amount != Decimal(core.invoice_amount(inv)):
        return _resp(f, E_AMOUNT)
    try:
        click_error = int(f.get("error") or 0)
    except ValueError:
        click_error = 0
    if txn.state == "performed":
        return _resp(f, OK, merchant_confirm_id=txn.id)   # takroriy Complete — idempotent
    if txn.state in ("cancelled", "reversed"):
        return _resp(f, E_CANCELLED)
    if click_error < 0:
        core.cancel(db, inv, txn, reason=click_error)
        return _resp(f, E_CANCELLED)
    if inv.status != "pending":
        return _resp(f, E_PAID if inv.status == "paid" else E_CANCELLED)
    core.perform(db, inv, txn)
    return _resp(f, OK, merchant_confirm_id=txn.id)
