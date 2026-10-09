"""Qarzdorlik va to'lov jadvali (bo'lib to'lash bosqichlari).

Biznes qoidalari mavjud `core_calc`dan olinadi (yagona manba): har bir
guruh a'zoligi (= shartnoma) oyma-oy hisoblanadi, tarif/guruh narxi, ta'til
va tasdiqlangan Special chegirmalar qo'llanadi. Jami qarz
`core_calc.student_cumulative_balance` bilan aynan bir xil chiqadi — bu modul
faqat uni bosqichlarga (oylarga) ajratadi va muddat qo'shadi.

To'lovlar bosqichlarga muddat tartibida (FIFO) taqsimlanadi — CRM'dagi
"bir oyda ortiqcha to'langan summa boshqa oy qarzini yopadi" qoidasiga mos.
Barcha bosqichlar yopilgandan keyin qolgan pul — avans.

Muddat: har oyning `due_day`-kuni (Moliya sozlamalari, admin belgilaydi).
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from .. import core_calc, models, tz
from .service import get_int_setting

ZERO = Decimal("0")


def due_date_for(year: int, month: int, due_day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(due_day, 1), last))


def _base_price(m: models.GroupStudent, g: models.Group) -> Decimal:
    if m.tariff:
        return Decimal(str(m.tariff.price))
    if g.course_price and Decimal(str(g.course_price)) > 0:
        return Decimal(str(g.course_price))
    return ZERO


def _months(start, end):
    y, mo = start
    while (y, mo) <= end:
        yield y, mo
        mo += 1
        if mo > 12:
            mo, y = 1, y + 1


def student_schedule(db: Session, student: models.Student, *, today: Optional[date] = None,
                     due_day: Optional[int] = None, include_next: bool = True) -> dict:
    """Talabaning to'lov jadvali va qarz xulosasi.

    Qaytaradi: {contracts, installments, totals}. `installments` — o'tgan va
    joriy oylar (+ include_next bo'lsa keyingi oy, "yaqinlashayotgan").
    """
    today = today or tz.today()
    due_day = due_day if due_day is not None else get_int_setting(db, "due_day")
    upto = (today.year, today.month)

    discounts = core_calc.active_special_discounts(db, student.id)
    vacations = db.query(models.StudentVacation).filter(models.StudentVacation.student_id == student.id).all()
    active_ids = core_calc._active_group_ids(db, student.id)
    primary = min(active_ids) if active_ids else None

    items = []
    contracts = []
    for m in student.group_memberships:
        g = m.group
        if not g:
            continue
        base = _base_price(m, g)
        contracts.append({
            "group_id": g.id, "group_name": g.name,
            "tariff": m.tariff.name if m.tariff else None,
            "monthly_price": base,
            "joined_at": m.joined_at.date().isoformat() if m.joined_at else None,
            "left_at": m.left_at.date().isoformat() if m.left_at else None,
            "group_active": bool(g.is_active),
        })
        if not g.is_active and g.closed_at is None:
            continue
        start = None
        if g.start_date:
            start = (g.start_date.year, g.start_date.month)
        if m.joined_at:
            joined = (m.joined_at.year, m.joined_at.month)
            start = joined if start is None else max(start, joined)
        if start is None:
            continue
        end = upto
        if include_next and m.left_at is None and g.is_active:
            end = (upto[0] + 1, 1) if upto[1] == 12 else (upto[0], upto[1] + 1)
        if m.left_at:
            end = min(end, (m.left_at.year, m.left_at.month))
        if not g.is_active:
            end = min(end, (g.closed_at.year, g.closed_at.month))
        for y, mo in _months(start, end):
            if not core_calc.bills_month(m, mo, y):
                continue
            net = core_calc.student_month_owed(db, student.id, g.id, mo, y, group=g, discounts=discounts,
                                               vacations=vacations, active_group_ids=active_ids)
            gross = base
            after_vac = core_calc.apply_vacations_to_price(db, student.id, g, mo, y, base, vacations) if base > 0 else ZERO
            after_vac = after_vac.quantize(Decimal("1")) if after_vac > 0 else ZERO
            items.append({
                "group_id": g.id, "group_name": g.name, "year": y, "month": mo,
                "gross": gross, "vacation": max(ZERO, gross - after_vac),
                "discount": max(ZERO, after_vac - net), "net": net,
                "due_date": due_date_for(y, mo, due_day),
                "future": (y, mo) > upto,
            })

    items.sort(key=lambda i: (i["due_date"], i["group_id"]))

    # Jami qarz manbai — core_calc (eski guruh to'lovlari kabi chekka holatlar ham)
    owed_now = core_calc.student_cumulative_owed(db, student, upto_year=upto[0], upto_month=upto[1],
                                                 discounts=discounts, vacations=vacations)
    paid = core_calc.student_total_paid_all_time(db, student.id)
    advance_in = Decimal(str(student.advance_balance or 0))
    pool = paid + advance_in
    schedule_now = sum((i["net"] for i in items if not i["future"]), ZERO)
    other_owed = owed_now - schedule_now   # eski guruh to'lovlari (core_calc qoidasi) — registrdagi summa

    left = pool - max(ZERO, other_owed)
    for i in items:
        take = min(max(left, ZERO), i["net"])
        i["paid"] = take
        i["remaining"] = i["net"] - take
        left -= take
        overdue = (not i["future"]) and i["remaining"] > 0 and i["due_date"] < today
        i["overdue_days"] = (today - i["due_date"]).days if overdue else 0
        if i["net"] <= 0:
            i["status"] = "free"
        elif i["remaining"] <= 0:
            i["status"] = "paid"
        elif overdue:
            i["status"] = "overdue"
        elif i["future"]:
            i["status"] = "upcoming"
        elif take > 0:
            i["status"] = "partial"
        else:
            i["status"] = "due"

    balance = pool - owed_now
    debt = max(ZERO, -balance)
    overdue_debt = sum((i["remaining"] for i in items if i["status"] == "overdue"), ZERO)
    overdue_debt = min(overdue_debt, debt)
    current = [i for i in items if not i["future"]]
    max_overdue = max((i["overdue_days"] for i in items), default=0)
    next_due = next((i for i in items if i["remaining"] > 0 and i["status"] != "overdue"), None)
    totals = {
        "contract_total": sum((i["gross"] for i in current), ZERO),
        "discounts": sum((i["discount"] + i["vacation"] for i in current), ZERO),
        "net_total": owed_now,
        "paid_total": pool,
        "debt": debt,
        "overdue_debt": overdue_debt,
        "not_due_debt": debt - overdue_debt,
        "advance": max(ZERO, balance),
        "overdue_days": max_overdue,
        "next_due_date": next_due["due_date"] if next_due else None,
        "next_due_amount": next_due["remaining"] if next_due else ZERO,
    }
    return {"contracts": contracts, "installments": items, "totals": totals}


def students_for_debts(db: Session, *, group_id: Optional[int] = None, search: Optional[str] = None):
    q = (
        db.query(models.Student)
        .options(
            joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.group),
            joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.tariff),
        )
        .filter(models.Student.is_demo == False)  # noqa: E712
    )
    if group_id:
        q = q.filter(models.Student.group_memberships.any(models.GroupStudent.group_id == group_id))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((models.Student.full_name.ilike(like)) | (models.Student.phone1.ilike(like)))
    return q.order_by(models.Student.full_name).all()
