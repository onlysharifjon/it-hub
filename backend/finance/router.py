"""Moliya bo'limi API (`/finance/*`).

Har bir endpoint alohida huquqni tekshiradi (permissions.py). Frontend ham
shu huquqlar bo'yicha menyu/tugmalarni yashiradi, lekin asosiy himoya shu yerda.

Filiallar: CRM'da filial modeli yo'q (yagona markaz) — shuning uchun filial
bo'yicha cheklov/filtr qo'llanmaydi.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import core_calc, models, tz, uploads_sign
from ..database import get_db
from ..main import UPLOAD_DIR, require_admin, require_auth
from ..models import UserRole
from . import calc, reports, service
from . import schemas as fs
from .permissions import FINANCE_DEFAULT, PERMISSIONS, effective_permissions, normalize

router = APIRouter(prefix="/finance", tags=["finance"])
FT = models.FinanceTransaction
ZERO = Decimal("0")
FIN_DOCS_DIR = os.path.join(UPLOAD_DIR, "finance_docs")
DOC_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".xlsx", ".xls", ".doc", ".docx"}
MAX_DOC_BYTES = 10 * 1024 * 1024


def need(*perms: str, any_of: bool = False):
    """Huquq tekshiruvi. any_of=True — sanalganlardan kamida bittasi."""
    def dep(user: models.User = Depends(require_auth)) -> models.User:
        eff = set(effective_permissions(user))
        ok = any(p in eff for p in perms) if any_of else all(p in eff for p in perms)
        if not ok:
            raise HTTPException(403, "Bu amal uchun ruxsatingiz yo'q")
        return user
    return Depends(dep)


ANY_FIN = need(*PERMISSIONS.keys(), any_of=True)


def _name(u):
    return (u.full_name or u.username) if u else None


def _ref(obj, label="name"):
    return {"id": obj.id, "name": getattr(obj, label)} if obj else None


def tx_out(tx: models.FinanceTransaction) -> dict:
    return {
        "id": tx.id, "number": tx.number, "kind": tx.kind, "flow": tx.flow, "status": tx.status,
        "amount": tx.amount, "signed_amount": tx.signed_amount, "currency": tx.currency,
        "fx_rate": tx.fx_rate, "amount_uzs": tx.amount_uzs, "op_date": tx.op_date, "method": tx.method,
        "account": _ref(tx.account), "to_account": _ref(tx.to_account),
        "student": {"id": tx.student.id, "name": tx.student.full_name, "phone": tx.student.phone1} if tx.student else None,
        "group": _ref(tx.group),
        "period_month": tx.period_month, "period_year": tx.period_year,
        "payment_id": tx.payment_id, "expense_id": tx.expense_id, "parent_invoice_id": tx.parent_invoice_id,
        "origin": {"id": tx.origin.id, "number": tx.origin.number, "kind": tx.origin.kind} if tx.origin else None,
        "category": _ref(tx.category), "counterparty": tx.counterparty,
        "responsible": {"id": tx.responsible.id, "name": _name(tx.responsible)} if tx.responsible else None,
        "staff": {"id": tx.staff.id, "name": _name(tx.staff)} if tx.staff else None,
        "external_ref": tx.external_ref, "external_verified": tx.external_verified,
        "reason": tx.reason, "notes": tx.notes,
        "document_url": f"/uploads/{uploads_sign.sign(tx.document_path)}" if tx.document_path else None,
        "created_by": _name(tx.created_by), "created_by_id": tx.created_by_id, "created_at": tx.created_at,
        "confirmed_by": _name(tx.confirmed_by), "confirmed_at": tx.confirmed_at,
        "cancelled_by": _name(tx.cancelled_by), "cancelled_at": tx.cancelled_at,
    }


def _load(db: Session, tx_id: int) -> models.FinanceTransaction:
    tx = (
        db.query(FT)
        .options(joinedload(FT.account), joinedload(FT.to_account), joinedload(FT.student), joinedload(FT.group),
                 joinedload(FT.category), joinedload(FT.origin), joinedload(FT.created_by),
                 joinedload(FT.confirmed_by), joinedload(FT.cancelled_by), joinedload(FT.responsible),
                 joinedload(FT.staff))
        .filter(FT.id == tx_id).first()
    )
    if not tx:
        raise HTTPException(404, "Operatsiya topilmadi")
    return tx


def _commit_tx(db: Session, fn, key: Optional[str], response: Response):
    """Yaratish + commit. Takroriy so'rov (bir xil idempotency_key) yangi
    operatsiya yaratmaydi — mavjudini 200 bilan qaytaradi. Parallel ikki
    so'rov unikal indeksga urilsa, ikkinchisi rollback qilinib mavjudi qaytadi."""
    try:
        tx, created = fn()
        db.commit()
    except IntegrityError:
        db.rollback()
        tx = service.find_by_key(db, key)
        if tx is None:
            raise HTTPException(409, "Operatsiyani saqlab bo'lmadi (takroriy yozuv)")
        created = False
    response.status_code = 201 if created else 200
    out = tx_out(_load(db, tx.id))
    out["duplicate"] = not created
    return out


# ── Profil / sozlamalar ──────────────────────────────────────────────────────

@router.get("/me")
def finance_me(db: Session = Depends(get_db), user: models.User = Depends(require_auth)):
    return {
        "role": user.role,
        "permissions": effective_permissions(user),
        "catalog": [{"key": k, "label": v, "default": k in FINANCE_DEFAULT} for k, v in PERMISSIONS.items()],
        "settings": {k: service.get_int_setting(db, k) for k in service.SETTINGS_DEFAULTS},
        "branches_enabled": False,
    }


@router.put("/settings")
def update_settings(payload: fs.SettingsUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    changes = payload.dict(exclude_none=True)
    old = {}
    for k, v in changes.items():
        row = db.query(models.FinanceSetting).filter(models.FinanceSetting.key == k).first()
        old[k] = row.value if row else service.SETTINGS_DEFAULTS[k]
        if row:
            row.value = str(v)
        else:
            db.add(models.FinanceSetting(key=k, value=str(v)))
    service.audit(db, actor=actor, entity_type="finance_setting", entity_id=None, action="update", old=old, new=changes)
    db.commit()
    return {k: service.get_int_setting(db, k) for k in service.SETTINGS_DEFAULTS}


@router.put("/users/{user_id}/permissions")
def set_user_permissions(user_id: int, payload: fs.PermissionsUpdate, db: Session = Depends(get_db),
                         actor: models.User = Depends(require_admin)):
    """Finans xodimining huquqlari — faqat admin. Xodim o'z huquqini o'zgartira olmaydi."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if user.role != UserRole.finance.value:
        raise HTTPException(400, "Moliya huquqlari faqat \"Finans\" rolidagi xodimga beriladi")
    unknown = set(payload.permissions or []) - set(PERMISSIONS)
    if unknown:
        raise HTTPException(400, f"Noma'lum huquq: {', '.join(sorted(unknown))}")
    old = effective_permissions(user)
    user.permissions = None if payload.permissions is None else json.dumps(normalize(payload.permissions))
    service.audit(db, actor=actor, entity_type="user_permissions", entity_id=user.id, action="update",
                  old=old, new=effective_permissions(user))
    db.commit()
    return {"user_id": user.id, "permissions": effective_permissions(user), "is_default": user.permissions is None}


@router.get("/users/{user_id}/permissions")
def get_user_permissions(user_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return {"user_id": user.id, "permissions": effective_permissions(user), "is_default": user.permissions is None}


# ── Ma'lumotnomalar ──────────────────────────────────────────────────────────

def _account_out(db: Session, a: models.FinanceAccount) -> dict:
    return {"id": a.id, "name": a.name, "kind": a.kind, "currency": a.currency, "code": a.code,
            "opening_balance": a.opening_balance, "balance": a.balance, "is_active": a.is_active, "note": a.note}


def computed_balance(db: Session, a: models.FinanceAccount) -> Decimal:
    """Qoldiqni jurnaldan qayta hisoblash (saqlangan `balance` bilan solishtirish uchun)."""
    own = db.query(func.coalesce(func.sum(FT.signed_amount), 0)).filter(
        FT.status == "confirmed", FT.account_id == a.id, FT.kind != "transfer").scalar()
    t_out = db.query(func.coalesce(func.sum(FT.amount), 0)).filter(
        FT.status == "confirmed", FT.kind == "transfer", FT.account_id == a.id).scalar()
    t_in = db.query(func.coalesce(func.sum(FT.amount), 0)).filter(
        FT.status == "confirmed", FT.kind == "transfer", FT.to_account_id == a.id).scalar()
    return Decimal(str(a.opening_balance)) + Decimal(str(own)) - Decimal(str(t_out)) + Decimal(str(t_in))


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), _: models.User = ANY_FIN):
    service.ensure_system_rows(db)
    db.commit()
    out = []
    for a in db.query(models.FinanceAccount).order_by(models.FinanceAccount.is_active.desc(), models.FinanceAccount.id):
        row = _account_out(db, a)
        row["computed_balance"] = computed_balance(db, a)
        row["in_sync"] = row["computed_balance"] == Decimal(str(a.balance))
        out.append(row)
    return out


@router.post("/accounts", status_code=201)
def create_account(payload: fs.AccountCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    a = models.FinanceAccount(name=payload.name.strip(), kind=payload.kind, currency=payload.currency,
                              opening_balance=service.q2(payload.opening_balance),
                              balance=service.q2(payload.opening_balance), note=payload.note)
    db.add(a)
    db.flush()
    service.audit(db, actor=actor, entity_type="finance_account", entity_id=a.id, action="create",
                  new=_account_out(db, a))
    db.commit()
    return _account_out(db, a)


@router.patch("/accounts/{account_id}")
def update_account(account_id: int, payload: fs.AccountUpdate, db: Session = Depends(get_db),
                   actor: models.User = Depends(require_admin)):
    a = db.query(models.FinanceAccount).filter(models.FinanceAccount.id == account_id).first()
    if not a:
        raise HTTPException(404, "Kassa/hisob topilmadi")
    old = _account_out(db, a)
    if payload.name is not None:
        a.name = payload.name.strip()
    if payload.note is not None:
        a.note = payload.note
    if payload.is_active is not None:
        a.is_active = payload.is_active
    if payload.opening_balance is not None:
        if not (payload.reason or "").strip():
            raise HTTPException(400, "Boshlang'ich qoldiqni o'zgartirish sababini yozing")
        delta = service.q2(payload.opening_balance) - Decimal(str(a.opening_balance))
        a.opening_balance = service.q2(payload.opening_balance)
        db.query(models.FinanceAccount).filter(models.FinanceAccount.id == a.id).update(
            {models.FinanceAccount.balance: models.FinanceAccount.balance + delta}, synchronize_session=False)
    service.audit(db, actor=actor, entity_type="finance_account", entity_id=a.id, action="update",
                  old=old, new=payload.dict(exclude_none=True), reason=payload.reason)
    db.commit()
    db.refresh(a)
    return _account_out(db, a)


@router.get("/categories")
def list_categories(db: Session = Depends(get_db), _: models.User = ANY_FIN):
    service.ensure_system_rows(db)
    db.commit()
    return [{"id": c.id, "name": c.name, "code": c.code, "is_active": c.is_active}
            for c in db.query(models.ExpenseCategory).order_by(models.ExpenseCategory.is_active.desc(),
                                                                models.ExpenseCategory.name)]


@router.post("/categories", status_code=201)
def create_category(payload: fs.CategoryCreate, db: Session = Depends(get_db),
                    actor: models.User = need("finance.categories")):
    name = payload.name.strip()
    if db.query(models.ExpenseCategory).filter(func.lower(models.ExpenseCategory.name) == name.lower()).first():
        raise HTTPException(400, "Bunday nomli kategoriya bor")
    c = models.ExpenseCategory(name=name)
    db.add(c)
    db.flush()
    service.audit(db, actor=actor, entity_type="finance_category", entity_id=c.id, action="create", new={"name": name})
    db.commit()
    return {"id": c.id, "name": c.name, "code": c.code, "is_active": c.is_active}


@router.patch("/categories/{category_id}")
def update_category(category_id: int, payload: fs.CategoryUpdate, db: Session = Depends(get_db),
                    actor: models.User = need("finance.categories")):
    c = db.query(models.ExpenseCategory).filter(models.ExpenseCategory.id == category_id).first()
    if not c:
        raise HTTPException(404, "Kategoriya topilmadi")
    old = {"name": c.name, "is_active": c.is_active}
    if payload.name is not None:
        name = payload.name.strip()
        dup = db.query(models.ExpenseCategory).filter(func.lower(models.ExpenseCategory.name) == name.lower(),
                                                      models.ExpenseCategory.id != c.id).first()
        if dup:
            raise HTTPException(400, "Bunday nomli kategoriya bor")
        c.name = name
    if payload.is_active is not None:
        if c.code in ("salary", "other") and payload.is_active is False:
            raise HTTPException(400, "Tizim kategoriyasini nofaol qilib bo'lmaydi")
        c.is_active = payload.is_active
    service.audit(db, actor=actor, entity_type="finance_category", entity_id=c.id, action="update",
                  old=old, new={"name": c.name, "is_active": c.is_active})
    db.commit()
    return {"id": c.id, "name": c.name, "code": c.code, "is_active": c.is_active}


@router.get("/staff")
def staff_options(db: Session = Depends(get_db), _: models.User = ANY_FIN):
    users = db.query(models.User).order_by(models.User.is_active.desc(), models.User.full_name).all()
    return [{"id": u.id, "name": _name(u), "role": u.role, "is_active": u.is_active} for u in users]


@router.get("/groups")
def group_options(db: Session = Depends(get_db), _: models.User = ANY_FIN):
    return [{"id": g.id, "name": g.name, "is_active": g.is_active}
            for g in db.query(models.Group).order_by(models.Group.is_active.desc(), models.Group.name)]


# ── Mijozlar ─────────────────────────────────────────────────────────────────

@router.get("/students")
def search_students(search: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=50),
                    db: Session = Depends(get_db), _: models.User = need("finance.clients", "finance.income", any_of=True)):
    q = db.query(models.Student).options(
        joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.group),
        joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.tariff),
    ).filter(models.Student.is_demo == False)  # noqa: E712
    s = search.strip()
    if s:
        like = f"%{s}%"
        q = q.filter(or_(models.Student.full_name.ilike(like), models.Student.phone1.ilike(like)))
    out = []
    for st in q.order_by(models.Student.is_archived, models.Student.full_name).limit(limit).all():
        out.append({
            "id": st.id, "name": st.full_name, "phone": st.phone1, "is_archived": st.is_archived,
            "contracts": [{
                "group_id": m.group_id, "group_name": m.group.name if m.group else None,
                "tariff": m.tariff.name if m.tariff else None,
                "monthly_price": calc._base_price(m, m.group) if m.group else ZERO,
                "active": m.left_at is None and bool(m.group and m.group.is_active),
            } for m in st.group_memberships],
        })
    return out


@router.get("/expected")
def expected_for_month(student_id: int, group_id: int, month: int = Query(..., ge=1, le=12),
                       year: int = Query(..., ge=2020), db: Session = Depends(get_db),
                       _: models.User = need("finance.clients", "finance.income", any_of=True)):
    """Kirim formasi uchun: shu oy hisoblangan summa, to'langan va qolgani +
    talabaning umumiy qarzi/avansi (ortiqcha to'lov avansga o'tadi)."""
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(404, "Talaba topilmadi")
    expected = core_calc.student_month_owed(db, student_id, group_id, month, year)
    paid = core_calc.student_month_paid(db, student_id, group_id, month, year)
    balance = core_calc.student_cumulative_balance(db, student)
    return {"expected": expected, "paid": paid, "remaining": max(ZERO, expected - paid),
            "debt": max(ZERO, -balance), "advance": max(ZERO, balance)}


@router.get("/students/{student_id}")
def student_finance(student_id: int, db: Session = Depends(get_db),
                    _: models.User = need("finance.clients", "finance.debts", any_of=True)):
    s = (
        db.query(models.Student)
        .options(joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.group),
                 joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.tariff))
        .filter(models.Student.id == student_id).first()
    )
    if not s:
        raise HTTPException(404, "Talaba topilmadi")
    sch = calc.student_schedule(db, s)
    txs = (
        db.query(FT).options(joinedload(FT.account), joinedload(FT.group), joinedload(FT.origin),
                             joinedload(FT.created_by), joinedload(FT.student), joinedload(FT.category),
                             joinedload(FT.to_account), joinedload(FT.confirmed_by), joinedload(FT.cancelled_by),
                             joinedload(FT.responsible), joinedload(FT.staff))
        .filter(FT.student_id == s.id).order_by(FT.op_date.desc(), FT.id.desc()).all()
    )
    discounts = [{"id": d.id, "kind": d.kind, "amount": d.amount, "month": d.month, "year": d.year,
                  "reason": d.reason, "group_id": d.group_id}
                 for d in core_calc.active_special_discounts(db, s.id)]
    return {
        "student": {"id": s.id, "name": s.full_name, "phone": s.phone1, "is_archived": s.is_archived},
        **sch, "discounts": discounts, "transactions": [tx_out(t) for t in txs],
    }


# ── Operatsiyalar ────────────────────────────────────────────────────────────

SORTS = {"date": FT.op_date, "amount": FT.amount, "number": FT.id, "created": FT.created_at}


@router.get("/transactions")
def list_transactions(
    kind: Optional[str] = Query(None, regex="^(income|expense|refund|adjustment|transfer)$"),
    flow: Optional[str] = Query(None, regex="^(income|expense|refund|transfer)$"),
    flows: Optional[str] = Query(None, regex="^(income|expense|refund|transfer)(,(income|expense|refund|transfer))*$"),
    status: Optional[str] = Query(None, regex="^(draft|confirmed|cancelled)$"),
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    method: Optional[str] = None, account_id: Optional[int] = None, category_id: Optional[int] = None,
    responsible_id: Optional[int] = None, student_id: Optional[int] = None, group_id: Optional[int] = None,
    search: Optional[str] = Query(None, max_length=100),
    sort: str = Query("date", regex="^(date|amount|number|created)$"),
    dir: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = need("finance.clients", "finance.income", "finance.expense", "finance.reports",
                             "finance.approve", any_of=True),
):
    eff = set(effective_permissions(user))
    f = dict(date_from=date_from, date_to=date_to, method=method, account_id=account_id, category_id=category_id,
             responsible_id=responsible_id, student_id=student_id, group_id=group_id)
    q = reports.base_query(db, f, statuses=(status,) if status else None)
    # Mijoz to'lovlarini ko'rish huquqi bo'lmasa — faqat xarajatlar
    if not eff & {"finance.clients", "finance.income", "finance.reports", "finance.approve"}:
        q = q.filter(FT.flow == "expense")
    if kind:
        q = q.filter(FT.kind == kind)
    if flow:
        q = q.filter(FT.flow == flow)
    if flows:
        q = q.filter(FT.flow.in_(flows.split(",")))
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.outerjoin(models.Student, models.Student.id == FT.student_id).filter(or_(
            FT.number.ilike(like), FT.counterparty.ilike(like), FT.notes.ilike(like),
            FT.external_ref.ilike(like), models.Student.full_name.ilike(like)))
    total = q.count()
    col = SORTS[sort]
    order = [col.asc() if dir == "asc" else col.desc(), FT.id.desc() if dir == "desc" else FT.id.asc()]
    items = q.order_by(*order).offset((page - 1) * page_size).limit(page_size).all()
    # Sahifadagi summalar valyuta bo'yicha (filtrlangan to'plam bo'yicha jami)
    sums = defaultdict(lambda: ZERO)
    agg = q.with_entities(FT.currency, FT.status, func.sum(FT.signed_amount)).group_by(FT.currency, FT.status)
    by_cur = {}
    for cur, st, s in agg.order_by(None).all():
        if st == "confirmed":
            by_cur[cur] = by_cur.get(cur, ZERO) + Decimal(str(s or 0))
    return {
        "items": [tx_out(t) for t in items],
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "total_pages": max(1, (total + page_size - 1) // page_size)},
        "confirmed_net_by_currency": by_cur,
    }


@router.get("/transactions/{tx_id}")
def get_transaction(tx_id: int, db: Session = Depends(get_db),
                    user: models.User = need("finance.clients", "finance.income", "finance.expense",
                                             "finance.reports", "finance.approve", "finance.audit", any_of=True)):
    tx = _load(db, tx_id)
    eff = set(effective_permissions(user))
    if tx.flow != "expense" and not eff & {"finance.clients", "finance.income", "finance.reports",
                                           "finance.approve", "finance.audit"}:
        raise HTTPException(403, "Bu amal uchun ruxsatingiz yo'q")
    out = tx_out(tx)
    children = db.query(FT).options(joinedload(FT.created_by)).filter(FT.origin_id == tx.id).order_by(FT.id).all()
    out["children"] = [{"id": c.id, "number": c.number, "kind": c.kind, "status": c.status, "amount": c.amount,
                        "op_date": c.op_date, "reason": c.reason, "created_by": _name(c.created_by)} for c in children]
    out["net_amount"] = service.net_amount(db, tx) if tx.status == "confirmed" and tx.kind in ("income", "expense") else None
    logs = (
        db.query(models.AuditLog).options(joinedload(models.AuditLog.changed_by_user))
        .filter(models.AuditLog.entity_type == "finance_tx", models.AuditLog.entity_id == tx.id)
        .order_by(models.AuditLog.changed_at).all()
    )
    out["history"] = [_audit_out(l) for l in logs]
    return out


@router.post("/income")
def create_income(payload: fs.IncomeCreate, response: Response, db: Session = Depends(get_db),
                  actor: models.User = need("finance.income")):
    if payload.confirm and "finance.approve" not in effective_permissions(actor):
        raise HTTPException(403, "Tasdiqlash huquqingiz yo'q — to'lovni qoralama sifatida saqlang")
    data = payload.dict()
    confirm = data.pop("confirm")
    return _commit_tx(db, lambda: service.create_income(db, actor, data, confirm=confirm),
                      payload.idempotency_key, response)


@router.post("/expenses")
def create_expense(payload: fs.ExpenseCreate, response: Response, db: Session = Depends(get_db),
                   actor: models.User = need("finance.expense")):
    if payload.confirm and "finance.approve" not in effective_permissions(actor):
        raise HTTPException(403, "Tasdiqlash huquqingiz yo'q — xarajatni qoralama sifatida saqlang")
    data = payload.dict()
    confirm = data.pop("confirm")
    return _commit_tx(db, lambda: service.create_expense(db, actor, data, confirm=confirm),
                      payload.idempotency_key, response)


@router.post("/transactions/{tx_id}/confirm")
def confirm_transaction(tx_id: int, db: Session = Depends(get_db),
                        actor: models.User = need("finance.approve")):
    tx = _load(db, tx_id)
    service.confirm_tx(db, tx, actor)
    db.commit()
    return tx_out(_load(db, tx_id))


@router.post("/transactions/{tx_id}/cancel")
def cancel_transaction(tx_id: int, payload: fs.ReasonIn, db: Session = Depends(get_db),
                       actor: models.User = Depends(require_auth)):
    tx = _load(db, tx_id)
    eff = set(effective_permissions(actor))
    own_draft = tx.created_by_id == actor.id and eff & {"finance.income", "finance.expense"}
    if "finance.approve" not in eff and not own_draft:
        raise HTTPException(403, "Bu amal uchun ruxsatingiz yo'q")
    service.cancel_tx(db, tx, actor, payload.reason.strip())
    db.commit()
    return tx_out(_load(db, tx_id))


@router.post("/transactions/{tx_id}/refund")
def refund_transaction(tx_id: int, payload: fs.RefundCreate, response: Response, db: Session = Depends(get_db),
                       actor: models.User = need("finance.refund")):
    data = payload.dict()
    data["reason"] = data["reason"].strip()
    return _commit_tx(db, lambda: service.create_refund(db, actor, tx_id, data), payload.idempotency_key, response)


@router.post("/transactions/{tx_id}/adjust")
def adjust_transaction(tx_id: int, payload: fs.AdjustmentCreate, response: Response, db: Session = Depends(get_db),
                       actor: models.User = need("finance.refund")):
    data = payload.dict()
    data["reason"] = data["reason"].strip()
    return _commit_tx(db, lambda: service.create_adjustment(db, actor, tx_id, data), payload.idempotency_key, response)


@router.post("/transfers")
def create_transfer(payload: fs.TransferCreate, response: Response, db: Session = Depends(get_db),
                    actor: models.User = need("finance.transfer")):
    data = payload.dict()
    return _commit_tx(db, lambda: service.create_transfer(db, actor, data), payload.idempotency_key, response)


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db),
                          _: models.User = need("finance.income", "finance.expense", "finance.refund", any_of=True)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in DOC_EXT:
        raise HTTPException(400, "Fayl turi qo'llab-quvvatlanmaydi (PDF, rasm, Excel yoki Word)")
    data = await file.read(MAX_DOC_BYTES + 1)
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(400, "Fayl hajmi 10 MB dan oshmasligi kerak")
    if not data:
        raise HTTPException(400, "Fayl bo'sh")
    os.makedirs(FIN_DOCS_DIR, exist_ok=True)
    rel = f"finance_docs/{uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, rel), "wb") as fh:
        fh.write(data)
    return {"path": rel, "url": f"/uploads/{uploads_sign.sign(rel)}", "name": file.filename}


# ── Dashboard ────────────────────────────────────────────────────────────────

def _sum_by(q):
    out = {}
    for cur, flow, s in q.group_by(FT.currency, FT.flow).all():
        out.setdefault(cur, {"income": ZERO, "refunds": ZERO, "expense": ZERO, "net": ZERO})
        v = Decimal(str(s or 0))
        if flow == "income":
            out[cur]["income"] += v
        elif flow == "refund":
            out[cur]["refunds"] += -v
        elif flow == "expense":
            out[cur]["expense"] += -v
        out[cur]["net"] += v
    return out


@router.get("/dashboard")
def dashboard(date_from: Optional[date] = None, date_to: Optional[date] = None,
              method: Optional[str] = Query(None, regex="^(cash|card|bank_transfer|online|unknown)$"),
              account_id: Optional[int] = None,
              db: Session = Depends(get_db), user: models.User = need("finance.dashboard")):
    d_from, d_to = reports.default_range(date_from, date_to)
    today = tz.today()

    def flows(a, b):
        q = db.query(FT.currency, FT.flow, func.sum(FT.signed_amount)).filter(
            FT.status == "confirmed", FT.flow.in_(("income", "refund", "expense")),
            FT.op_date >= a, FT.op_date <= b)
        if method:
            q = q.filter(FT.method == method)
        if account_id:
            q = q.filter(FT.account_id == account_id)
        return _sum_by(q)

    period = flows(d_from, d_to)
    today_sum = flows(today, today)
    span = (d_to - d_from).days + 1
    prev = flows(d_from - timedelta(days=span), d_from - timedelta(days=1))

    # Grafik: kunlik (≤ 62 kun) yoki oylik
    rep = reports.report_cashflow(db, {"date_from": d_from, "date_to": d_to, "method": method,
                                       "account_id": account_id,
                                       "granularity": "month" if span > 62 else "day"})
    chart = [{"label": str(r["period"]), "currency": r["currency"], "income": r["income"] - r["refunds"],
              "expense": r["expense"], "net": r["net"]} for r in rep["rows"]]

    accounts = []
    balances = {}
    for a in db.query(models.FinanceAccount).filter(models.FinanceAccount.is_active == True).order_by(models.FinanceAccount.id):  # noqa: E712
        accounts.append({"id": a.id, "name": a.name, "kind": a.kind, "currency": a.currency, "balance": a.balance})
        balances[a.currency] = balances.get(a.currency, ZERO) + Decimal(str(a.balance))

    drafts = db.query(FT.kind, func.count(FT.id)).filter(FT.status == "draft").group_by(FT.kind).all()

    # Qarzdorlik (UZS) — mijozlar to'lov jadvali asosida
    debt = overdue = advance = ZERO
    debtors = overdue_cnt = 0
    upcoming = []
    horizon = today + timedelta(days=service.get_int_setting(db, "upcoming_days"))
    due_day = service.get_int_setting(db, "due_day")
    for s in calc.students_for_debts(db):
        sch = calc.student_schedule(db, s, today=today, due_day=due_day)
        t = sch["totals"]
        debt += t["debt"]
        overdue += t["overdue_debt"]
        advance += t["advance"]
        debtors += 1 if t["debt"] > 0 else 0
        overdue_cnt += 1 if t["overdue_debt"] > 0 else 0
        for i in sch["installments"]:
            if i["remaining"] > 0 and i["status"] != "overdue" and today <= i["due_date"] <= horizon:
                upcoming.append({"student_id": s.id, "student": s.full_name, "phone": s.phone1,
                                 "group": i["group_name"], "due_date": i["due_date"], "amount": i["remaining"],
                                 "period": f"{reports.MONTHS[i['month'] - 1]} {i['year']}"})
    upcoming.sort(key=lambda x: (x["due_date"], x["student"]))

    return {
        "date_from": d_from, "date_to": d_to, "today": today,
        "period": period, "previous": prev, "today_totals": today_sum,
        "chart": chart, "chart_granularity": rep["granularity"],
        "accounts": accounts, "balances": balances,
        "debt": {"total": debt, "overdue": overdue, "not_due": debt - overdue, "advance": advance,
                 "debtors": debtors, "overdue_students": overdue_cnt},
        "upcoming": {"items": upcoming[:50], "count": len(upcoming),
                     "total": sum((u["amount"] for u in upcoming), ZERO), "days": (horizon - today).days},
        "drafts": {k: c for k, c in drafts},
    }


# ── Qarzdorlik ───────────────────────────────────────────────────────────────

DEBT_SORT = {"debt", "overdue_debt", "overdue_days", "student", "advance", "paid_total", "next_due_date"}


@router.get("/debts")
def list_debts(search: Optional[str] = Query(None, max_length=100), group_id: Optional[int] = None,
               status: str = Query("debtor", regex="^(all|debtor|overdue|advance)$"),
               sort: str = Query("debt"), dir: str = Query("desc", regex="^(asc|desc)$"),
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
               db: Session = Depends(get_db), _: models.User = need("finance.debts")):
    rep = reports.report_debts(db, {"search": search, "group_id": group_id, "status": status})
    rows = rep["rows"]
    key = sort if sort in DEBT_SORT else "debt"
    rows.sort(key=lambda r: (r[key] is None, r[key] if r[key] is not None else 0) if key != "student"
              else (r["student"] or "").lower(), reverse=(dir == "desc"))
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "totals": rep["totals"].get("UZS", {}),
            "meta": {"total": total, "page": page, "page_size": page_size,
                     "total_pages": max(1, (total + page_size - 1) // page_size)}}


# ── Hisobotlar ───────────────────────────────────────────────────────────────

def _report_filters(date_from, date_to, method, account_id, category_id, responsible_id, group_id,
                    student_id, status, search, granularity):
    return {k: v for k, v in dict(
        date_from=date_from, date_to=date_to, method=method, account_id=account_id, category_id=category_id,
        responsible_id=responsible_id, group_id=group_id, student_id=student_id, status=status,
        search=search, granularity=granularity).items() if v not in (None, "")}


@router.get("/reports")
def report_catalog(_: models.User = need("finance.reports")):
    return [{"key": k, "label": v} for k, v in reports.REPORTS.items()]


@router.get("/reports/{kind}")
def get_report(kind: str, date_from: Optional[date] = None, date_to: Optional[date] = None,
               method: Optional[str] = None, account_id: Optional[int] = None, category_id: Optional[int] = None,
               responsible_id: Optional[int] = None, group_id: Optional[int] = None,
               student_id: Optional[int] = None, status: Optional[str] = None,
               search: Optional[str] = Query(None, max_length=100), granularity: Optional[str] = None,
               limit: int = Query(500, ge=1, le=5000),
               db: Session = Depends(get_db), user: models.User = need("finance.reports")):
    if kind in ("debts", "overdue") and "finance.debts" not in effective_permissions(user):
        raise HTTPException(403, "Qarzdorlik hisobotlari uchun ruxsatingiz yo'q")
    rep = reports.build(db, kind, _report_filters(date_from, date_to, method, account_id, category_id,
                                                  responsible_id, group_id, student_id, status, search, granularity))
    rep["row_count"] = len(rep["rows"])
    rep["truncated"] = len(rep["rows"]) > limit
    rep["rows"] = rep["rows"][:limit]
    return rep


@router.get("/reports/{kind}/export")
def export_report(kind: str, format: str = Query("xlsx", regex="^(xlsx|csv)$"),
                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                  method: Optional[str] = None, account_id: Optional[int] = None, category_id: Optional[int] = None,
                  responsible_id: Optional[int] = None, group_id: Optional[int] = None,
                  student_id: Optional[int] = None, status: Optional[str] = None,
                  search: Optional[str] = Query(None, max_length=100), granularity: Optional[str] = None,
                  db: Session = Depends(get_db), user: models.User = need("finance.reports", "finance.export")):
    if kind in ("debts", "overdue") and "finance.debts" not in effective_permissions(user):
        raise HTTPException(403, "Qarzdorlik hisobotlari uchun ruxsatingiz yo'q")
    f = _report_filters(date_from, date_to, method, account_id, category_id, responsible_id, group_id,
                        student_id, status, search, granularity)
    rep = reports.build(db, kind, f)
    if rep.get("lines"):
        rep = {**rep, "columns": rep["lines_columns"], "rows": rep["lines"]}
    service.audit(db, actor=user, entity_type="finance_export", entity_id=None, action="export",
                  new={"report": kind, "format": format, "filters": f, "rows": len(rep["rows"])})
    db.commit()
    stamp = tz.today().strftime("%Y%m%d")
    if format == "csv":
        body, mime = reports.to_csv(rep), "text/csv; charset=utf-8"
    else:
        body, mime = reports.to_xlsx(rep), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content=body, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="moliya-{kind}-{stamp}.{format}"'})


# ── Operatsiyalar tarixi (audit) ─────────────────────────────────────────────

AUDIT_ACTIONS = {"create": "Yaratildi", "confirm": "Tasdiqlandi", "cancel": "Bekor qilindi", "refund": "Qaytarim",
                 "adjust": "Tuzatish", "transfer": "O'tkazma", "update": "O'zgartirildi", "export": "Eksport",
                 "delete": "O'chirildi"}
AUDIT_ENTITIES = ("finance_tx", "finance_account", "finance_category", "finance_setting", "finance_export",
                  "user_permissions", "payment", "expense")


def _audit_out(l: models.AuditLog) -> dict:
    def load(v):
        try:
            return json.loads(v) if v else None
        except ValueError:
            return v
    return {"id": l.id, "entity_type": l.entity_type, "entity_id": l.entity_id, "action": l.action,
            "action_label": AUDIT_ACTIONS.get(l.action, l.action), "changed_at": l.changed_at,
            "changed_by": _name(l.changed_by_user), "changed_by_id": l.changed_by_id,
            "old_value": load(l.old_value), "new_value": load(l.new_value), "reason": l.reason}


@router.get("/audit")
def finance_audit(entity_type: Optional[str] = None, action: Optional[str] = None,
                  actor_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
                  search: Optional[str] = Query(None, max_length=100),
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                  db: Session = Depends(get_db), _: models.User = need("finance.audit")):
    """Faqat o'qish. Audit yozuvlarini o'zgartirish/o'chirish endpoint'i yo'q."""
    AL = models.AuditLog
    q = db.query(AL).options(joinedload(AL.changed_by_user)).filter(AL.entity_type.in_(AUDIT_ENTITIES))
    if entity_type:
        q = q.filter(AL.entity_type == entity_type)
    if action:
        q = q.filter(AL.action == action)
    if actor_id:
        q = q.filter(AL.changed_by_id == actor_id)
    if date_from:
        q = q.filter(AL.changed_at >= tz.day_bounds(date_from)[0])
    if date_to:
        q = q.filter(AL.changed_at < tz.day_bounds(date_to)[1])
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.filter(or_(AL.new_value.ilike(like), AL.old_value.ilike(like), AL.reason.ilike(like)))
    total = q.count()
    rows = q.order_by(AL.changed_at.desc(), AL.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_audit_out(l) for l in rows],
            "meta": {"total": total, "page": page, "page_size": page_size,
                     "total_pages": max(1, (total + page_size - 1) // page_size)}}


# ── Moslik tekshiruvi ────────────────────────────────────────────────────────

@router.get("/reconcile")
def reconcile(db: Session = Depends(get_db), _: models.User = need("finance.reports")):
    """Jurnal ↔ registr va saqlangan ↔ hisoblangan qoldiq mosligi."""
    pay_total = Decimal(str(db.query(func.coalesce(func.sum(models.Payment.amount), 0)).scalar()))
    exp_total = Decimal(str(db.query(func.coalesce(func.sum(models.Expense.amount), 0)).scalar()))
    j_pay = ZERO
    for kind, s in db.query(FT.kind, func.sum(FT.amount_uzs)).filter(
            FT.status == "confirmed", FT.flow.in_(("income", "refund")), FT.student_id.isnot(None)).group_by(FT.kind):
        j_pay += -Decimal(str(s or 0)) if kind == "refund" else Decimal(str(s or 0))
    j_exp = Decimal(str(db.query(func.coalesce(func.sum(FT.amount_uzs), 0)).filter(
        FT.status == "confirmed", FT.flow == "expense").scalar()))
    accounts = []
    for a in db.query(models.FinanceAccount).order_by(models.FinanceAccount.id):
        cb = computed_balance(db, a)
        accounts.append({"id": a.id, "name": a.name, "stored": a.balance, "computed": cb,
                         "in_sync": cb == Decimal(str(a.balance))})
    return {
        "payments": {"ledger": pay_total, "journal": j_pay, "in_sync": pay_total == j_pay},
        "expenses": {"ledger": exp_total, "journal": j_exp, "in_sync": exp_total == j_exp},
        "accounts": accounts,
    }
