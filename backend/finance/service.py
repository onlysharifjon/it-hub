"""Moliya operatsiyalari — yagona yozish nuqtasi.

Qoidalar (shu modulda majburlanadi):
  * Pul summalari — Decimal (Numeric(14,2)), float ishlatilmaydi.
  * Operatsiya, hisob qoldig'i va talaba/xarajat registri (Payment/Expense)
    BITTA DB tranzaksiyasida yoziladi — commit chaqiruvchida (router), xato
    bo'lsa hammasi birga bekor bo'ladi. Qoldiq `balance = balance + :delta`
    atomar UPDATE bilan o'zgaradi (parallel so'rovlar bir-birini yo'qotmaydi).
  * Qoralama va bekor qilingan operatsiya qoldiq/registrga ta'sir qilmaydi —
    ta'sir faqat `confirm` paytida bir marta qo'llanadi (holat shartli UPDATE
    bilan o'zgaradi: ikki parallel tasdiq ikki marta yozmaydi).
  * Tasdiqlangan operatsiya o'chirilmaydi/summasi o'zgarmaydi — qaytarim va
    tuzatish `origin_id` bilan bog'langan alohida yozuv, sababi majburiy.
  * Ichki o'tkazma `flow=transfer`, `signed_amount=0` — tushum/xarajatga kirmaydi.
  * Valyuta: hisob va operatsiya valyutasi bir xil bo'lishi shart; so'm
    bo'lmagan operatsiya talaba/xarajat registriga faqat kurs (fx_rate) bilan
    yoziladi. Hisobotlar summalarni valyuta bo'yicha alohida qaytaradi.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models, tz
from ..models import UserRole

ZERO = Decimal("0")
CENT = Decimal("0.01")

KINDS = ("income", "expense", "refund", "adjustment", "transfer")
STATUSES = ("draft", "confirmed", "cancelled")
METHODS = ("cash", "card", "bank_transfer", "online", "unknown")
ACCOUNT_KINDS = ("cash", "bank", "card", "online")
CURRENCIES = ("UZS", "USD", "EUR", "RUB")
PREFIX = {"income": "KR", "expense": "XR", "refund": "QT", "adjustment": "TZ", "transfer": "OT"}

MAIN_CASH = "main_cash"
ONLINE = "online"

DEFAULT_CATEGORIES = [
    ("Ish haqi", "salary"), ("Boshqa", "other"), ("Ijara", None), ("Kommunal xizmatlar", None),
    ("Reklama va marketing", None), ("Jihozlar", None), ("Ofis xarajatlari", None), ("Soliq va to'lovlar", None),
]

SETTINGS_DEFAULTS = {
    "due_day": "10",          # oylik to'lov muddati — oyning shu kunigacha
    "upcoming_days": "7",     # "yaqinlashayotgan to'lovlar" oynasi (kun)
}


def q2(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)


def to_uzs(amount: Decimal, currency: str, fx_rate: Optional[Decimal]) -> Decimal:
    if currency == "UZS":
        return q2(amount)
    if not fx_rate or Decimal(str(fx_rate)) <= 0:
        raise HTTPException(400, f"{currency} uchun kurs (1 {currency} = ? so'm) kiritilishi shart")
    return q2(Decimal(str(amount)) * Decimal(str(fx_rate)))


# ── Sozlamalar / tizim yozuvlari ─────────────────────────────────────────────

def get_setting(db: Session, key: str) -> str:
    row = db.query(models.FinanceSetting).filter(models.FinanceSetting.key == key).first()
    return row.value if row else SETTINGS_DEFAULTS[key]


def get_int_setting(db: Session, key: str) -> int:
    try:
        return int(get_setting(db, key))
    except (TypeError, ValueError):
        return int(SETTINGS_DEFAULTS[key])


def ensure_system_rows(db: Session) -> None:
    """Tizim hisoblari va standart kategoriyalar (migratsiya ham yaratadi —
    bu yerda faqat yo'q bo'lsa, masalan test bazasida)."""
    have = {a.code for a in db.query(models.FinanceAccount.code).filter(models.FinanceAccount.code.isnot(None))}
    if MAIN_CASH not in have:
        db.add(models.FinanceAccount(name="Asosiy kassa", kind="cash", currency="UZS", code=MAIN_CASH,
                                     opening_balance=ZERO, balance=ZERO))
    if ONLINE not in have:
        db.add(models.FinanceAccount(name="Onlayn to'lovlar (Payme/Click/Uzum)", kind="online",
                                     currency="UZS", code=ONLINE, opening_balance=ZERO, balance=ZERO))
    if not db.query(models.ExpenseCategory.id).first():
        for name, code in DEFAULT_CATEGORIES:
            db.add(models.ExpenseCategory(name=name, code=code))
    db.flush()


def system_account(db: Session, code: str) -> models.FinanceAccount:
    acc = db.query(models.FinanceAccount).filter(models.FinanceAccount.code == code).first()
    if acc is None:
        ensure_system_rows(db)
        acc = db.query(models.FinanceAccount).filter(models.FinanceAccount.code == code).first()
    return acc


def category_by_code(db: Session, code: str) -> Optional[models.ExpenseCategory]:
    cat = db.query(models.ExpenseCategory).filter(models.ExpenseCategory.code == code).first()
    if cat is None:
        ensure_system_rows(db)
        cat = db.query(models.ExpenseCategory).filter(models.ExpenseCategory.code == code).first()
    return cat


# ── Audit ────────────────────────────────────────────────────────────────────

def snapshot(tx: models.FinanceTransaction) -> dict:
    return {
        "number": tx.number, "kind": tx.kind, "status": tx.status,
        "amount": str(tx.amount), "currency": tx.currency,
        "fx_rate": str(tx.fx_rate) if tx.fx_rate is not None else None,
        "op_date": tx.op_date.isoformat() if tx.op_date else None,
        "method": tx.method, "account_id": tx.account_id, "to_account_id": tx.to_account_id,
        "student_id": tx.student_id, "group_id": tx.group_id,
        "period": f"{tx.period_year}-{tx.period_month:02d}" if tx.period_year and tx.period_month else None,
        "category_id": tx.category_id, "counterparty": tx.counterparty,
        "responsible_id": tx.responsible_id, "origin_id": tx.origin_id,
        "notes": tx.notes,
    }


def audit(db: Session, *, actor: Optional[models.User], entity_type: str, entity_id, action: str,
          old=None, new=None, reason: Optional[str] = None) -> None:
    """Audit yozuvi. Faqat qo'shiladi — o'zgartirish/o'chirish endpoint'i yo'q.
    Provayder callback'i kabi tizim hodisalarida (actor yo'q) yozilmaydi —
    u holda operatsiyaning o'zi (external_ref, external_verified) iz qoldiradi."""
    if actor is None:
        return
    db.add(models.AuditLog(
        entity_type=entity_type, entity_id=entity_id, action=action,
        changed_by_id=actor.id, changed_at=datetime.utcnow(),
        old_value=json.dumps(old, ensure_ascii=False, default=str) if old is not None else None,
        new_value=json.dumps(new, ensure_ascii=False, default=str) if new is not None else None,
        reason=reason,
    ))


# ── Ichki yordamchilar ───────────────────────────────────────────────────────

def _apply_balance(db: Session, account_id: Optional[int], delta: Decimal) -> None:
    if not account_id or not delta:
        return
    db.query(models.FinanceAccount).filter(models.FinanceAccount.id == account_id).update(
        {models.FinanceAccount.balance: models.FinanceAccount.balance + delta},
        synchronize_session=False,
    )


def _op_datetime(op_date: date) -> datetime:
    """Registr (Payment.paid_at / Expense.created_at) uchun naive UTC vaqt:
    bugun bo'lsa — hozir, aks holda o'sha Toshkent kunining 12:00 i."""
    if op_date == tz.today():
        return datetime.utcnow()
    return tz.to_utc(datetime(op_date.year, op_date.month, op_date.day, 12, 0))


def _assign_number(db: Session, tx: models.FinanceTransaction) -> None:
    db.flush()
    tx.number = f"{PREFIX[tx.kind]}-{tx.id:06d}"


def _account(db: Session, account_id: Optional[int], *, required=True) -> Optional[models.FinanceAccount]:
    if not account_id:
        if required:
            raise HTTPException(400, "Kassa yoki hisobni tanlang")
        return None
    acc = db.query(models.FinanceAccount).filter(models.FinanceAccount.id == account_id).first()
    if not acc:
        raise HTTPException(404, "Kassa/hisob topilmadi")
    if not acc.is_active:
        raise HTTPException(400, f"\"{acc.name}\" hisobi nofaol")
    return acc


def _find_by_key(db: Session, key: Optional[str], actor: Optional[models.User]):
    if not key:
        return None
    tx = db.query(models.FinanceTransaction).filter(models.FinanceTransaction.idempotency_key == key).first()
    if tx is not None and actor is not None and tx.created_by_id not in (None, actor.id):
        raise HTTPException(409, "Bu so'rov kaliti boshqa operatsiyada ishlatilgan")
    return tx


def find_by_key(db: Session, key: Optional[str]):
    if not key:
        return None
    return db.query(models.FinanceTransaction).filter(models.FinanceTransaction.idempotency_key == key).first()


def _children(db: Session, origin_id: int):
    return db.query(models.FinanceTransaction).filter(
        models.FinanceTransaction.origin_id == origin_id,
        models.FinanceTransaction.status == "confirmed",
    ).all()


def net_amount(db: Session, origin: models.FinanceTransaction) -> Decimal:
    """Asl kirim/xarajatning tuzatish va qaytarimlardan keyingi sof summasi
    (asl valyutada). Kirim uchun bu — qaytarilishi mumkin bo'lgan qoldiq."""
    total = Decimal(str(origin.amount))
    for ch in _children(db, origin.id):
        if ch.kind == "adjustment":
            total += Decimal(str(ch.amount))
        elif ch.kind == "refund":
            total -= Decimal(str(ch.amount))
    return total


def _flow_and_sign(kind: str, amount: Decimal, origin: Optional[models.FinanceTransaction]):
    if kind == "income":
        return "income", amount
    if kind == "expense":
        return "expense", -amount
    if kind == "refund":
        return "refund", -amount
    if kind == "transfer":
        return "transfer", ZERO
    # adjustment — asl operatsiya oqimida; summa ishorali (+ ko'paytiradi)
    if origin.flow == "income":
        return "income", amount
    return "expense", -amount


def _notify_payment(db: Session, student_id: int, amount_uzs: Decimal) -> None:
    from ..parent.notifications import notify_parents_of_student
    notify_parents_of_student(
        db, student_id=student_id, ntype="payment", title="To'lov qabul qilindi",
        body=f"{int(amount_uzs):,} so'm to'lov qabul qilindi".replace(",", " "),
    )


def _apply_effects(db: Session, tx: models.FinanceTransaction, actor: Optional[models.User]) -> None:
    """Tasdiqlangan operatsiyaning qoldiq va registrga ta'siri (bir marta)."""
    if tx.kind == "transfer":
        _apply_balance(db, tx.account_id, -Decimal(str(tx.amount)))
        _apply_balance(db, tx.to_account_id, Decimal(str(tx.amount)))
        return
    _apply_balance(db, tx.account_id, Decimal(str(tx.signed_amount)))

    origin = tx.origin
    when = _op_datetime(tx.op_date)
    if tx.flow in ("income", "refund") and tx.student_id:
        ledger = Decimal(str(tx.amount_uzs))
        if tx.kind == "refund":
            ledger = -ledger
        label = {"income": None, "refund": "Qaytarim", "adjustment": "Tuzatish"}[tx.kind]
        note = tx.notes if tx.kind == "income" else f"{label} {tx.number} ({origin.number}): {tx.reason}"
        p = models.Payment(
            student_id=tx.student_id, group_id=tx.group_id, amount=ledger,
            month=tx.period_month, year=tx.period_year, paid_at=when, notes=note,
            recorded_by_id=actor.id if actor else tx.created_by_id,
        )
        db.add(p)
        db.flush()
        tx.payment_id = p.id
        if tx.kind == "income":
            _notify_payment(db, tx.student_id, ledger)
    elif tx.flow == "expense":
        cat = tx.category or (origin.category if origin else None)
        name_bits = [cat.name if cat else "Xarajat"]
        if tx.counterparty:
            name_bits.append(tx.counterparty)
        name = " — ".join(name_bits)
        if tx.kind == "adjustment":
            name = f"Tuzatish {tx.number} ({origin.number}): {tx.reason}"
        local = tz.to_local(when)
        legacy_cat = "salary" if cat is not None and cat.code == "salary" else "other"
        e = models.Expense(
            name=name[:300], amount=Decimal(str(tx.amount_uzs)), month=local.month, year=local.year,
            category=legacy_cat, staff_id=(tx.staff_id or (origin.staff_id if origin else None)) if legacy_cat == "salary" else None,
            created_at=when,
        )
        db.add(e)
        db.flush()
        tx.expense_id = e.id


def _new_tx(db: Session, actor: Optional[models.User], **fields) -> models.FinanceTransaction:
    origin = fields.pop("origin", None)
    amount = q2(fields["amount"])
    flow, signed = _flow_and_sign(fields["kind"], amount, origin)
    tx = models.FinanceTransaction(
        **fields, origin_id=origin.id if origin else None,
        flow=flow, signed_amount=signed, status="draft",
        created_by_id=actor.id if actor else None, created_at=datetime.utcnow(),
    )
    tx.amount = amount
    if origin is not None:
        tx.origin = origin
    db.add(tx)
    _assign_number(db, tx)
    return tx


def _mark_confirmed(db: Session, tx: models.FinanceTransaction, actor: Optional[models.User]) -> None:
    tx.status = "confirmed"
    tx.confirmed_by_id = actor.id if actor else None
    tx.confirmed_at = datetime.utcnow()


# ── Ommaviy amallar ──────────────────────────────────────────────────────────

def create_income(db: Session, actor: models.User, data: dict, *, confirm: bool):
    """Mijoz to'lovi. Qaytaradi: (tx, created: bool)."""
    existing = _find_by_key(db, data.get("idempotency_key"), actor)
    if existing:
        return existing, False
    student = db.query(models.Student).filter(models.Student.id == data["student_id"]).first()
    if not student:
        raise HTTPException(404, "Talaba topilmadi")
    member = (
        db.query(models.GroupStudent)
        .filter(models.GroupStudent.student_id == student.id, models.GroupStudent.group_id == data["group_id"])
        .first()
    )
    if not member:
        raise HTTPException(400, "Talaba tanlangan guruhga (shartnomaga) biriktirilmagan")
    acc = _account(db, data.get("account_id"))
    currency = data.get("currency") or acc.currency
    if currency != acc.currency:
        raise HTTPException(400, f"Hisob valyutasi {acc.currency}, to'lov valyutasi {currency} — mos emas")
    amount = q2(data["amount"])
    amount_uzs = to_uzs(amount, currency, data.get("fx_rate"))
    tx = _new_tx(
        db, actor, kind="income", amount=amount, currency=currency,
        fx_rate=data.get("fx_rate") if currency != "UZS" else None, amount_uzs=amount_uzs,
        op_date=data.get("op_date") or tz.today(), method=data["method"], account_id=acc.id,
        student_id=student.id, group_id=data["group_id"],
        period_month=data["period_month"], period_year=data["period_year"],
        external_ref=data.get("external_ref"), notes=data.get("notes"),
        document_path=data.get("document_path"), responsible_id=data.get("responsible_id"),
        idempotency_key=data.get("idempotency_key"),
    )
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="create", new=snapshot(tx))
    if confirm:
        confirm_tx(db, tx, actor)
    return tx, True


def create_expense(db: Session, actor: models.User, data: dict, *, confirm: bool):
    existing = _find_by_key(db, data.get("idempotency_key"), actor)
    if existing:
        return existing, False
    cat = db.query(models.ExpenseCategory).filter(models.ExpenseCategory.id == data["category_id"]).first()
    if not cat or not cat.is_active:
        raise HTTPException(400, "Xarajat kategoriyasi topilmadi yoki nofaol")
    if cat.code == "salary" and not data.get("staff_id"):
        raise HTTPException(400, "\"Ish haqi\" xarajati uchun xodimni tanlang")
    if data.get("staff_id") and not db.query(models.User.id).filter(models.User.id == data["staff_id"]).first():
        raise HTTPException(404, "Xodim topilmadi")
    acc = _account(db, data.get("account_id"))
    currency = data.get("currency") or acc.currency
    if currency != acc.currency:
        raise HTTPException(400, f"Hisob valyutasi {acc.currency}, xarajat valyutasi {currency} — mos emas")
    amount = q2(data["amount"])
    tx = _new_tx(
        db, actor, kind="expense", amount=amount, currency=currency,
        fx_rate=data.get("fx_rate") if currency != "UZS" else None,
        amount_uzs=to_uzs(amount, currency, data.get("fx_rate")),
        op_date=data.get("op_date") or tz.today(), method=data.get("method") or "cash", account_id=acc.id,
        category_id=cat.id, counterparty=data.get("counterparty"),
        responsible_id=data.get("responsible_id"), staff_id=data.get("staff_id") if cat.code == "salary" else None,
        notes=data.get("notes"), document_path=data.get("document_path"),
        idempotency_key=data.get("idempotency_key"),
    )
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="create", new=snapshot(tx))
    if confirm:
        confirm_tx(db, tx, actor)
    return tx, True


def confirm_tx(db: Session, tx: models.FinanceTransaction, actor: Optional[models.User]) -> models.FinanceTransaction:
    """Qoralamani tasdiqlash — qoldiq va registrga ta'sir shu yerda (bir marta).
    Holat shartli UPDATE bilan o'zgaradi: parallel ikkinchi tasdiq 0 qator
    yangilaydi va hech narsa yozmaydi."""
    if tx.status == "confirmed":
        return tx
    if tx.status != "draft":
        raise HTTPException(409, "Bekor qilingan operatsiyani tasdiqlab bo'lmaydi")
    if (tx.kind == "expense" and actor is not None and actor.role != UserRole.admin.value
            and tx.created_by_id == actor.id):
        raise HTTPException(403, "O'zingiz kiritgan xarajatni o'zingiz tasdiqlay olmaysiz — boshqa vakolatli xodim yoki admin tasdiqlaydi")
    if tx.account_id:
        acc = db.query(models.FinanceAccount).filter(models.FinanceAccount.id == tx.account_id).first()
        if acc and not acc.is_active:
            raise HTTPException(400, f"\"{acc.name}\" hisobi nofaol — tasdiqlab bo'lmaydi")
    updated = (
        db.query(models.FinanceTransaction)
        .filter(models.FinanceTransaction.id == tx.id, models.FinanceTransaction.status == "draft")
        .update({models.FinanceTransaction.status: "confirmed"}, synchronize_session=False)
    )
    if not updated:
        db.refresh(tx)
        return tx
    _mark_confirmed(db, tx, actor)
    _apply_effects(db, tx, actor)
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="confirm",
          old={"status": "draft"}, new={"status": "confirmed", "number": tx.number})
    return tx


def cancel_tx(db: Session, tx: models.FinanceTransaction, actor: models.User, reason: str) -> models.FinanceTransaction:
    if tx.status == "cancelled":
        return tx
    if tx.status == "confirmed":
        raise HTTPException(409, "Tasdiqlangan operatsiyani bekor qilib bo'lmaydi — qaytarim yoki tuzatish yarating")
    updated = (
        db.query(models.FinanceTransaction)
        .filter(models.FinanceTransaction.id == tx.id, models.FinanceTransaction.status == "draft")
        .update({models.FinanceTransaction.status: "cancelled"}, synchronize_session=False)
    )
    if not updated:
        db.refresh(tx)
        return tx
    tx.status = "cancelled"
    tx.cancelled_by_id = actor.id
    tx.cancelled_at = datetime.utcnow()
    tx.reason = reason
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="cancel",
          old={"status": "draft"}, new={"status": "cancelled"}, reason=reason)
    return tx


def _lock_origin(db: Session, origin_id: int) -> models.FinanceTransaction:
    origin = (
        db.query(models.FinanceTransaction)
        .filter(models.FinanceTransaction.id == origin_id)
        .with_for_update()
        .first()
    )
    if not origin:
        raise HTTPException(404, "Asl operatsiya topilmadi")
    if origin.status != "confirmed":
        raise HTTPException(409, "Faqat tasdiqlangan operatsiyaga qaytarim/tuzatish qilinadi")
    return origin


def create_refund(db: Session, actor: models.User, origin_id: int, data: dict):
    existing = _find_by_key(db, data.get("idempotency_key"), actor)
    if existing:
        return existing, False
    origin = _lock_origin(db, origin_id)
    if origin.kind != "income":
        raise HTTPException(400, "Qaytarim faqat mijoz to'lovi (kirim) uchun")
    amount = q2(data["amount"])
    refundable = net_amount(db, origin)
    if amount > refundable:
        raise HTTPException(400, f"Qaytarim qaytarilishi mumkin bo'lgan qoldiqdan oshmasligi kerak: "
                                 f"{refundable:,.2f} {origin.currency}".replace(",", " "))
    acc = _account(db, data.get("account_id") or origin.account_id)
    if acc.currency != origin.currency:
        raise HTTPException(400, f"Qaytarim hisobi valyutasi {acc.currency}, to'lov valyutasi {origin.currency}")
    tx = _new_tx(
        db, actor, origin=origin, kind="refund", amount=amount, currency=origin.currency,
        fx_rate=origin.fx_rate, amount_uzs=to_uzs(amount, origin.currency, origin.fx_rate),
        op_date=data.get("op_date") or tz.today(), method=data.get("method") or origin.method,
        account_id=acc.id, student_id=origin.student_id, group_id=origin.group_id,
        period_month=origin.period_month, period_year=origin.period_year,
        reason=data["reason"], notes=data.get("notes"), document_path=data.get("document_path"),
        idempotency_key=data.get("idempotency_key"),
    )
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="refund",
          old={"origin": origin.number, "refundable": str(refundable)}, new=snapshot(tx), reason=data["reason"])
    confirm_tx(db, tx, actor)
    return tx, True


def create_adjustment(db: Session, actor: models.User, origin_id: int, data: dict):
    existing = _find_by_key(db, data.get("idempotency_key"), actor)
    if existing:
        return existing, False
    origin = _lock_origin(db, origin_id)
    if origin.kind not in ("income", "expense"):
        raise HTTPException(400, "Tuzatish faqat kirim yoki xarajat operatsiyasiga qilinadi")
    delta = q2(data["amount"])
    if delta == 0:
        raise HTTPException(400, "Tuzatish summasi 0 bo'lmasligi kerak")
    before = net_amount(db, origin)
    if before + delta < 0:
        raise HTTPException(400, f"Tuzatishdan keyin summa manfiy bo'lib qoladi (hozirgi sof summa: {before:,.2f})".replace(",", " "))
    acc = _account(db, data.get("account_id") or origin.account_id)
    if acc.currency != origin.currency:
        raise HTTPException(400, f"Hisob valyutasi {acc.currency}, asl operatsiya valyutasi {origin.currency}")
    tx = _new_tx(
        db, actor, origin=origin, kind="adjustment", amount=delta, currency=origin.currency,
        fx_rate=origin.fx_rate, amount_uzs=to_uzs(delta, origin.currency, origin.fx_rate),
        op_date=data.get("op_date") or tz.today(), method=origin.method, account_id=acc.id,
        student_id=origin.student_id, group_id=origin.group_id,
        period_month=origin.period_month, period_year=origin.period_year,
        category_id=origin.category_id, counterparty=origin.counterparty, staff_id=origin.staff_id,
        reason=data["reason"], notes=data.get("notes"), idempotency_key=data.get("idempotency_key"),
    )
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="adjust",
          old={"origin": origin.number, "net_before": str(before)},
          new={**snapshot(tx), "net_after": str(before + delta)}, reason=data["reason"])
    confirm_tx(db, tx, actor)
    return tx, True


def create_transfer(db: Session, actor: models.User, data: dict):
    existing = _find_by_key(db, data.get("idempotency_key"), actor)
    if existing:
        return existing, False
    src = _account(db, data["account_id"])
    dst = _account(db, data["to_account_id"])
    if src.id == dst.id:
        raise HTTPException(400, "Bir hisobning o'ziga o'tkazib bo'lmaydi")
    if src.currency != dst.currency:
        raise HTTPException(400, "Turli valyutadagi hisoblar orasida o'tkazma qilinmaydi (konvertatsiya kursi qoidasi yo'q)")
    amount = q2(data["amount"])
    tx = _new_tx(
        db, actor, kind="transfer", amount=amount, currency=src.currency, amount_uzs=None,
        op_date=data.get("op_date") or tz.today(), method=None,
        account_id=src.id, to_account_id=dst.id, notes=data.get("notes"),
        idempotency_key=data.get("idempotency_key"),
    )
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="transfer", new=snapshot(tx))
    confirm_tx(db, tx, actor)
    return tx, True


# ── Eski (mavjud) oqimlar bilan integratsiya ─────────────────────────────────
#
# To'lovlar/Xarajatlar sahifalari va Payme/Click/Uzum callback'lari avvalgidek
# Payment/Expense qatorini yozadi. Quyidagi ilgaklar shu qatorni jurnalga
# tasdiqlangan operatsiya sifatida aks ettiradi (kassa qoldig'i ham yangilanadi),
# admin eski sahifada summani o'zgartirsa yoki o'chirsa — jurnalda asl yozuv
# o'zgarmaydi, unga bog'langan tuzatish yoziladi.

def tx_for_payment(db: Session, payment_id: int) -> Optional[models.FinanceTransaction]:
    return db.query(models.FinanceTransaction).filter(models.FinanceTransaction.payment_id == payment_id).first()


def tx_for_expense(db: Session, expense_id: int) -> Optional[models.FinanceTransaction]:
    return db.query(models.FinanceTransaction).filter(models.FinanceTransaction.expense_id == expense_id).first()


def _mirror(db: Session, actor, **fields) -> models.FinanceTransaction:
    tx = _new_tx(db, actor, **fields)
    _mark_confirmed(db, tx, actor)
    _apply_balance(db, tx.account_id, Decimal(str(tx.signed_amount)))
    audit(db, actor=actor, entity_type="finance_tx", entity_id=tx.id, action="create", new=snapshot(tx))
    return tx


def _default_account_for(db: Session, method: str) -> models.FinanceAccount:
    """Hisob tanlanmagan bo'lsa: naqd — "Asosiy kassa"; karta — birinchi faol
    karta (yo'q bo'lsa bank) hisobi; bank o'tkazmasi — birinchi faol bank hisobi.
    Mos hisob ochilmagan bo'lsa — "Asosiy kassa"."""
    kinds = {"card": ("card", "bank"), "bank_transfer": ("bank",)}.get(method, ())
    for kind in kinds:
        acc = (db.query(models.FinanceAccount)
               .filter(models.FinanceAccount.kind == kind, models.FinanceAccount.is_active == True,  # noqa: E712
                       models.FinanceAccount.currency == "UZS")
               .order_by(models.FinanceAccount.id).first())
        if acc:
            return acc
    return system_account(db, MAIN_CASH)


def on_legacy_payment_created(db: Session, p: models.Payment, actor: models.User,
                              method: Optional[str] = None, account_id: Optional[int] = None) -> models.FinanceTransaction:
    acc = _account(db, account_id) if account_id else _default_account_for(db, method or "cash")
    if acc.currency != "UZS":
        raise HTTPException(400, "To'lovlar sahifasidan faqat so'mdagi hisobga to'lov qabul qilinadi")
    amount = q2(p.amount)
    return _mirror(
        db, actor, kind="income", amount=amount, currency="UZS", amount_uzs=amount,
        op_date=tz.to_local(p.paid_at).date(), method=method or "cash", account_id=acc.id,
        student_id=p.student_id, group_id=p.group_id, period_month=p.month, period_year=p.year,
        payment_id=p.id, notes=p.notes,
    )


def _guard_legacy(db: Session, tx: Optional[models.FinanceTransaction], what: str) -> None:
    if tx is None:
        return
    if tx.kind != "income" and tx.kind != "expense":
        raise HTTPException(409, f"Bu {what} qaytarim/tuzatish yozuvi — uni Moliya → Operatsiyalar bo'limidan boshqaring")
    if tx.currency != "UZS":
        raise HTTPException(409, f"Valyutadagi {what}ni Moliya bo'limidan tuzating")
    # Eski sahifaning o'zi yozgan tuzatishlar (registr qatorisiz) to'sqinlik qilmaydi —
    # Moliya bo'limidan qilingan qaytarim/tuzatish (o'z Payment/Expense qatori bor) esa to'sadi.
    if any(ch.kind == "refund" or ch.payment_id or ch.expense_id for ch in _children(db, tx.id)):
        raise HTTPException(409, f"Bu {what}ga qaytarim/tuzatish bog'langan — Moliya bo'limidan tuzating")


def guard_legacy_payment(db: Session, p: models.Payment) -> Optional[models.FinanceTransaction]:
    tx = tx_for_payment(db, p.id)
    _guard_legacy(db, tx, "to'lov")
    return tx


def guard_legacy_expense(db: Session, e: models.Expense) -> Optional[models.FinanceTransaction]:
    tx = tx_for_expense(db, e.id)
    _guard_legacy(db, tx, "xarajat")
    return tx


def legacy_correction(db: Session, tx: Optional[models.FinanceTransaction], delta: Decimal,
                      actor: models.User, reason: str, *, detach: bool = False) -> None:
    """Eski sahifada summa o'zgardi/qator o'chirildi — registr allaqachon
    o'zgargan, jurnalga faqat bog'langan tuzatish yoziladi (+ qoldiq)."""
    if tx is None:
        return
    delta = q2(delta)
    if detach:
        if tx.payment_id:
            tx.payment_id = None
        if tx.expense_id:
            tx.expense_id = None
    if delta == 0:
        return
    adj = _mirror(
        db, actor, origin=tx, kind="adjustment", amount=delta, currency="UZS", amount_uzs=delta,
        op_date=tz.today(), method=tx.method, account_id=tx.account_id,
        student_id=tx.student_id, group_id=tx.group_id,
        period_month=tx.period_month, period_year=tx.period_year,
        category_id=tx.category_id, counterparty=tx.counterparty, staff_id=tx.staff_id, reason=reason,
    )
    audit(db, actor=actor, entity_type="finance_tx", entity_id=adj.id, action="adjust",
          old={"origin": tx.number}, new={"delta": str(delta)}, reason=reason)


def on_legacy_expense_created(db: Session, e: models.Expense, actor: models.User) -> models.FinanceTransaction:
    acc = system_account(db, MAIN_CASH)
    cat = category_by_code(db, "salary" if e.category == "salary" else "other")
    amount = q2(e.amount)
    staff = db.query(models.User).filter(models.User.id == e.staff_id).first() if e.staff_id else None
    return _mirror(
        db, actor, kind="expense", amount=amount, currency="UZS", amount_uzs=amount,
        op_date=tz.to_local(e.created_at or datetime.utcnow()).date(), method="cash", account_id=acc.id,
        category_id=cat.id if cat else None, staff_id=e.staff_id,
        counterparty=(staff.full_name or staff.username) if staff else None,
        expense_id=e.id, notes=e.name,
    )


def on_online_payment_performed(db: Session, inv, txn) -> None:
    """Payme/Click/Uzum `perform` dan keyin: provayder tasdiqlagan Payment
    qatorlari jurnalga "bank tasdiqlagan" kirim sifatida yoziladi."""
    acc = system_account(db, ONLINE)
    db.flush()
    rows = db.query(models.Payment).filter(models.Payment.parent_invoice_id == inv.id).all()
    for p in rows:
        if tx_for_payment(db, p.id):
            continue
        amount = q2(p.amount)
        _mirror(
            db, None, kind="income", amount=amount, currency="UZS", amount_uzs=amount,
            op_date=tz.to_local(p.paid_at).date(), method="online", account_id=acc.id,
            student_id=p.student_id, group_id=p.group_id, period_month=p.month, period_year=p.year,
            payment_id=p.id, parent_invoice_id=inv.id, notes=p.notes,
            external_ref=f"{inv.provider}:{txn.provider_txn_id}", external_verified=True,
        )


def on_online_payment_reversed(db: Session, inv, txn) -> None:
    """Provayder bajarilgan to'lovni bekor qildi (integratsiya Payment
    qatorlarini o'chiradi) — jurnalda har bir kirimga qaytarim yoziladi."""
    origins = db.query(models.FinanceTransaction).filter(
        models.FinanceTransaction.parent_invoice_id == inv.id,
        models.FinanceTransaction.kind == "income",
        models.FinanceTransaction.status == "confirmed",
    ).all()
    for origin in origins:
        origin.payment_id = None
        left = net_amount(db, origin)
        if left <= 0:
            continue
        _mirror(
            db, None, origin=origin, kind="refund", amount=left, currency=origin.currency, amount_uzs=left,
            op_date=tz.today(), method="online", account_id=origin.account_id,
            student_id=origin.student_id, group_id=origin.group_id,
            period_month=origin.period_month, period_year=origin.period_year,
            parent_invoice_id=inv.id, external_ref=f"{inv.provider}:{txn.provider_txn_id}",
            external_verified=True, reason=f"Provayder to'lovni bekor qildi (kod: {txn.cancel_reason})",
        )
