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
from typing import Any, Optional

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from .. import models, security, tz
from ..database import get_db
from .errors import MinarError
from .models import MinarAccount, MinarLoginToken, MinarSession

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
QR_TOKEN_TTL = timedelta(days=int(os.getenv("MINAR_QR_DAYS", "14")))
PASSWORD_RESET_WINDOW = timedelta(minutes=30)
PASSWORD_MIN, PASSWORD_MAX = 6, 64

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


def account_usable(acc: MinarAccount | None, student: models.Student | None) -> bool:
    """Akkaunt ochiq va talabasi faol bo'lsa (test akkaunt uchun talaba holati tekshirilmaydi)."""
    if not acc or not acc.is_active or not student:
        return False
    return acc.is_test or (student.is_active and not student.is_archived)


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
    if not account_usable(acc, student):
        raise MinarError(403, "Akkaunt faol emas. Ustozingga murojaat qil.")

    _open_session(db, response, acc)
    return acc


def _open_session(db: Session, response: Response, acc: MinarAccount, *, password_reset: bool = False) -> None:
    """Muvaffaqiyatli kirish: hisoblagichlarni tozalaydi, sessiya yaratadi va cookie qo'yadi (commit qiladi)."""
    now = datetime.utcnow()
    acc.failed_attempts = 0
    acc.locked_until = None
    acc.last_login_at = now
    # eskirgan sessiyalarni tozalash + bittasini yaratish
    db.query(MinarSession).filter(MinarSession.account_id == acc.id, MinarSession.expires_at < now).delete()
    raw = secrets.token_urlsafe(32)
    db.add(MinarSession(
        account_id=acc.id, token_hash=_hash_token(raw), created_at=now,
        expires_at=now + timedelta(days=SESSION_DAYS), last_seen_at=now,
        password_reset_until=now + PASSWORD_RESET_WINDOW if password_reset else None,
    ))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, raw, max_age=SESSION_DAYS * 86400, httponly=True,
        secure=COOKIE_SECURE, samesite="lax", path="/",
    )


# ── QR orqali kirish ────────────────────────────────────────────────────────

def issue_login_token(db: Session, acc: MinarAccount, created_by_id: Optional[int]) -> str:
    """Yangi QR token (eski ishlatilmaganlari bekor bo'ladi). Xom token faqat shu yerda qaytadi."""
    now = datetime.utcnow()
    db.query(MinarLoginToken).filter(MinarLoginToken.account_id == acc.id,
                                     MinarLoginToken.used_at.is_(None)).delete()
    raw = secrets.token_urlsafe(24)
    db.add(MinarLoginToken(account_id=acc.id, token_hash=_hash_token(raw), created_by_id=created_by_id,
                           created_at=now, expires_at=now + QR_TOKEN_TTL))
    return raw


def qr_login(db: Session, request: Request, response: Response, token: Any) -> MinarAccount:
    ip = client_ip(request)
    if not security.rate_limit_ok(f"minar-qr-ip:{ip}", limit=20, window=60):
        raise MinarError(429, "Juda ko‘p urinish. Bir daqiqadan keyin qayta urinib ko‘r.")
    invalid = MinarError(401, "QR-kod eskirgan yoki ishlatilgan. Ustozingdan yangisini so‘ra.")
    if not isinstance(token, str) or not (16 <= len(token) <= 64):
        raise invalid
    now = datetime.utcnow()
    row = db.query(MinarLoginToken).filter(MinarLoginToken.token_hash == _hash_token(token)) \
        .with_for_update().first()
    if not row or row.used_at or row.expires_at < now:
        raise invalid
    acc = db.query(MinarAccount).filter(MinarAccount.id == row.account_id).first()
    student = acc and db.query(models.Student).filter(models.Student.id == acc.student_id).first()
    if not account_usable(acc, student):
        raise MinarError(403, "Akkaunt faol emas. Ustozingga murojaat qil.")
    row.used_at = now
    _open_session(db, response, acc, password_reset=True)
    return acc


# ── Parolni almashtirish ────────────────────────────────────────────────────

def _current_session(db: Session, request: Request) -> Optional[MinarSession]:
    raw = request.cookies.get(COOKIE_NAME)
    return raw and db.query(MinarSession).filter(MinarSession.token_hash == _hash_token(raw)).first()


def password_status(db: Session, request: Request) -> dict:
    sess = _current_session(db, request)
    return {"canSetWithoutCurrent": bool(sess and sess.password_reset_until
                                         and sess.password_reset_until > datetime.utcnow())}


def change_password(db: Session, request: Request, acc: MinarAccount, current: Any, new: Any) -> None:
    if not security.rate_limit_ok(f"minar-pw:{acc.id}", limit=5, window=60):
        raise MinarError(429, "Juda ko‘p urinish. Bir daqiqadan keyin qayta urinib ko‘r.")
    if not isinstance(new, str) or not (PASSWORD_MIN <= len(new) <= PASSWORD_MAX):
        raise MinarError(400, f"Yangi parol {PASSWORD_MIN}–{PASSWORD_MAX} belgidan iborat bo‘lsin.")
    if len(set(new)) < 3 or new.upper() == acc.login_id:
        raise MinarError(400, "Bu parol juda oson. Harf va raqamlarni aralashtir.")
    sess = _current_session(db, request)
    now = datetime.utcnow()
    via_qr = bool(sess and sess.password_reset_until and sess.password_reset_until > now)
    if not via_qr:
        if not isinstance(current, str) or not security.verify_password(current, acc.password_hash):
            raise MinarError(400, "Hozirgi parol noto‘g‘ri.")
    acc.password_hash = security.hash_password(new)
    acc.password_changed_at = now
    # boshqa qurilmalardagi sessiyalar yopiladi, joriy sessiya qoladi
    q = db.query(MinarSession).filter(MinarSession.account_id == acc.id)
    if sess:
        q = q.filter(MinarSession.id != sess.id)
        sess.password_reset_until = None
    q.delete(synchronize_session=False)
    db.query(MinarLoginToken).filter(MinarLoginToken.account_id == acc.id).delete()
    db.commit()


def logout(db: Session, request: Request, response: Response) -> None:
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        db.query(MinarSession).filter(MinarSession.token_hash == _hash_token(raw)).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


def revoke_sessions(db: Session, account_id: int) -> None:
    db.query(MinarSession).filter(MinarSession.account_id == account_id).delete()
    db.query(MinarLoginToken).filter(MinarLoginToken.account_id == account_id).delete()


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
    student = acc and db.query(models.Student).filter(models.Student.id == acc.student_id).first()
    if not account_usable(acc, student):
        raise unauth
    if now - sess.last_seen_at > _TOUCH_EVERY:
        sess.last_seen_at = now
        db.commit()
    return acc


def today_key() -> str:
    """Toshkent kuni kaliti (YYYY-MM-DD)."""
    return tz.today().isoformat()
