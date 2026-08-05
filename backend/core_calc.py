"""To'lov / qarz hisobining yagona manbai (single source of truth).

Ham CRM (main.py), ham ota-ona API (parent/) shu funksiyalardan foydalanadi —
mantiq ikki joyda takrorlanmasligi uchun.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract, func
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


def _lesson_dates_in_month(db: Session, group_id: int, student_id: int, month: int, year: int) -> list:
    """Shu guruh/talaba uchun berilgan oyda Attendance'da qayd etilgan dars sanalari."""
    rows = (
        db.query(models.Attendance.lesson_date)
        .filter(
            models.Attendance.group_id == group_id,
            models.Attendance.student_id == student_id,
            extract("month", models.Attendance.lesson_date) == month,
            extract("year", models.Attendance.lesson_date) == year,
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


_PARITY_SCHEDULES = {"toq kunlar": 1, "juft kunlar": 0}  # 1=toq (odd), 0=juft (even) kun


def _scheduled_lesson_dates_in_month(group: models.Group, month: int, year: int) -> Optional[list]:
    """Guruh jadvali "Toq kunlar"/"Juft kunlar" bo'lsa, shu oydagi barcha mos
    sanalarni qaytaradi (yo'qlama hali kiritilmagan bo'lsa ham ishlashi uchun).
    Boshqa jadval formatlari uchun None — chaqiruvchi Attendance'ga qaytadi."""
    sched = (group.schedule or "").strip().lower()
    parity = _PARITY_SCHEDULES.get(sched)
    if parity is None:
        return None
    _, days_in_month = calendar.monthrange(year, month)
    return [date(year, month, d) for d in range(1, days_in_month + 1) if d % 2 == parity]


def apply_vacations_to_price(db: Session, student_id: int, group: models.Group,
                             month: int, year: int, price: Decimal, vacations: list) -> Decimal:
    """Ta'til kunlariga to'g'ri kelgan darslarni oylik narxdan chiqarib tashlaydi.

    `vacations` — talabaning oldindan olingan StudentVacation ro'yxati (chaqiruvchi
    tomonidan bitta so'rov bilan olinishi mumkin, ko'p talaba/guruh holatida N+1
    so'rovlardan qochish uchun). Faqat vacations bo'sh bo'lmasa ishlaydi — aks holda
    narx o'zgarishsiz qaytadi (attendance-independent standart xatti-harakat saqlanadi).

    Formula: kurs_narxi/12 * (jami darslar - ta'tilga tushgan darslar). Yo'qlama
    qilingan (kelgan yoki kelmagan) kunlar hisobga kiradi, faqat ta'til kuni chiqib
    ketadi. Dars sanalari, imkon bo'lsa, guruh jadvalidan ("Toq/Juft kunlar")
    hisoblanadi — shunda hali yo'qlama kiritilmagan bo'lsa ham to'g'ri ishlaydi.
    Boshqa formatdagi jadvallar uchun Attendance'da qayd etilgan sanalarga qaytiladi
    (bu holatda alohida so'rov kerak bo'ladi).
    """
    if price <= 0 or month is None or year is None or not vacations or not group:
        return price
    lesson_dates = _scheduled_lesson_dates_in_month(group, month, year)
    if lesson_dates is None:
        lesson_dates = _lesson_dates_in_month(db, group.id, student_id, month, year)
    if not lesson_dates:
        return price
    vacation_lessons = sum(
        1 for d in lesson_dates if any(v.start_date <= d <= v.end_date for v in vacations)
    )
    if vacation_lessons <= 0:
        return price
    total_lessons = len(lesson_dates)
    billable = max(total_lessons - vacation_lessons, 0)
    per_lesson = price / Decimal(12)
    return (per_lesson * billable).quantize(Decimal("1"))


def vacation_adjusted_price(db: Session, student_id: int, group_id: int,
                            month: int, year: int, price: Decimal) -> Decimal:
    """`apply_vacations_to_price`ning qulay o'rami — vacations/group'ni o'zi so'raydi.
    Bitta talaba/guruh uchun hisoblashda ishlatiladi (masalan to'lov tafsiloti
    sahifasi). Ko'p talaba uchun ro'yxatda `apply_vacations_to_price`ni to'g'ridan-to'g'ri,
    oldindan olingan vacations bilan chaqiring — N+1 so'rovlardan qochish uchun."""
    if price <= 0 or month is None or year is None:
        return price
    vacations = (
        db.query(models.StudentVacation)
        .filter(models.StudentVacation.student_id == student_id)
        .all()
    )
    if not vacations:
        return price
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    return apply_vacations_to_price(db, student_id, group, month, year, price, vacations)


def student_month_owed(db: Session, student_id: int, group_id: int,
                       month: int = None, year: int = None) -> Decimal:
    """Bitta guruh uchun oylik to'liq summa: tarif narxi, aks holda guruh narxi.

    Ta'til (agar bor bo'lsa) va special chegirmalar shu yerda qo'llanadi (yagona
    manba). month/year berilsa free_month chegirmasi va ta'til hisobga olinadi.
    """
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        return ZERO
    if g.start_date and g.start_date.date() > date.today():
        return ZERO  # guruh hali boshlanmagan — talaba hali qarzdor emas
    member = next((m for m in g.members if m.student_id == student_id), None)
    if member and member.tariff:
        price = Decimal(str(member.tariff.price))
    elif g.course_price and Decimal(str(g.course_price)) > 0:
        price = Decimal(str(g.course_price))
    else:
        price = ZERO
    if price <= 0:
        return ZERO
    price = vacation_adjusted_price(db, student_id, group_id, month, year, price)
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
