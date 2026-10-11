"""Ota-ona API — /parent/... (nginx orqali https://crm.minaracademy.uz/api/parent/...).

Shartnoma: docs/parent-api/README.md va docs/parent-api/openapi.yaml.
Xatolar yagona formatda (parent/errors.py): {"code", "message", "errors", "request_id"}.
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models, security, tz, uploads_sign
from ..database import get_db
from ..phone_utils import normalize_phone
from . import schemas, service
from .deps import get_current_parent, get_owned_child
from .errors import api_error, request_id
from .payments import config as pay_config
from .phone_auth.service import account_deleted_error, review_password_login
from .payments.checkout import create_checkout

router = APIRouter(prefix="/parent", tags=["parent"])

_RATE_HEADERS = {"Retry-After": "60"}
REFRESH_REUSE_GRACE_SEC = int(os.getenv("PARENT_REFRESH_REUSE_GRACE_SEC", "10"))
AVATAR_MAX_BYTES = 2 * 1024 * 1024
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
# Ilovadagi "Akkauntni o'chirish" tugmasi uchun flag. Endpoint flag'dan qat'i nazar ishlaydi.
ACCOUNT_DELETION_ENABLED = os.getenv("PARENT_ACCOUNT_DELETION_ENABLED", "false").strip().lower() == "true"
log = logging.getLogger("ithub.parent")


def _client_ip(request: Request) -> str:
    # X-Real-IP nginx tomonidan qayta yoziladi (ishonchli); X-Forwarded-For soxtalashtiriladi.
    return (request.headers.get("x-real-ip", "") or (request.client.host if request.client else "")).strip()


def _rate_limited():
    return api_error("rate_limited", "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring.", 429,
                     headers=_RATE_HEADERS)


def _invalid_credentials():
    return api_error("invalid_credentials", "Telefon raqam yoki parol xato", 401)


def _find_parent(db: Session, username: str) -> Optional[models.Parent]:
    """Aniq login bo'yicha, bo'lmasa telefonning oxirgi 9 raqami bo'yicha (formatdan qat'i nazar).
    Bir nechta akkaunt mos kelsa — hech biri tanlanmaydi (noaniqlik = 401)."""
    exact = db.query(models.Parent).filter(models.Parent.username == username.strip()).first()
    if exact:
        return exact
    key = normalize_phone(username)
    if len(key) != 9:
        return None
    candidates = (
        db.query(models.Parent)
        .filter((models.Parent.phone.like(f"%{key[-2:]}")) | (models.Parent.username.like(f"%{key[-2:]}")))
        .all()
    )
    matches = {p.id: p for p in candidates
               if normalize_phone(p.phone) == key or normalize_phone(p.username) == key}
    return next(iter(matches.values())) if len(matches) == 1 else None


# ── Public privacy policy (no parent login required) ────────────────────────

@router.get("/privacy.html", include_in_schema=False)
def privacy_policy():
    """Public, static privacy notice. The same URL works for App Store Review."""
    file_path = Path(__file__).resolve().parent.parent / "static" / "privacy.html"
    return FileResponse(
        file_path,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=schemas.TokenPair)
def login(payload: schemas.ParentLoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    if not security.rate_limit_ok(f"plogin-ip:{ip}", limit=15, window=60):
        raise _rate_limited()
    # login bo'yicha limit IP bilan birga — begona odam akkauntni bloklab qo'ya olmasin
    uname = normalize_phone(payload.username) or payload.username.strip().lower()
    if not security.rate_limit_ok(f"plogin-user-ip:{uname}:{ip}", limit=6, window=60) or \
            not security.rate_limit_ok(f"plogin-user:{uname}", limit=30, window=60):
        raise _rate_limited()

    review = review_password_login(db, payload.username, payload.password)
    if review is not None:
        if not review.is_active:
            raise _invalid_credentials()
        return _issue_tokens(db, review)
    parent = _find_parent(db, payload.username)
    if parent is not None and parent.deleted_at is not None:
        raise account_deleted_error()
    # Parol o'zgartirilmaydi (trim yo'q). Topilmasa ham bcrypt ishlaydi — vaqtdan bilib bo'lmasin.
    ok = security.verify_password(payload.password, parent.hashed_password if parent else security.DUMMY_HASH)
    if not parent or not ok or not parent.is_active:
        raise _invalid_credentials()
    return _issue_tokens(db, parent)


@router.post("/auth/refresh", response_model=schemas.TokenPair)
def refresh(payload: schemas.RefreshRequest, request: Request, db: Session = Depends(get_db)):
    if not security.rate_limit_ok(f"prefresh-ip:{_client_ip(request)}", limit=60, window=60):
        raise _rate_limited()
    token_hash = security.hash_token(payload.refresh_token)
    row = (
        db.query(models.ParentRefreshToken)
        .filter(models.ParentRefreshToken.token_hash == token_hash)
        .first()
    )
    if not row:
        raise api_error("invalid_token", "Refresh token yaroqsiz", 401)
    now = datetime.utcnow()

    if row.revoked_at is not None:
        # Rotatsiya qilingan tokenni qayta ishlatish — o'g'irlik alomati: butun sessiyalar
        # bekor qilinadi. Istisno: bir necha soniya ichidagi parallel refresh (tarmoq qayta
        # urinishi) — faqat 401, boshqa sessiyalarga tegilmaydi.
        if now - row.revoked_at > timedelta(seconds=REFRESH_REUSE_GRACE_SEC):
            db.query(models.ParentRefreshToken).filter(
                models.ParentRefreshToken.parent_id == row.parent_id,
                models.ParentRefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": now}, synchronize_session=False)
            db.commit()
            raise api_error("token_reuse", "Sessiya bekor qilindi. Qaytadan kiring.", 401)
        raise api_error("invalid_token", "Refresh token allaqachon ishlatilgan", 401)

    if row.expires_at < now:
        raise api_error("token_expired", "Refresh token muddati tugagan", 401)

    parent = db.query(models.Parent).filter(models.Parent.id == row.parent_id).first()
    if not parent or not parent.is_active:
        raise api_error("invalid_token", "Refresh token yaroqsiz", 401)

    # Atomik rotatsiya: parallel so'rovlardan faqat bittasi eski tokenni "yutadi".
    won = (
        db.query(models.ParentRefreshToken)
        .filter(models.ParentRefreshToken.id == row.id, models.ParentRefreshToken.revoked_at.is_(None))
        .update({"revoked_at": now}, synchronize_session=False)
    )
    if won != 1:
        db.rollback()
        raise api_error("invalid_token", "Refresh token allaqachon ishlatilgan", 401)
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


# ── Parent mobile app feature availability ────────────────────────────────

@router.get("/app-config", response_model=schemas.ParentAppCapabilities)
def parent_app_config(parent: models.Parent = Depends(get_current_parent)):
    """Fail closed: flag'lar faqat real sinovdan keyin env orqali qo'lda yoqiladi
    (PARENT_PAYMENTS_ENABLED + provayder sozlamalari, PARENT_ACCOUNT_DELETION_ENABLED)."""
    providers = pay_config.active_providers(parent)
    return schemas.ParentAppCapabilities(
        payments_enabled=bool(providers),
        payment_providers=providers,
        account_deletion_enabled=ACCOUNT_DELETION_ENABLED,
        privacy_policy_url="https://crm.minaracademy.uz/api/parent/privacy.html",
    )


# ── Profil ───────────────────────────────────────────────────────────────

def _profile(parent: models.Parent) -> schemas.ParentProfile:
    full = (parent.full_name or "").strip()
    return schemas.ParentProfile(
        display_name=(parent.display_name or "").strip() or full,
        full_name=full,
        phone=service.phone_e164(parent.phone) or parent.phone,
    )


@router.get("/profile", response_model=schemas.ParentProfile)
def profile(parent: models.Parent = Depends(get_current_parent)):
    return _profile(parent)


def _validated_avatar(raw: str) -> Optional[str]:
    """Bo'sh satr — rasmni o'chirish. Aks holda JPEG/PNG/WEBP, ≤ 2 MB, toza base64."""
    if raw == "":
        return None
    data = raw.split(",", 1)[1] if raw.startswith("data:") and "," in raw else raw
    try:
        blob = base64.b64decode("".join(data.split()), validate=True)
    except (binascii.Error, ValueError):
        raise api_error("validation_error", "Rasm noto'g'ri", 422,
                        errors={"avatar_base64": ["Yaroqli base64 emas."]})
    if not blob or len(blob) > AVATAR_MAX_BYTES:
        raise api_error("validation_error", "Rasm hajmi 2 MB dan oshmasin", 422,
                        errors={"avatar_base64": ["Rasm 1 bayt – 2 MB oralig'ida bo'lishi kerak."]})
    is_jpeg = blob[:3] == b"\xff\xd8\xff"
    is_png = blob[:8] == b"\x89PNG\r\n\x1a\n"
    is_webp = blob[:4] == b"RIFF" and blob[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise api_error("validation_error", "Faqat JPEG, PNG yoki WEBP rasm", 422,
                        errors={"avatar_base64": ["Faqat JPEG, PNG yoki WEBP."]})
    return base64.b64encode(blob).decode()


@router.patch("/profile", status_code=204, response_class=Response)
def update_profile(
    payload: schemas.ParentProfileUpdate,
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    sent = payload.__fields_set__
    if not sent:
        raise api_error("validation_error", "Hech qanday maydon yuborilmadi", 422,
                        errors={"__root__": ["display_name yoki avatar_base64 yuboring."]})
    if "display_name" in sent:
        parent.display_name = payload.display_name
    if "avatar_base64" in sent:
        if payload.avatar_base64 is None:
            raise api_error("validation_error", "Rasm noto'g'ri", 422,
                            errors={"avatar_base64": ["null emas, bo'sh satr yuboring (o'chirish uchun)."]})
        parent.avatar = _validated_avatar(payload.avatar_base64)
    db.commit()
    return Response(status_code=204)


@router.delete("/account", status_code=204, response_class=Response)
def delete_parent_account(
    request: Request,
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Ilovadan akkauntni o'chirish: kirish yopiladi, ma'lumot o'chirilmaydi.

    Barcha refresh tokenlar bekor qilinadi, akkaunt `is_active=false` + `deleted_at`. Keyin shu raqam bilan
    kirishda (parol yoki OTP) "Bunday raqam bizda mavjud emas" xabari chiqadi. Ota-ona ma'lumoti, farzand
    bog'lanishi, invoyslar va o'quvchining akademik yozuvlari saqlanadi — administrator CRM'da shu raqam bilan
    akkaunt yaratsa, o'sha akkaunt tiklanadi. 204 faqat commit'dan keyin.
    """
    # Bir vaqtdagi login/refresh bilan poyga bo'lmasin
    target = (
        db.query(models.Parent)
        .filter(models.Parent.id == parent.id)
        .with_for_update()
        .first()
    )
    if target is None or not target.is_active:
        raise api_error("unauthorized", "Token yaroqsiz", 401)

    parent_id = target.id
    try:
        db.query(models.ParentRefreshToken).filter(
            models.ParentRefreshToken.parent_id == parent_id
        ).delete(synchronize_session=False)
        target.is_active = False
        target.deleted_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        log.exception("parent account deletion failed parent_id=%s request_id=%s",
                      parent_id, request_id(request))
        raise
    # Audit: shaxsiy ma'lumotsiz (faqat id) — konteyner logi; DB'da parents.deleted_at.
    log.warning("AUDIT parent_account_deleted parent_id=%s mode=deactivated request_id=%s",
                parent_id, request_id(request))
    return Response(status_code=204)


# ── Farzandlar ───────────────────────────────────────────────────────────────

@router.get("/children", response_model=List[schemas.ChildRead])
def children(parent: models.Parent = Depends(get_current_parent), db: Session = Depends(get_db)):
    students = (
        db.query(models.Student)
        .join(models.ParentChild, models.ParentChild.student_id == models.Student.id)
        .filter(models.ParentChild.parent_id == parent.id)
        .order_by(models.Student.full_name.asc(), models.Student.id.asc())
        .all()
    )
    return [service.build_child(db, s) for s in students]


def _period(month: int, year: int) -> tuple:
    max_year = tz.today().year + 1
    if year < 2020 or year > max_year:
        raise api_error("validation_error", "Yil noto'g'ri", 422,
                        errors={"year": [f"2020–{max_year} oralig'ida bo'lishi kerak."]})
    return month, year


@router.get("/children/{child_id}/payment-summary", response_model=schemas.ChildPaymentSummary)
def payment_summary(
    child: models.Student = Depends(get_owned_child),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    month, year = _period(month, year)
    return service.build_payment_summary(db, child, month, year)


@router.post("/children/{child_id}/pay", response_model=schemas.CheckoutResponse)
def pay(
    payload: schemas.PayRequest,
    child: models.Student = Depends(get_owned_child),
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    url = create_checkout(db, parent, child, payload.group_id, payload.amount, payload.provider)
    return schemas.CheckoutResponse(checkout_url=url)


@router.get("/children/{child_id}/attendance", response_model=schemas.ChildAttendance)
def attendance(
    child: models.Student = Depends(get_owned_child),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    month, year = _period(month, year)
    return service.build_attendance(db, child, month, year)


@router.get("/children/{child_id}/schedule", response_model=List[schemas.ScheduleSlotRead])
def schedule(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_schedule(db, child)


# ── O'quv jarayoni ───────────────────────────────────────────────────────────

@router.get("/children/{child_id}/grades", response_model=List[schemas.GradeRead])
def grades(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_grades(db, child)


@router.get("/children/{child_id}/homework", response_model=List[schemas.HomeworkRead])
def homework(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_homework(db, child)


@router.get("/children/{child_id}/feedback", response_model=List[schemas.FeedbackRead])
def feedback(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_feedback(db, child)


@router.get("/children/{child_id}/certificates", response_model=List[schemas.CertificateRead])
def certificates(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_certificates(db, child)


@router.get("/children/{child_id}/teacher", response_model=schemas.TeacherContact)
def teacher_contact(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    contact = service.build_teacher(db, child)
    if not contact:
        raise api_error("teacher_not_assigned", "Bolaga o'qituvchi biriktirilmagan", 404)
    return contact


@router.get("/certificates/{certificate_id}/file", include_in_schema=False)
def certificate_file(certificate_id: int, exp: Optional[str] = None, sig: Optional[str] = None,
                     db: Session = Depends(get_db)):
    """Bearer'siz, imzolangan va muddatli havola (tashqi brauzer uchun)."""
    if not uploads_sign.verify_token(f"cert:{certificate_id}", exp, sig):
        raise api_error("link_expired", "Havola yaroqsiz yoki muddati o'tgan. Ilovada ro'yxatni yangilang.", 403)
    c = db.query(models.Certificate).filter(models.Certificate.id == certificate_id).first()
    if not c or not (c.file_url or "").startswith("https://"):
        raise api_error("not_found", "Sertifikat topilmadi", 404)
    marker = "/uploads/certificates/"
    if marker in c.file_url:
        name = c.file_url.rsplit("/", 1)[-1]
        base = os.path.realpath(os.path.join(UPLOAD_DIR, "certificates"))
        path = os.path.realpath(os.path.join(base, name))
        if not path.startswith(base + os.sep) or not os.path.isfile(path):
            raise api_error("not_found", "Sertifikat fayli topilmadi", 404)
        return FileResponse(path, media_type="application/pdf", headers={
            "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="certificate-{c.id}.pdf"',
        })
    return RedirectResponse(c.file_url, status_code=302)


# ── Bildirishnomalar ─────────────────────────────────────────────────────────

@router.get("/notifications", response_model=List[schemas.ParentNotificationRead])
def notifications(parent: models.Parent = Depends(get_current_parent), db: Session = Depends(get_db)):
    rows = (
        db.query(models.ParentNotification)
        .filter(models.ParentNotification.parent_id == parent.id)
        .order_by(models.ParentNotification.created_at.desc(), models.ParentNotification.id.desc())
        .all()
    )
    return [service.notification_read(n) for n in rows]


@router.post("/notifications/{notification_id}/read", status_code=204, response_class=Response)
def mark_read(
    notification_id: int,
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    n = db.query(models.ParentNotification).filter(models.ParentNotification.id == notification_id).first()
    if n is None:
        raise api_error("not_found", "Bildirishnoma topilmadi", 404)
    if n.parent_id != parent.id:
        raise api_error("forbidden", "Bu bildirishnoma sizga tegishli emas", 403)
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
    return Response(status_code=204)


# ── Qo'shimcha (joriy ilova chaqirmaydi; eski versiyalar uchun saqlangan) ────

@router.get("/events", response_model=List[schemas.EventRead])
def events(parent: models.Parent = Depends(get_current_parent), db: Session = Depends(get_db)):
    return service.build_events(db)


@router.get("/children/{child_id}/coins", response_model=schemas.ChildCoins)
def coins(child: models.Student = Depends(get_owned_child), db: Session = Depends(get_db)):
    return service.build_coins(db, child)
