"""Ota-ona API — /parent/... (nginx orqali /api/parent/...)."""
from __future__ import annotations

from datetime import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .. import models, tz
from ..database import get_db
from .. import security
from . import schemas, service
from .deps import get_current_parent, get_owned_child

router = APIRouter(prefix="/parent", tags=["parent"])


def _err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


# ── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=schemas.TokenPair)
def login(payload: schemas.ParentLoginRequest, request: Request, db: Session = Depends(get_db)):
    # X-Real-IP nginx tomonidan qayta yoziladi (ishonchli); X-Forwarded-For soxtalashtiriladi.
    ip = (request.headers.get("x-real-ip", "") or (request.client.host if request.client else "")).strip()
    if not security.rate_limit_ok(f"plogin-ip:{ip}", limit=15, window=60):
        raise _err("rate_limited", "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring.", 429)
    if not security.rate_limit_ok(f"plogin-user:{payload.username.lower()}", limit=6, window=60):
        raise _err("rate_limited", "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring.", 429)

    parent = db.query(models.Parent).filter(models.Parent.username == payload.username).first()
    if not parent or not security.verify_password(payload.password, parent.hashed_password):
        raise _err("invalid_credentials", "Login yoki parol xato", 401)
    if not parent.is_active:
        raise _err("account_disabled", "Akkount faol emas", 403)
    return _issue_tokens(db, parent)


@router.post("/auth/refresh", response_model=schemas.TokenPair)
def refresh(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    token_hash = security.hash_token(payload.refresh_token)
    row = (
        db.query(models.ParentRefreshToken)
        .filter(models.ParentRefreshToken.token_hash == token_hash)
        .first()
    )
    if not row:
        raise _err("invalid_token", "Refresh token yaroqsiz", 401)

    # Rotatsiya qilingan tokenni qayta ishlatish — o'g'irlik alomati: butun oilani bekor qilamiz
    if row.revoked_at is not None:
        db.query(models.ParentRefreshToken).filter(
            models.ParentRefreshToken.parent_id == row.parent_id,
            models.ParentRefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": datetime.utcnow()})
        db.commit()
        raise _err("token_reuse", "Sessiya bekor qilindi. Qaytadan kiring.", 401)

    if row.expires_at < datetime.utcnow():
        raise _err("token_expired", "Refresh token muddati tugagan", 401)

    parent = db.query(models.Parent).filter(models.Parent.id == row.parent_id).first()
    if not parent or not parent.is_active:
        raise _err("account_disabled", "Akkount faol emas", 401)

    row.revoked_at = datetime.utcnow()   # eski tokenni bekor qilamiz (rotatsiya)
    return _issue_tokens(db, parent)


def _issue_tokens(db: Session, parent: models.Parent) -> schemas.TokenPair:
    raw_refresh, refresh_hash = security.new_refresh_token()
    db.add(models.ParentRefreshToken(
        parent_id=parent.id, token_hash=refresh_hash,
        expires_at=security.refresh_expiry(), created_at=datetime.utcnow(),
    ))
    db.commit()
    return schemas.TokenPair(
        access_token=security.create_parent_access_token(parent.id),
        refresh_token=raw_refresh,
    )


# ── Profil / bolalar ─────────────────────────────────────────────────────────

@router.get("/profile", response_model=schemas.ParentProfile)
def profile(parent: models.Parent = Depends(get_current_parent)):
    return schemas.ParentProfile(
        full_name=parent.full_name, display_name=parent.display_name,
        phone=parent.phone, avatar=parent.avatar,
    )


@router.patch("/profile", response_model=schemas.ParentProfile)
def update_profile(
    payload: schemas.ParentProfileUpdate,
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    if payload.display_name is not None:
        name = payload.display_name.strip()
        if not name:
            raise _err("invalid_name", "Ism bo'sh bo'lishi mumkin emas", 422)
        parent.display_name = name
    if payload.avatar_base64 is not None:
        parent.avatar = payload.avatar_base64 or None   # bo'sh satr — rasmni o'chirish
    db.commit()
    return schemas.ParentProfile(
        full_name=parent.full_name, display_name=parent.display_name,
        phone=parent.phone, avatar=parent.avatar,
    )


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_parent_account(
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Permanently close a parent login and erase personally identifying account data.

    The parent owns only the *portal account*, not the academy's student, attendance,
    grade or payment records. Student records must never be cascade-deleted here.

    A financial invoice may need to remain for lawful accounting. Since invoices
    have a non-null FK to parents, keep only an anonymized, inactive tombstone
    when one exists. Otherwise delete the parent row entirely.
    """
    # Serialize concurrent account deletion and token issuing for this parent.
    target = (
        db.query(models.Parent)
        .filter(models.Parent.id == parent.id)
        .with_for_update()
        .first()
    )
    if target is None or not target.is_active:
        raise _err("unauthorized", "Token yaroqsiz", 401)

    parent_id = target.id
    try:
        # Prevent previously issued refresh tokens from ever being used again.
        db.query(models.ParentRefreshToken).filter(
            models.ParentRefreshToken.parent_id == parent_id
        ).delete(synchronize_session=False)

        # Clear all parent-only information while retaining shared student records.
        db.query(models.ParentNotification).filter(
            models.ParentNotification.parent_id == parent_id
        ).delete(synchronize_session=False)
        db.query(models.ParentChild).filter(
            models.ParentChild.parent_id == parent_id
        ).delete(synchronize_session=False)

        has_invoices = db.query(models.ParentInvoice.id).filter(
            models.ParentInvoice.parent_id == parent_id
        ).first() is not None
        if has_invoices:
            # Invoice rows are retained for a separately reviewed accounting policy.
            # Do not retain a usable login or any parent name, phone, avatar, etc.
            pseudonym = f"deleted-parent-{parent_id}"
            target.is_active = False
            target.full_name = "Deleted parent"
            target.display_name = None
            target.phone = pseudonym
            target.username = pseudonym
            target.avatar = None
            target.hashed_password = security.hash_password(secrets.token_urlsafe(32))
            target.created_by_id = None
        else:
            db.delete(target)

        db.commit()
    except Exception:
        db.rollback()
        raise
    return None


@router.get("/children", response_model=list[schemas.ChildRead])
def children(parent: models.Parent = Depends(get_current_parent), db: Session = Depends(get_db)):
    students = (
        db.query(models.Student)
        .join(models.ParentChild, models.ParentChild.student_id == models.Student.id)
        .filter(models.ParentChild.parent_id == parent.id)
        .order_by(models.Student.full_name.asc())
        .all()
    )
    return [service.build_child(db, s) for s in students]


@router.get("/children/{child_id}/payment-summary", response_model=schemas.ChildPaymentSummary)
def payment_summary(
    child: models.Student = Depends(get_owned_child),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2020),
    db: Session = Depends(get_db),
):
    now = tz.now()                      # standart oy/yil — Toshkent taqvimi
    return service.build_payment_summary(db, child, month or now.month, year or now.year)


@router.get("/children/{child_id}/attendance", response_model=schemas.ChildAttendance)
def attendance(
    child: models.Student = Depends(get_owned_child),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2020),
    db: Session = Depends(get_db),
):
    now = tz.now()                      # standart oy/yil — Toshkent taqvimi
    return service.build_attendance(db, child, month or now.month, year or now.year)


@router.get("/children/{child_id}/schedule", response_model=list[schemas.ScheduleSlotRead])
def schedule(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_schedule(db, child)


@router.get("/children/{child_id}/coins", response_model=schemas.ChildCoins)
def coins(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_coins(db, child)


# ── O'quv jarayoni (baholar / uy vazifasi / izohlar) ─────────────────────────

@router.get("/children/{child_id}/grades", response_model=list[schemas.GradeRead])
def grades(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_grades(db, child)


@router.get("/children/{child_id}/homework", response_model=list[schemas.HomeworkRead])
def homework(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_homework(db, child)


@router.get("/children/{child_id}/feedback", response_model=list[schemas.FeedbackRead])
def feedback(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_feedback(db, child)


@router.get("/children/{child_id}/teacher", response_model=schemas.TeacherContact)
def teacher_contact(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    contact = service.build_teacher(db, child)
    if not contact:
        raise _err("not_found", "O'qituvchi topilmadi", 404)
    return contact


@router.get("/children/{child_id}/certificates", response_model=list[schemas.CertificateRead])
def certificates(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_certificates(db, child)


# ── Tadbirlar ────────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[schemas.EventRead])
def events(parent: models.Parent = Depends(get_current_parent), db: Session = Depends(get_db)):
    return service.build_events(db)


# ── Bildirishnomalar ─────────────────────────────────────────────────────────

@router.get("/notifications", response_model=list[schemas.ParentNotificationRead])
def notifications(parent: models.Parent = Depends(get_current_parent), db: Session = Depends(get_db)):
    rows = (
        db.query(models.ParentNotification)
        .filter(models.ParentNotification.parent_id == parent.id)
        .order_by(models.ParentNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        schemas.ParentNotificationRead(
            id=n.id, type=n.type, title=n.title, body=n.body,
            created_at=n.created_at, is_read=n.read_at is not None,
        )
        for n in rows
    ]


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(
    notification_id: int,
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    n = (
        db.query(models.ParentNotification)
        .filter(
            models.ParentNotification.id == notification_id,
            models.ParentNotification.parent_id == parent.id,
        )
        .first()
    )
    if n and n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return None


# ── To'lov (stub — Payme/Click/Uzum keyin) ───────────────────────────────────

@router.post("/children/{child_id}/pay", response_model=schemas.CheckoutResponse)
def pay(
    payload: schemas.PayRequest,
    child: models.Student = Depends(get_owned_child),
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    group = db.query(models.Group).filter(models.Group.id == payload.group_id).first()
    if not group:
        raise _err("not_found", "Guruh topilmadi", 404)
    membership = next((m for m in child.group_memberships if m.group_id == group.id), None)
    if not membership:
        raise _err("not_found", "Bola bu guruhda emas", 404)

    # Validatsiya: 0 < amount <= joriy qarz + 2 oylik tarif
    from ..core_calc import student_month_owed
    monthly = student_month_owed(db, child.id, group.id)
    max_amount = monthly * 3  # joriy oy + 2 oy oldindan
    if payload.amount <= 0 or payload.amount > int(max_amount):
        raise _err("invalid_amount", "Summa noto'g'ri (juda katta yoki 0)", 422)

    invoice = models.ParentInvoice(
        parent_id=parent.id, student_id=child.id, group_id=group.id,
        amount=payload.amount, provider=payload.provider, status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(invoice)
    db.flush()
    invoice.checkout_ref = f"STUB-{payload.provider}-{invoice.id}"
    db.commit()
    # STUB: haqiqiy Payme/Click/Uzum integratsiyasi alohida vazifa
    return schemas.CheckoutResponse(
        checkout_url=f"https://checkout.minaracademy.uz/stub/{invoice.checkout_ref}",
    )
