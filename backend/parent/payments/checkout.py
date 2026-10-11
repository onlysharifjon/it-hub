"""POST /parent/children/{id}/pay — invoys yaratish va checkout URL."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ... import models, tz
from ...core_calc import student_cumulative_balance, student_month_owed
from ..errors import api_error
from . import click, config, payme, uzum

_BUILDERS = {"payme": payme.checkout_url, "click": click.checkout_url, "uzum": uzum.checkout_url}
_REUSE_WINDOW = timedelta(minutes=30)


def create_checkout(db: Session, parent: models.Parent, child: models.Student,
                    group_id: int, amount: int, provider: str) -> str:
    membership = next((m for m in child.group_memberships if m.group_id == group_id), None)
    if membership is None or membership.group is None:
        # Begona yoki mavjud bo'lmagan guruh — shu bola bilan bog'lanmagan
        raise api_error("group_not_found", "Guruh topilmadi", 404)
    group = membership.group

    lo, hi = config.min_amount(), config.max_amount()
    if amount < lo or amount > hi:
        raise api_error("invalid_amount", f"Summa {lo} va {hi} so'm oralig'ida bo'lishi kerak", 422,
                        errors={"amount": [f"{lo}–{hi} so'm oralig'ida butun son kiriting."]})

    # Biznes chegarasi: joriy qarz + 3 oylik to'lov (adashib juda katta summa yuborilmasin).
    today = tz.today()
    debt = max(Decimal(0), -student_cumulative_balance(db, child, today.year, today.month))
    monthly = student_month_owed(db, child.id, group.id, today.month, today.year)
    if monthly <= 0:
        monthly = student_month_owed(db, child.id, group.id)
    cap = int(debt + monthly * 3)
    if cap <= 0:
        raise api_error("nothing_to_pay", "Bu guruh bo'yicha to'lanadigan summa yo'q", 422,
                        errors={"group_id": ["Bu guruh uchun to'lov talab qilinmaydi."]})
    if amount > cap:
        raise api_error("invalid_amount", f"Summa {cap} so'mdan oshmasligi kerak", 422,
                        errors={"amount": [f"Eng ko'pi {cap} so'm."]})

    if provider not in config.active_providers(parent):
        raise api_error("payment_provider_unavailable",
                        "Bu to'lov usuli hozircha ishlamayapti. Boshqa usulni tanlang.", 503)

    now = datetime.utcnow()
    # Qayta urinish: so'nggi 30 daqiqada xuddi shu parametrlar bilan yaratilgan, hali
    # provayderga tushmagan invoys bo'lsa — o'sha qaytariladi (takroriy bosishda dublikat yo'q).
    inv = (
        db.query(models.ParentInvoice)
        .filter(models.ParentInvoice.parent_id == parent.id,
                models.ParentInvoice.student_id == child.id,
                models.ParentInvoice.group_id == group.id,
                models.ParentInvoice.provider == provider,
                models.ParentInvoice.amount == amount,
                models.ParentInvoice.status == "pending",
                models.ParentInvoice.created_at >= now - _REUSE_WINDOW)
        .order_by(models.ParentInvoice.id.desc())
        .first()
    )
    if inv is not None and inv.transactions:
        inv = None
    if inv is None:
        inv = models.ParentInvoice(
            parent_id=parent.id, student_id=child.id, group_id=group.id, amount=amount,
            provider=provider, status="pending", created_at=now,
            expires_at=now + timedelta(minutes=config.invoice_ttl_minutes()),
        )
        db.add(inv)
        db.flush()
        inv.checkout_ref = f"{provider}-{inv.id}"
    url = _BUILDERS[provider](inv)
    if not config.checkout_url_allowed(provider, url):
        db.rollback()
        raise api_error("payment_provider_unavailable", "To'lov provayderi noto'g'ri sozlangan", 503)
    db.commit()
    return url
