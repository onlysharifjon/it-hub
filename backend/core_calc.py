"""To'lov / qarz hisobining yagona manbai (single source of truth).

Ham CRM (main.py), ham ota-ona API (parent/) shu funksiyalardan foydalanadi —
mantiq ikki joyda takrorlanmasligi uchun.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

ZERO = Decimal("0")


def active_special_discounts(db: Session, student_id: int) -> list:
    """Talabaning aktiv Special chegirmalari."""
    return (
        db.query(models.SpecialDiscount)
        .filter(
            models.SpecialDiscount.student_id == student_id,
            models.SpecialDiscount.is_active == True,
        )
        .all()
    )


def apply_special_discounts(price: Decimal, discounts: list, group_id: int,
                            month: int = None, year: int = None) -> Decimal:
    """Special chegirmalarni narxga qo'llaydi.

    - free_month: month/year mos kelsa oy to'liq bepul (0).
    - monthly:    har oy amount so'm ayiriladi (butun kurs davomida).
    group_id NULL bo'lgan chegirma barcha guruhlarga tegishli.
    """
    if price <= 0 or not discounts:
        return price
    off = ZERO
    for d in discounts:
        if d.group_id and d.group_id != group_id:
            continue
        if d.kind == "free_month":
            if month is not None and year is not None and d.month == month and d.year == year:
                return ZERO
        elif d.kind == "monthly":
            off += Decimal(str(d.amount or 0))
    return max(ZERO, price - off)


def student_month_owed(db: Session, student_id: int, group_id: int,
                       month: int = None, year: int = None) -> Decimal:
    """Bitta guruh uchun oylik to'liq summa: tarif narxi, aks holda guruh narxi.

    Special chegirmalar shu yerda qo'llanadi (yagona manba). month/year
    berilsa free_month chegirmasi ham hisobga olinadi.
    """
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        return ZERO
    member = next((m for m in g.members if m.student_id == student_id), None)
    if member and member.tariff:
        price = Decimal(str(member.tariff.price))
    elif g.course_price and Decimal(str(g.course_price)) > 0:
        price = Decimal(str(g.course_price))
    else:
        price = ZERO
    if price <= 0:
        return ZERO
    price = apply_special_discounts(price, active_special_discounts(db, student_id),
                                    group_id, month, year)
    return price.quantize(Decimal("1")) if price > 0 else ZERO


def student_month_paid(db: Session, student_id: int, group_id: int, month: int, year: int) -> Decimal:
    """Talabaning shu guruh + oy uchun jami to'lovi."""
    total = (
        db.query(func.sum(models.Payment.amount))
        .filter(
            models.Payment.group_id == group_id,
            models.Payment.student_id == student_id,
            models.Payment.month == month,
            models.Payment.year == year,
        )
        .scalar()
    )
    return total or ZERO


def payment_status(total_owed: Decimal, total_paid: Decimal, advance: Decimal = ZERO) -> str:
    """Holat: none (to'lov talab qilinmaydi) | paid | partial | debtor."""
    covered = total_paid + advance
    if total_owed <= 0:
        return "none"
    if covered >= total_owed:
        return "paid"
    if covered > 0:
        return "partial"
    return "debtor"
