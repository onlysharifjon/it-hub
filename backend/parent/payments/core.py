"""Invoys hayot sikli — provayderdan mustaqil umumiy qism.

Pul CRM moliyaviy registriga (`payments` jadvali) FAQAT provayder tasdiqlagan
paytda (`perform`) yoziladi. Taqsimot siyosati (`allocate`):

  1. Tanlangan guruh bo'yicha, eng eski qarzdan boshlab (a'zolik boshlangan oydan
     joriy Toshkent oyigacha) har oyning qolgan qarzi (`student_month_owed` −
     `student_month_paid`) yopiladi — CRM'dagi qo'lda to'lov kabi har oy uchun
     alohida Payment qatori.
  2. Ortib qolgan summa joriy oyga yoziladi (guruh hali boshlanmagan bo'lsa —
     boshlanish oyiga). CRM kumulyativ hisobida u avtomatik avans bo'ladi.

Refund (`reverse`) — shu invoys yozgan Payment qatorlari o'chiriladi (CRM'da
to'lovni o'chirish bilan bir xil ta'sir).

Takroriy/parallel callback: tranzaksiya (provider, provider_txn_id) unikal,
invoys qatori `SELECT ... FOR UPDATE` bilan qulflanadi va holat o'tishi
(pending → paid) faqat bir marta bajariladi.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ... import models, tz
from ...core_calc import bills_month, student_month_owed, student_month_paid
from ..notifications import notify_parents_of_student
from . import config

PROVIDER_LABEL = {"payme": "Payme", "click": "Click", "uzum": "Uzum"}


def now_ms() -> int:
    return int(time.time() * 1000)


def invoice_expired(inv: models.ParentInvoice) -> bool:
    exp = inv.expires_at or (inv.created_at + timedelta(minutes=config.invoice_ttl_minutes()))
    return datetime.utcnow() > exp


def lock_invoice(db: Session, invoice_id) -> Optional[models.ParentInvoice]:
    try:
        iid = int(str(invoice_id).strip())
    except (TypeError, ValueError):
        return None
    return (
        db.query(models.ParentInvoice)
        .filter(models.ParentInvoice.id == iid)
        .with_for_update()
        .first()
    )


def lock_txn(db: Session, provider: str, provider_txn_id: str) -> Optional[models.PaymentTransaction]:
    return (
        db.query(models.PaymentTransaction)
        .filter(models.PaymentTransaction.provider == provider,
                models.PaymentTransaction.provider_txn_id == str(provider_txn_id))
        .with_for_update()
        .first()
    )


def invoice_amount(inv: models.ParentInvoice) -> int:
    return int(Decimal(str(inv.amount)))


def active_txn(inv: models.ParentInvoice, exclude_id: Optional[str] = None) -> Optional[models.PaymentTransaction]:
    """Invoysning hali yakunlanmagan yoki bajarilgan boshqa tranzaksiyasi."""
    for t in inv.transactions:
        if t.state in ("created", "performed") and t.provider_txn_id != exclude_id:
            return t
    return None


# ── Taqsimot ─────────────────────────────────────────────────────────────────

def _group_months(student: models.Student, group: models.Group, upto: Tuple[int, int]) -> List[Tuple[int, int]]:
    months = set()
    for m in student.group_memberships:
        if m.group_id != group.id:
            continue
        start = (m.joined_at.year, m.joined_at.month) if m.joined_at else None
        if group.start_date:
            gs = (group.start_date.year, group.start_date.month)
            start = gs if start is None else max(start, gs)
        if start is None:
            continue
        end = upto
        if m.left_at:
            end = min(end, (m.left_at.year, m.left_at.month))
        if not group.is_active:
            if group.closed_at is None:
                continue
            end = min(end, (group.closed_at.year, group.closed_at.month))
        y, mo = start
        while (y, mo) <= end:
            if bills_month(m, mo, y):
                months.add((y, mo))
            mo += 1
            if mo > 12:
                y, mo = y + 1, 1
    return sorted(months)


def allocate(db: Session, inv: models.ParentInvoice) -> List[Tuple[int, int, Decimal]]:
    """[(year, month, amount), ...] — invoys summasini oylarga taqsimlaydi."""
    student, group = inv.student, inv.group
    today = tz.today()
    current = (today.year, today.month)
    left = Decimal(str(inv.amount))
    parts: List[Tuple[int, int, Decimal]] = []
    for y, mo in _group_months(student, group, current):
        if left <= 0:
            break
        owed = student_month_owed(db, student.id, group.id, mo, y)
        paid = Decimal(str(student_month_paid(db, student.id, group.id, mo, y)))
        due = owed - paid
        if due <= 0:
            continue
        take = min(due, left)
        parts.append((y, mo, take))
        left -= take
    if left > 0:
        target = current
        if group.start_date and (group.start_date.year, group.start_date.month) > current:
            target = (group.start_date.year, group.start_date.month)
        for i, (y, mo, a) in enumerate(parts):
            if (y, mo) == target:
                parts[i] = (y, mo, a + left)
                break
        else:
            parts.append((target[0], target[1], left))
    return parts


def perform(db: Session, inv: models.ParentInvoice, txn: models.PaymentTransaction) -> None:
    """Provayder tasdiqladi: registrga yozish + bildirishnoma. Chaqiruvchi commit qiladi.
    Invoys allaqachon `paid` bo'lsa hech narsa qilmaydi (idempotent)."""
    if txn.state == "performed":
        return
    txn.state = "performed"
    txn.perform_time = now_ms()
    if inv.status == "paid":
        return
    label = PROVIDER_LABEL.get(inv.provider, inv.provider)
    paid_at = datetime.utcnow()
    for y, mo, amount in allocate(db, inv):
        db.add(models.Payment(
            student_id=inv.student_id, group_id=inv.group_id, amount=amount,
            month=mo, year=y, paid_at=paid_at, recorded_by_id=None,
            notes=f"{label} (onlayn, #{inv.id})", parent_invoice_id=inv.id,
        ))
    inv.status = "paid"
    inv.paid_at = paid_at
    # Moliya jurnali: provayder tasdiqlagan kirim ("Onlayn to'lovlar" hisobiga)
    from ...finance import service as finance_service
    finance_service.on_online_payment_performed(db, inv, txn)
    amount_txt = f"{invoice_amount(inv):,}".replace(",", " ")
    notify_parents_of_student(
        db, student_id=inv.student_id, ntype="payment",
        title="To'lov qabul qilindi",
        body=f"{inv.student.full_name} uchun {amount_txt} so'm to'lov tasdiqlandi ({label}).",
    )


def cancel(db: Session, inv: models.ParentInvoice, txn: models.PaymentTransaction,
           reason: Optional[int] = None) -> None:
    """Tranzaksiyani bekor qilish. Bajarilgan bo'lsa — refund (Payment qatorlari o'chiriladi)."""
    if txn.state in ("cancelled", "reversed"):
        return
    was_performed = txn.state == "performed"
    txn.state = "reversed" if was_performed else "cancelled"
    txn.cancel_time = now_ms()
    txn.cancel_reason = reason
    inv.cancelled_at = datetime.utcnow()
    if was_performed:
        from ...finance import service as finance_service
        finance_service.on_online_payment_reversed(db, inv, txn)
        db.query(models.Payment).filter(models.Payment.parent_invoice_id == inv.id).delete(
            synchronize_session=False)
        inv.status = "refunded"
        amount_txt = f"{invoice_amount(inv):,}".replace(",", " ")
        notify_parents_of_student(
            db, student_id=inv.student_id, ntype="payment",
            title="To'lov bekor qilindi",
            body=f"{inv.student.full_name} uchun {amount_txt} so'm onlayn to'lov qaytarildi.",
        )
    elif inv.status == "pending":
        inv.status = "cancelled"
