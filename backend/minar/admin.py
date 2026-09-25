"""Xodimlar API'si (CRM tomoni): o'quvchi akkauntlari va Minar shop buyurtmalari.

Bearer JWT (mavjud CRM login). Rollar: admin, support_teacher. Bu router space domenida OCHILMAYDI —
nginx `space.minaracademy.uz/api/` faqat `/minar/...` ga yo'naltiriladi.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, security, tz
from ..database import get_db
from ..models import UserRole
from . import auth as student_auth
from . import catalog as C
from .models import MinarAccount, MinarPurchase

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"      # 0/o, 1/l/i kabi adashadigan belgilarsiz
ORDER_STATUSES = ("pending", "ready", "collected")


def staff_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer),
               db: Session = Depends(get_db)) -> models.User:
    from .. import main            # kechiktirilgan import: main.py oxirida shu router ulanadi
    user = main.require_auth(credentials, db)
    if user.role not in (UserRole.admin.value, UserRole.metodist.value):
        raise HTTPException(status_code=403, detail="Bu amal faqat admin va support teacher uchun")
    return user


def _audit(db: Session, user: models.User, action: str, account_id: int, data: dict) -> None:
    from .. import main
    main.write_audit(db, entity_type="minar_account", entity_id=account_id, action=action,
                     changed_by_id=user.id, new_value=data)


def _new_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(8))


def _login_id(student_id: int) -> str:
    return f"MA{student_id:04d}"


def _active_group(db: Session, student_id: int) -> Optional[models.Group]:
    return (
        db.query(models.Group)
        .join(models.GroupStudent, models.GroupStudent.group_id == models.Group.id)
        .filter(models.GroupStudent.student_id == student_id, models.Group.is_active.is_(True),
                models.GroupStudent.left_at.is_(None))
        .order_by(models.GroupStudent.joined_at.desc())
        .first()
    )


def _create(db: Session, student: models.Student, user: models.User, course: Optional[str],
            password: Optional[str]) -> dict:
    group = _active_group(db, student.id)
    course = course or C.default_course_for_stage(group.stage if group else None)
    plain = password or _new_password()
    acc = MinarAccount(
        student_id=student.id, login_id=_login_id(student.id), password_hash=security.hash_password(plain),
        course=course, created_by_id=user.id, created_at=datetime.utcnow(), password_changed_at=datetime.utcnow(),
    )
    db.add(acc)
    db.flush()
    _audit(db, user, "create", acc.id, {"student_id": student.id, "course": course})
    return {"student_id": student.id, "full_name": student.full_name, "group": group.name if group else None,
            "login_id": acc.login_id, "password": plain, "course": course}


class AccountCreate(BaseModel):
    student_id: int
    course: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=64)


class BulkCreate(BaseModel):
    group_id: int
    course: Optional[str] = None


class AccountPatch(BaseModel):
    course: Optional[str] = None
    is_active: Optional[bool] = None


class OrderPatch(BaseModel):
    status: str


def _check_course(course: Optional[str]) -> None:
    if course is not None and course not in C.COURSES:
        raise HTTPException(status_code=400, detail="Kurs HTML, CSS yoki JavaScript bo'lishi kerak")


@router.get("/accounts")
def list_accounts(group_id: Optional[int] = Query(None), q: Optional[str] = Query(None),
                  active: Optional[bool] = Query(None),
                  db: Session = Depends(get_db), _: models.User = Depends(staff_user)):
    query = db.query(MinarAccount, models.Student).join(models.Student, models.Student.id == MinarAccount.student_id)
    if group_id:
        query = query.join(models.GroupStudent, models.GroupStudent.student_id == models.Student.id) \
                     .filter(models.GroupStudent.group_id == group_id,
                             models.GroupStudent.left_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(models.Student.full_name.ilike(like) | MinarAccount.login_id.ilike(like))
    if active is not None:
        query = query.filter(MinarAccount.is_active.is_(active))
    now = datetime.utcnow()
    out = []
    for acc, st in query.order_by(models.Student.full_name).limit(500).all():
        g = _active_group(db, st.id)
        out.append({
            "student_id": st.id, "full_name": st.full_name, "group": g.name if g else None,
            "login_id": acc.login_id, "course": acc.course, "is_active": acc.is_active,
            "locked": bool(acc.locked_until and acc.locked_until > now),
            "xp": acc.xp, "streak": acc.streak,
            "last_login_at": tz.isoformat(acc.last_login_at) if acc.last_login_at else None,
            "created_at": tz.isoformat(acc.created_at),
        })
    return out


@router.post("/accounts", status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db), user: models.User = Depends(staff_user)):
    _check_course(payload.course)
    student = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    if student.is_archived or not student.is_active:
        raise HTTPException(status_code=400, detail="Talaba faol emas")
    if db.query(MinarAccount.id).filter(MinarAccount.student_id == student.id).first():
        raise HTTPException(status_code=409, detail="Bu talabaning akkaunti bor. Parolni tiklash uchun reset-password ishlating")
    result = _create(db, student, user, payload.course, payload.password)
    db.commit()
    return result


@router.post("/accounts/bulk", status_code=201)
def create_accounts_bulk(payload: BulkCreate, db: Session = Depends(get_db), user: models.User = Depends(staff_user)):
    _check_course(payload.course)
    group = db.query(models.Group).filter(models.Group.id == payload.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    students = (
        db.query(models.Student)
        .join(models.GroupStudent, models.GroupStudent.student_id == models.Student.id)
        .outerjoin(MinarAccount, MinarAccount.student_id == models.Student.id)
        .filter(models.GroupStudent.group_id == group.id, models.Student.is_active.is_(True),
                models.Student.is_archived.is_(False), MinarAccount.id.is_(None),
                models.GroupStudent.left_at.is_(None))
        .order_by(models.Student.full_name).limit(200).all()
    )
    created: List[dict] = []
    for st in students:
        item = _create(db, st, user, payload.course or C.default_course_for_stage(group.stage), None)
        item["group"] = group.name
        created.append(item)
    db.commit()
    return {"created": created, "count": len(created)}


def _account_by_student(db: Session, student_id: int) -> MinarAccount:
    acc = db.query(MinarAccount).filter(MinarAccount.student_id == student_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Bu talabaning Minar akkaunti yo'q")
    return acc


@router.post("/accounts/{student_id}/reset-password")
def reset_password(student_id: int, db: Session = Depends(get_db), user: models.User = Depends(staff_user)):
    acc = _account_by_student(db, student_id)
    plain = _new_password()
    acc.password_hash = security.hash_password(plain)
    acc.password_changed_at = datetime.utcnow()
    acc.failed_attempts, acc.locked_until = 0, None
    student_auth.revoke_sessions(db, acc.id)
    _audit(db, user, "reset_password", acc.id, {"student_id": student_id})
    db.commit()
    return {"student_id": student_id, "login_id": acc.login_id, "password": plain}


@router.patch("/accounts/{student_id}")
def patch_account(student_id: int, payload: AccountPatch, db: Session = Depends(get_db),
                  user: models.User = Depends(staff_user)):
    _check_course(payload.course)
    acc = _account_by_student(db, student_id)
    changes = {}
    if payload.course is not None:
        acc.course = changes["course"] = payload.course
    if payload.is_active is not None:
        acc.is_active = changes["is_active"] = payload.is_active
        if not payload.is_active:
            student_auth.revoke_sessions(db, acc.id)
    _audit(db, user, "update", acc.id, changes)
    db.commit()
    return {"student_id": student_id, "login_id": acc.login_id, "course": acc.course, "is_active": acc.is_active}


def _order_dict(p: MinarPurchase, acc: MinarAccount, st: models.Student) -> dict:
    return {"id": p.id, "student_id": st.id, "student_name": st.full_name, "login_id": acc.login_id,
            "product_id": p.product_id, "name": p.name, "price": p.price, "status": p.status,
            "created_at": tz.isoformat(p.created_at), "updated_at": tz.isoformat(p.updated_at)}


@router.get("/orders")
def list_orders(status: Optional[str] = Query(None), db: Session = Depends(get_db),
                _: models.User = Depends(staff_user)):
    """Minar shop sovg'a buyurtmalari (Hero buyumlari — darhol `delivered` — bu yerda ko'rinmaydi)."""
    q = (
        db.query(MinarPurchase, MinarAccount, models.Student)
        .join(MinarAccount, MinarAccount.id == MinarPurchase.account_id)
        .join(models.Student, models.Student.id == MinarAccount.student_id)
        .filter(MinarPurchase.status.in_(ORDER_STATUSES))
    )
    if status:
        if status not in ORDER_STATUSES:
            raise HTTPException(status_code=400, detail="Holat: pending, ready yoki collected")
        q = q.filter(MinarPurchase.status == status)
    return [_order_dict(*row) for row in q.order_by(MinarPurchase.created_at.desc()).limit(500).all()]


@router.patch("/orders/{order_id}")
def update_order(order_id: str, payload: OrderPatch, db: Session = Depends(get_db),
                 user: models.User = Depends(staff_user)):
    if payload.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Holat: pending, ready yoki collected")
    row = (
        db.query(MinarPurchase, MinarAccount, models.Student)
        .join(MinarAccount, MinarAccount.id == MinarPurchase.account_id)
        .join(models.Student, models.Student.id == MinarAccount.student_id)
        .filter(MinarPurchase.id == order_id).first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    p, acc, st = row
    if p.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Bu buyurtma (Hero buyumi) holati o'zgartirilmaydi")
    old = p.status
    p.status, p.updated_at, p.updated_by_id = payload.status, datetime.utcnow(), user.id
    _audit(db, user, "order_status", acc.id, {"order_id": p.id, "from": old, "to": payload.status})
    db.commit()
    return _order_dict(p, acc, st)
