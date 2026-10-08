"""Payme Merchant API (JSON-RPC) — POST /payme (nginx orqali /api/payme).

Payme kabinetida "Endpoint URL": https://crm.minaracademy.uz/api/payme
Hisob maydoni (account): PAYME_ACCOUNT_FIELD (default "order_id") = ParentInvoice.id.

Oqim: ota-ona /parent/children/{id}/pay -> invoys + checkout havolasi -> Payme
CheckPerform/Create/Perform -> PerformTransaction'da CRM'ga Payment yoziladi.

Sozlamalar (.env):
  PAYME_MERCHANT_ID   — kassa ID
  PAYME_KEY           — kassa kaliti (test rejimda test kaliti)
  PAYME_TEST_MODE     — true: checkout.test.paycom.uz (default true)
  PAYME_ACCOUNT_FIELD — default order_id
  PAYME_RETURN_URL    — to'lovdan keyin qaytish manzili (ixtiyoriy)
"""
from __future__ import annotations

import base64
import binascii
import hmac
import os
import time
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import models, tz
from .database import get_db
from .parent.notifications import notify_parents_of_student

router = APIRouter(tags=["payme"])

TIMEOUT_MS = 12 * 60 * 60 * 1000  # Payme: yaratilgan tranzaksiya 12 soatdan keyin eskiradi

STATE_CREATED = 1
STATE_PERFORMED = 2
STATE_CANCELLED = -1
STATE_CANCELLED_AFTER_PERFORM = -2
REASON_TIMEOUT = 4


def merchant_id() -> str:
    return os.getenv("PAYME_MERCHANT_ID", "").strip()


def _key() -> str:
    return os.getenv("PAYME_KEY", "").strip()


def _test_mode() -> bool:
    return os.getenv("PAYME_TEST_MODE", "true").strip().lower() in ("1", "true", "yes")


def account_field() -> str:
    return os.getenv("PAYME_ACCOUNT_FIELD", "order_id").strip() or "order_id"


def is_configured() -> bool:
    return bool(merchant_id() and _key())


def checkout_url(invoice: models.ParentInvoice) -> str:
    """Payme checkout havolasi (GET, base64 parametrlar)."""
    params = f"m={merchant_id()};ac.{account_field()}={invoice.id};a={_tiyin(invoice.amount)}"
    ret = os.getenv("PAYME_RETURN_URL", "").strip()
    if ret:
        params += f";c={ret}"
    host = "https://checkout.test.paycom.uz" if _test_mode() else "https://checkout.paycom.uz"
    return f"{host}/{base64.b64encode(params.encode()).decode()}"


def _tiyin(amount) -> int:
    return int(Decimal(str(amount)) * 100)


def _now_ms() -> int:
    return int(time.time() * 1000)


class PaymeError(Exception):
    def __init__(self, code: int, uz: str, ru: str, en: str, data: str | None = None):
        self.code, self.message, self.data = code, {"uz": uz, "ru": ru, "en": en}, data


def _err_order_not_found():
    return PaymeError(-31050, "Buyurtma topilmadi", "Заказ не найден", "Order not found", account_field())


def _err_tx_not_found():
    return PaymeError(-31003, "Tranzaksiya topilmadi", "Транзакция не найдена", "Transaction not found")


def _err_cannot_perform():
    return PaymeError(-31008, "Amalni bajarib bo'lmaydi", "Невозможно выполнить операцию",
                      "Unable to perform operation")


def _authorized(request: Request) -> bool:
    key = _key()
    header = request.headers.get("authorization", "")
    if not key or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode()
    except (binascii.Error, UnicodeDecodeError):
        return False
    login, _, password = decoded.partition(":")
    return login == "Paycom" and hmac.compare_digest(password.encode(), key.encode())


# ── Metodlar ─────────────────────────────────────────────────────────────────

def _find_invoice(db: Session, params: dict, lock: bool = False) -> models.ParentInvoice:
    raw = (params.get("account") or {}).get(account_field())
    try:
        invoice_id = int(raw)
    except (TypeError, ValueError):
        raise _err_order_not_found()
    q = db.query(models.ParentInvoice).filter(
        models.ParentInvoice.id == invoice_id, models.ParentInvoice.provider == "payme")
    if lock:
        q = q.with_for_update()
    invoice = q.first()
    if not invoice:
        raise _err_order_not_found()
    return invoice


def _check_invoice(invoice: models.ParentInvoice, amount) -> None:
    if invoice.status != "pending":
        raise PaymeError(-31051, "Buyurtma to'langan yoki bekor qilingan",
                         "Заказ уже оплачен или отменён", "Order already paid or cancelled", account_field())
    if not isinstance(amount, int) or amount != _tiyin(invoice.amount):
        raise PaymeError(-31001, "Noto'g'ri summa", "Неверная сумма", "Invalid amount")


def _get_tx(db: Session, params: dict, lock: bool = False) -> models.PaymeTransaction:
    q = db.query(models.PaymeTransaction).filter(models.PaymeTransaction.paycom_id == str(params.get("id")))
    if lock:
        q = q.with_for_update()
    tx = q.first()
    if not tx:
        raise _err_tx_not_found()
    return tx


def _cancel(db: Session, tx: models.PaymeTransaction, reason: int | None) -> None:
    if tx.state == STATE_PERFORMED:
        if tx.payment_id:
            payment = db.query(models.Payment).filter(models.Payment.id == tx.payment_id).first()
            tx.payment_id = None
            if payment:
                db.delete(payment)
        tx.state = STATE_CANCELLED_AFTER_PERFORM
    else:
        tx.state = STATE_CANCELLED
    tx.reason = reason
    tx.cancel_time = _now_ms()
    tx.invoice.status = "cancelled"


def check_perform_transaction(db: Session, params: dict) -> dict:
    _check_invoice(_find_invoice(db, params), params.get("amount"))
    return {"allow": True}


def create_transaction(db: Session, params: dict) -> dict:
    tx = db.query(models.PaymeTransaction).filter(
        models.PaymeTransaction.paycom_id == str(params.get("id"))).first()
    if tx:
        if tx.state != STATE_CREATED:
            raise _err_cannot_perform()
        if _now_ms() - tx.create_time > TIMEOUT_MS:
            _cancel(db, tx, REASON_TIMEOUT)
            db.commit()
            raise _err_cannot_perform()
        return {"create_time": tx.create_time, "transaction": str(tx.id), "state": tx.state}

    invoice = _find_invoice(db, params, lock=True)
    _check_invoice(invoice, params.get("amount"))
    busy = db.query(models.PaymeTransaction).filter(
        models.PaymeTransaction.invoice_id == invoice.id,
        models.PaymeTransaction.state == STATE_CREATED).first()
    if busy:
        raise PaymeError(-31050, "Buyurtma bo'yicha boshqa to'lov kutilmoqda",
                         "По заказу ожидается другая оплата", "Another payment is pending for this order",
                         account_field())
    tx = models.PaymeTransaction(
        paycom_id=str(params["id"]), invoice_id=invoice.id, amount=params["amount"],
        state=STATE_CREATED, paycom_time=int(params.get("time") or 0), create_time=_now_ms(),
    )
    db.add(tx)
    db.commit()
    return {"create_time": tx.create_time, "transaction": str(tx.id), "state": tx.state}


def perform_transaction(db: Session, params: dict) -> dict:
    tx = _get_tx(db, params, lock=True)
    if tx.state == STATE_CREATED:
        if _now_ms() - tx.create_time > TIMEOUT_MS:
            _cancel(db, tx, REASON_TIMEOUT)
            db.commit()
            raise _err_cannot_perform()
        invoice = tx.invoice
        today = tz.today()
        payment = models.Payment(
            student_id=invoice.student_id, group_id=invoice.group_id, amount=invoice.amount,
            month=today.month, year=today.year, paid_at=datetime.utcnow(),
            notes=f"Payme orqali onlayn to'lov (invoys #{invoice.id})",
        )
        db.add(payment)
        db.flush()
        tx.payment_id = payment.id
        tx.state = STATE_PERFORMED
        tx.perform_time = _now_ms()
        invoice.status = "paid"
        amount = int(Decimal(str(invoice.amount)))
        notify_parents_of_student(
            db, student_id=invoice.student_id, ntype="payment",
            title="To'lov qabul qilindi",
            body=f"{amount:,} so'm to'lov Payme orqali qabul qilindi".replace(",", " "),
        )
        db.commit()
    elif tx.state != STATE_PERFORMED:
        raise _err_cannot_perform()
    return {"transaction": str(tx.id), "perform_time": tx.perform_time, "state": tx.state}


def cancel_transaction(db: Session, params: dict) -> dict:
    tx = _get_tx(db, params, lock=True)
    if tx.state in (STATE_CREATED, STATE_PERFORMED):
        _cancel(db, tx, params.get("reason"))
        db.commit()
    return {"transaction": str(tx.id), "cancel_time": tx.cancel_time, "state": tx.state}


def check_transaction(db: Session, params: dict) -> dict:
    tx = _get_tx(db, params)
    return {
        "create_time": tx.create_time, "perform_time": tx.perform_time, "cancel_time": tx.cancel_time,
        "transaction": str(tx.id), "state": tx.state, "reason": tx.reason,
    }


def get_statement(db: Session, params: dict) -> dict:
    txs = (
        db.query(models.PaymeTransaction)
        .filter(models.PaymeTransaction.paycom_time >= int(params.get("from") or 0),
                models.PaymeTransaction.paycom_time <= int(params.get("to") or 0))
        .order_by(models.PaymeTransaction.paycom_time)
        .all()
    )
    return {"transactions": [
        {
            "id": tx.paycom_id, "time": tx.paycom_time, "amount": tx.amount,
            "account": {account_field(): str(tx.invoice_id)},
            "create_time": tx.create_time, "perform_time": tx.perform_time, "cancel_time": tx.cancel_time,
            "transaction": str(tx.id), "state": tx.state, "reason": tx.reason,
        }
        for tx in txs
    ]}


METHODS = {
    "CheckPerformTransaction": check_perform_transaction,
    "CreateTransaction": create_transaction,
    "PerformTransaction": perform_transaction,
    "CancelTransaction": cancel_transaction,
    "CheckTransaction": check_transaction,
    "GetStatement": get_statement,
}


@router.post("/payme")
async def payme_endpoint(request: Request, db: Session = Depends(get_db)):
    # Payme protokoli: javob har doim HTTP 200, xato JSON-RPC "error" ichida.
    try:
        body = await request.json()
    except ValueError:
        body = None
    req_id = body.get("id") if isinstance(body, dict) else None

    def error(e: PaymeError) -> dict:
        err = {"code": e.code, "message": e.message}
        if e.data:
            err["data"] = e.data
        return {"jsonrpc": "2.0", "id": req_id, "error": err}

    if not _authorized(request):
        return error(PaymeError(-32504, "Ruxsat yo'q", "Недостаточно привилегий", "Insufficient privileges"))
    if not isinstance(body, dict) or not isinstance(body.get("params"), dict):
        return error(PaymeError(-32700, "JSON xato", "Ошибка парсинга JSON", "Parse error"))
    method = METHODS.get(body.get("method"))
    if not method:
        return error(PaymeError(-32601, "Metod topilmadi", "Метод не найден", "Method not found"))
    try:
        return {"jsonrpc": "2.0", "id": req_id, "result": method(db, body["params"])}
    except PaymeError as e:
        db.rollback()
        return error(e)
