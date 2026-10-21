"""Payme (Paycom) Merchant API — JSON-RPC 2.0, POST /payment-callbacks/payme.

Autentifikatsiya: `Authorization: Basic base64("Paycom:<PAYME_KEY>")`.
Summalar provayderda tiyinda (1 so'm = 100 tiyin), bizda so'mda.
Javob har doim HTTP 200 (Payme talabi), xato `error` obyektida.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
from decimal import Decimal
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models
from . import config, core

log = logging.getLogger("ithub.payments.payme")

TIMEOUT_MS = 43_200_000  # 12 soat — Payme protokoli bo'yicha "created" tranzaksiya umri

# Payme tranzaksiya holatlari
ST_CREATED, ST_PERFORMED, ST_CANCELLED, ST_CANCELLED_AFTER = 1, 2, -1, -2

E_AUTH = -32504
E_METHOD = -32601
E_PARSE = -32700
E_RPC = -32600
E_AMOUNT = -31001
E_TXN_NOT_FOUND = -31003
E_CANNOT_CANCEL = -31007
E_CANNOT_PERFORM = -31008
E_ACCOUNT = -31050
E_ACCOUNT_BUSY = -31099
E_SYSTEM = -32400

_MSG = {
    E_AUTH: ("Avtorizatsiya xatosi", "Ошибка авторизации", "Authorization error"),
    E_METHOD: ("Metod topilmadi", "Метод не найден", "Method not found"),
    E_PARSE: ("JSON xato", "Ошибка разбора JSON", "Parse error"),
    E_RPC: ("So'rov noto'g'ri", "Неверный запрос", "Invalid request"),
    E_AMOUNT: ("Summa noto'g'ri", "Неверная сумма", "Invalid amount"),
    E_TXN_NOT_FOUND: ("Tranzaksiya topilmadi", "Транзакция не найдена", "Transaction not found"),
    E_CANNOT_CANCEL: ("Bekor qilib bo'lmaydi", "Невозможно отменить", "Cannot cancel"),
    E_CANNOT_PERFORM: ("Amalni bajarib bo'lmaydi", "Невозможно выполнить операцию", "Cannot perform"),
    E_ACCOUNT: ("Invoys topilmadi yoki to'lab bo'lmaydi", "Счёт не найден или недоступен", "Invoice not found"),
    E_ACCOUNT_BUSY: ("Invoys bo'yicha boshqa tranzaksiya kutilmoqda", "Счёт ожидает оплаты", "Invoice is busy"),
    E_SYSTEM: ("Tizim xatosi", "Системная ошибка", "System error"),
}

_STATE = {"created": ST_CREATED, "performed": ST_PERFORMED,
          "cancelled": ST_CANCELLED, "reversed": ST_CANCELLED_AFTER}


class PaymeError(Exception):
    def __init__(self, code: int, data: Optional[str] = None):
        self.code, self.data = code, data


def checkout_url(inv: models.ParentInvoice) -> str:
    parts = [f"m={config.payme_merchant_id()}",
             f"ac.{config.payme_account_field()}={inv.id}",
             f"a={core.invoice_amount(inv) * 100}"]
    ret = config.return_url()
    if ret:
        parts.append(f"c={ret}")
    token = base64.b64encode(";".join(parts).encode()).decode()
    return f"{config.payme_checkout_base()}/{token}"


def _auth_ok(request: Request) -> bool:
    key = config.payme_key()
    header = request.headers.get("authorization", "")
    if not key or not header.lower().startswith("basic "):
        return False
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return False
    login, _, pwd = raw.partition(":")
    return login == "Paycom" and hmac.compare_digest(pwd, key)


def _err(req_id, code: int, data: Optional[str] = None) -> JSONResponse:
    uz, ru, en = _MSG.get(code, _MSG[E_SYSTEM])
    err = {"code": code, "message": {"uz": uz, "ru": ru, "en": en}}
    if data:
        err["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": err})


def _txn_json(t: models.PaymentTransaction) -> dict:
    return {
        "create_time": t.create_time,
        "perform_time": t.perform_time or 0,
        "cancel_time": t.cancel_time or 0,
        "transaction": str(t.id),
        "state": _STATE[t.state],
        "reason": t.cancel_reason,
    }


def _amount_tiyin(params: dict) -> int:
    amount = params.get("amount")
    # Payme Amount is a positive integer number of tiyin. int(50000.5) would
    # silently truncate and could turn an invalid amount into a valid payment.
    if type(amount) is not int or amount <= 0:
        raise PaymeError(E_AMOUNT)
    return amount


def _payable_invoice(db: Session, params: dict, exclude_txn: Optional[str] = None,
                     busy_code: int = E_ACCOUNT_BUSY) -> models.ParentInvoice:
    field = config.payme_account_field()
    account = params.get("account")
    if not isinstance(account, dict):
        raise PaymeError(E_ACCOUNT, field)
    inv = core.lock_invoice(db, account.get(field))
    if not inv or inv.provider != "payme":
        raise PaymeError(E_ACCOUNT, field)
    if inv.status != "pending" or core.invoice_expired(inv):
        raise PaymeError(E_ACCOUNT, field)
    if _amount_tiyin(params) != core.invoice_amount(inv) * 100:
        raise PaymeError(E_AMOUNT)
    busy = core.active_txn(inv, exclude_id=exclude_txn)
    if busy is not None:
        raise PaymeError(busy_code, field if busy_code == E_ACCOUNT_BUSY else None)
    return inv


def _check_perform(db, params):
    _payable_invoice(db, params)
    return {"allow": True}


def _timed_out(txn: models.PaymentTransaction) -> bool:
    # Payme's 12-hour limit starts at the timestamp in CreateTransaction.time,
    # not when our database happened to process the callback.
    return core.now_ms() - (txn.provider_time or txn.create_time) >= TIMEOUT_MS


def _create(db, params):
    pid = str(params.get("id") or "")
    if not pid:
        raise PaymeError(E_RPC)
    provider_time = params.get("time")
    if type(provider_time) is not int or provider_time <= 0:
        raise PaymeError(E_RPC)
    txn = core.lock_txn(db, "payme", pid)
    if txn:
        field = config.payme_account_field()
        account = params.get("account")
        if not isinstance(account, dict) or str(account.get(field)) != str(txn.invoice_id):
            raise PaymeError(E_ACCOUNT, field)
        if _amount_tiyin(params) != core.invoice_amount(txn.invoice) * 100:
            raise PaymeError(E_AMOUNT)
        if txn.provider_time is not None and provider_time != txn.provider_time:
            raise PaymeError(E_CANNOT_PERFORM)
        if txn.state != "created":
            raise PaymeError(E_CANNOT_PERFORM)
        if _timed_out(txn):
            core.cancel(db, txn.invoice, txn, reason=4)
            db.commit()
            raise PaymeError(E_CANNOT_PERFORM)
        return {"create_time": txn.create_time, "transaction": str(txn.id), "state": ST_CREATED}
    if core.now_ms() - provider_time >= TIMEOUT_MS:
        raise PaymeError(E_CANNOT_PERFORM)
    inv = _payable_invoice(db, params, exclude_txn=pid, busy_code=E_CANNOT_PERFORM)
    txn = models.PaymentTransaction(
        invoice_id=inv.id, provider="payme", provider_txn_id=pid, state="created",
        amount=inv.amount, provider_time=provider_time,
        create_time=core.now_ms(),
    )
    db.add(txn)
    db.flush()
    return {"create_time": txn.create_time, "transaction": str(txn.id), "state": ST_CREATED}


def _perform(db, params):
    txn = core.lock_txn(db, "payme", str(params.get("id") or ""))
    if not txn:
        raise PaymeError(E_TXN_NOT_FOUND)
    inv = core.lock_invoice(db, txn.invoice_id)
    if txn.state == "created":
        if _timed_out(txn):
            core.cancel(db, inv, txn, reason=4)
            db.commit()
            raise PaymeError(E_CANNOT_PERFORM)
        if inv.status != "pending":
            raise PaymeError(E_CANNOT_PERFORM)
        core.perform(db, inv, txn)
    elif txn.state != "performed":
        raise PaymeError(E_CANNOT_PERFORM)
    return {"transaction": str(txn.id), "perform_time": txn.perform_time, "state": ST_PERFORMED}


def _cancel(db, params):
    txn = core.lock_txn(db, "payme", str(params.get("id") or ""))
    if not txn:
        raise PaymeError(E_TXN_NOT_FOUND)
    inv = core.lock_invoice(db, txn.invoice_id)
    if txn.state == "performed" and not config.allow_refund():
        raise PaymeError(E_CANNOT_CANCEL)
    try:
        reason = int(params.get("reason")) if params.get("reason") is not None else None
    except (TypeError, ValueError):
        reason = None
    core.cancel(db, inv, txn, reason=reason)
    return {"transaction": str(txn.id), "cancel_time": txn.cancel_time, "state": _STATE[txn.state]}


def _check(db, params):
    txn = (db.query(models.PaymentTransaction)
           .filter(models.PaymentTransaction.provider == "payme",
                   models.PaymentTransaction.provider_txn_id == str(params.get("id") or ""))
           .first())
    if not txn:
        raise PaymeError(E_TXN_NOT_FOUND)
    return _txn_json(txn)


def _statement(db, params):
    try:
        t_from, t_to = int(params.get("from")), int(params.get("to"))
    except (TypeError, ValueError):
        raise PaymeError(E_RPC)
    payme_time = func.coalesce(models.PaymentTransaction.provider_time,
                              models.PaymentTransaction.create_time)
    rows = (db.query(models.PaymentTransaction)
            .filter(models.PaymentTransaction.provider == "payme",
                    payme_time >= t_from,
                    payme_time <= t_to)
            .order_by(payme_time.asc(), models.PaymentTransaction.id.asc())
            .all())
    field = config.payme_account_field()
    out = []
    for t in rows:
        item = _txn_json(t)
        item.update({
            "id": t.provider_txn_id, "time": t.provider_time or t.create_time,
            "amount": int(Decimal(str(t.amount)) * 100), "account": {field: str(t.invoice_id)},
        })
        out.append(item)
    return {"transactions": out}


_METHODS = {
    "CheckPerformTransaction": _check_perform,
    "CreateTransaction": _create,
    "PerformTransaction": _perform,
    "CancelTransaction": _cancel,
    "CheckTransaction": _check,
    "GetStatement": _statement,
}


async def handle(request: Request, db: Session) -> JSONResponse:
    try:
        body = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _err(None, E_PARSE)
    req_id = body.get("id") if isinstance(body, dict) else None
    if not config.is_configured("payme") or not _auth_ok(request):
        return _err(req_id, E_AUTH)
    if not isinstance(body, dict) or not isinstance(body.get("params"), dict):
        return _err(req_id, E_RPC)
    fn = _METHODS.get(body.get("method"))
    if fn is None:
        return _err(req_id, E_METHOD)
    try:
        result = fn(db, body["params"])
        db.commit()
    except PaymeError as e:
        db.rollback()
        return _err(req_id, e.code, e.data)
    except IntegrityError:
        # Parallel CreateTransaction bir xil id bilan — ikkinchisi unique'ga uriladi.
        db.rollback()
        return _err(req_id, E_CANNOT_PERFORM)
    except Exception:
        db.rollback()
        log.exception("payme %s failed", body.get("method"))
        return _err(req_id, E_SYSTEM)
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})
