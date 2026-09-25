"""O'quvchi sessiyasi: HttpOnly cookie + bazadagi (hashlangan) token.

* Token bazada faqat sha256 ko'rinishida — baza oqib ketsa ham sessiyani o'g'irlab bo'lmaydi.
* Logout / parol almashtirish / akkauntni o'chirish sessiyalarni darhol bekor qiladi.
* CSRF: cookie SameSite=Lax + holat o'zgartiruvchi so'rovlarda Origin tekshiruvi.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from .. import models, security, tz
from ..database import get_db
from .errors import MinarError
from .models import MinarAccount, MinarSession

COOKIE_NAME = "minar_session"
SESSION_DAYS = int(os.getenv("MINAR_SESSION_DAYS", "30"))
COOKIE_SECURE = os.getenv("MINAR_COOKIE_SECURE", "true").lower() != "false"
ALLOWED_ORIGINS = {
    o.strip().rstrip("/")
    for o in os.getenv("MINAR_ALLOWED_ORIGINS", "https://space.minaracademy.uz").split(",")
    if o.strip()
}
LOCK_AFTER = 10            # ketma-ket xato urinishlar
LOCK_MINUTES = 15
_TOUCH_EVERY = timedelta(minutes=5)

# login_id topilmaganda ham bcrypt vaqti sarflansin (mavjud ID'ni vaqt orqali bilib bo'lmasin)
_DUMMY_HASH = security.hash_password("dummy-password-for-timing")


def client_ip(request: Request) -> str:
    # nginx X-Real-IP ni $remote_addr bilan qayta yozadi; X-Forwarded-For'ga ishonmaymiz (soxtalashadi).
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_login_id(value: str) -> str:
    return (value or "").strip().upper()


def origin_allowed(origin: str | None) -> bool:
    """Origin sarlavhasi yo'q (brauzer bo'lmagan mijoz) — ruxsat; bor bo'lsa ro'yxatda bo'lishi shart."""
    if not origin:
        return True
    return origin.rstrip("/") in ALLOWED_ORIGINS


def check_origin(request: Request) -> None:
    """POST/PATCH/DELETE uchun CSRF himoyasi (dependency)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not origin_allowed(request.headers.get("origin")):
        raise MinarError(403, "So‘rov manbai ruxsat etilmagan.")


def login(db: Session, request: Request, response: Response, login_id: str, password: str) -> MinarAccount:
    ip = client_ip(request)
    lid = normalize_login_id(login_id)
    if not lid or not password or len(lid) > 20 or len(password) > 128:
        raise MinarError(400, "ID va parolni kiriting.")
    if not security.rate_limit_ok(f"minar-login-ip:{ip}", limit=20, window=60) or \
            not security.rate_limit_ok(f"minar-login-id:{lid}", limit=6, window=60):
        raise MinarError(429, "Juda ko‘p urinish. Bir daqiqadan keyin qayta urinib ko‘r.")

    acc = db.query(MinarAccount).filter(MinarAccount.login_id == lid).first()
    now = datetime.utcnow()
    if acc and acc.locked_until and acc.locked_until > now:
        raise MinarError(429, "Akkaunt vaqtincha bloklandi. 15 daqiqadan keyin urinib ko‘r yoki ustozingga ayt.")

    ok = security.verify_password(password, acc.password_hash if acc else _DUMMY_HASH)
    if not acc or not ok:
        if acc:
            acc.failed_attempts = (acc.failed_attempts or 0) + 1
            if acc.failed_attempts >= LOCK_AFTER:
                acc.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                acc.failed_attempts = 0
            db.commit()
        raise MinarError(401, "ID yoki parol noto‘g‘ri.")

    student = db.query(models.Student).filter(models.Student.id == acc.student_id).first()
    if not acc.is_active or not student or not student.is_active or student.is_archived:
        raise MinarError(403, "Akkaunt faol emas. Ustozingga murojaat qil.")

    acc.failed_attempts = 0
    acc.locked_until = None
    acc.last_login_at = now
    # eskirgan sessiyalarni tozalash + bittasini yaratish
    db.query(MinarSession).filter(MinarSession.account_id == acc.id, MinarSession.expires_at < now).delete()
    raw = secrets.token_urlsafe(32)
    db.add(MinarSession(
        account_id=acc.id, token_hash=_hash_token(raw), created_at=now,
        expires_at=now + timedelta(days=SESSION_DAYS), last_seen_at=now,
    ))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, raw, max_age=SESSION_DAYS * 86400, httponly=True,
        secure=COOKIE_SECURE, samesite="lax", path="/",
    )
    return acc


def logout(db: Session, request: Request, response: Response) -> None:
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        db.query(MinarSession).filter(MinarSession.token_hash == _hash_token(raw)).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


def revoke_sessions(db: Session, account_id: int) -> None:
    db.query(MinarSession).filter(MinarSession.account_id == account_id).delete()


def current_account(request: Request, db: Session = Depends(get_db)) -> MinarAccount:
    check_origin(request)
    raw = request.cookies.get(COOKIE_NAME)
    unauth = MinarError(401, "Akkauntingga kirishing kerak.")
    if not raw:
        raise unauth
    now = datetime.utcnow()
    sess = db.query(MinarSession).filter(MinarSession.token_hash == _hash_token(raw)).first()
    if not sess or sess.expires_at < now:
        raise unauth
    acc = db.query(MinarAccount).filter(MinarAccount.id == sess.account_id).first()
    if not acc or not acc.is_active:
        raise unauth
    student = db.query(models.Student).filter(models.Student.id == acc.student_id).first()
    if not student or not student.is_active or student.is_archived:
        raise unauth
    if now - sess.last_seen_at > _TOUCH_EVERY:
        sess.last_seen_at = now
        db.commit()
    return acc


def today_key() -> str:
    """Toshkent kuni kaliti (YYYY-MM-DD)."""
    return tz.today().isoformat()
