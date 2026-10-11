"""PhoneVerificationService — Telegram Gateway OTP bilan ota-ona login/registratsiyasi.

Xavfsizlik qoidalari:
  * Bir telefon uchun bir vaqtda faqat bitta `pending` verification — DB'dagi unikal
    qisman indeks parallel so'rovlarni to'xtatadi (ikkinchisi IntegrityError → 429).
  * Kod Gateway'ga faqat yozuv (rezerv) commit qilingandan keyin yuboriladi; send
    timeout'ida qayta yuborilmaydi (ikki marta kod/to'lov bo'lmasin).
  * Urinishlar `UPDATE … WHERE attempts < 5` bilan atomik oshiriladi (Gateway'ga murojaatdan
    oldin) — parallel taxminlar ham hisobga olinadi.
  * `code_valid`dan keyin `UPDATE … WHERE status='pending'` — verification faqat bir marta
    ishlatiladi (replay himoyasi); token berish shu tranzaksiyada.
  * Loglarda telefon maskalanadi, kod/token yozilmaydi.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ... import models, security
from ...phone_utils import normalize_phone
from ..errors import api_error
from .gateway import GatewayError, TelegramGatewayClient

log = logging.getLogger("ithub.phone_auth")

CODE_LENGTH = 6
OTP_TTL_SEC = 120
RESEND_COOLDOWN_SEC = 60
MAX_ATTEMPTS = 5
MAX_RESENDS = 3

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


# App Store review akkaunti: shu raqamga Telegram'ga kod yuborilmaydi, qat'iy kod qabul qilinadi.
# Ikkalasi ham faqat env'da (repo public) — biri berilmasa funksiya o'chiq.
REVIEW_GATEWAY_ID = "app-review-static"


def review_phone() -> Optional[str]:
    raw = os.getenv("PARENT_REVIEW_PHONE", "").strip()
    code = os.getenv("PARENT_REVIEW_OTP", "").strip()
    if not raw or not re.fullmatch(r"\d{4,6}", code):
        return None
    try:
        return normalize_e164(raw)
    except Exception:
        return None


def is_review_phone(phone: str) -> bool:
    rp = review_phone()
    return bool(rp) and secrets.compare_digest(rp, phone)


def review_password_login(db: Session, raw_username: str, password: str) -> Optional[models.Parent]:
    """Parol ekrani orqali review kirishi: raqam + qat'iy kod mos bo'lsa ota-ona (yo'q bo'lsa yaratiladi).
    Mos kelmasa None — oddiy parol tekshiruvi davom etadi."""
    rp = review_phone()
    code = os.getenv("PARENT_REVIEW_OTP", "").strip()
    if not rp or not secrets.compare_digest(password.encode(), code.encode()):
        return None
    try:
        phone = normalize_e164(raw_username)
    except Exception:
        return None
    if not secrets.compare_digest(rp, phone):
        return None
    key = normalize_phone(phone)
    parent = next((p for p in db.query(models.Parent).filter(models.Parent.phone.like(f"%{key[-2:]}")).all()
                   if normalize_phone(p.phone) == key or normalize_phone(p.username) == key), None)
    if parent is None:
        parent = models.Parent(full_name=phone, phone=phone, username=phone,
                               hashed_password=security.hash_password(secrets.token_urlsafe(32)),
                               is_active=True, created_at=datetime.utcnow())
        db.add(parent)
        db.flush()
    log.info("review account password login parent=%s", parent.id)
    return parent


def allowed_prefixes() -> List[str]:
    raw = os.getenv("PHONE_OTP_ALLOWED_PREFIXES", "+998")
    return [p.strip() for p in raw.split(",") if p.strip()]


def mask_phone(phone: str) -> str:
    """+998901234567 → +998******67"""
    if not phone or len(phone) < 7:
        return "***"
    return phone[:4] + "*" * (len(phone) - 6) + phone[-2:]


def normalize_e164(raw: str) -> str:
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if re.fullmatch(r"\d{9}", s):
        s = "+998" + s
    elif re.fullmatch(r"998\d{9}", s):
        s = "+" + s
    if not _E164.match(s) or (s.startswith("+998") and len(s) != 13):
        raise api_error("invalid_phone_number", "Telefon raqam noto'g'ri. Namuna: +998901234567", 400,
                        errors={"phoneNumber": ["E.164 formatida kiriting, masalan +998901234567."]})
    if not any(s.startswith(p) for p in allowed_prefixes()):
        raise api_error("phone_not_supported", "Bu davlat raqamlari qo'llab-quvvatlanmaydi", 400,
                        errors={"phoneNumber": ["Faqat " + ", ".join(allowed_prefixes()) + " raqamlari."]})
    return s


def _too_many(message: str, retry_after: int, code: str = "too_many_requests"):
    return api_error(code, message, 429, headers={"Retry-After": str(max(1, int(retry_after)))})


def _gateway_error(e: GatewayError):
    log.warning("telegram gateway error kind=%s detail=%s", e.kind, e.detail)
    if e.kind == "not_reachable":
        return api_error("telegram_not_available",
                         "Bu raqamga Telegram orqali kod yuborib bo'lmaydi. Raqamda Telegram akkaunti borligini tekshiring.",
                         400, errors={"phoneNumber": ["Telegram akkaunti topilmadi yoki xabar qabul qilmaydi."]})
    if e.kind == "rate_limited":
        return _too_many("Juda ko'p so'rov. Birozdan so'ng qayta urinib ko'ring.", 60)
    if e.kind == "rejected":
        return api_error("gateway_error", "Tasdiqlash xizmati so'rovni bajarmadi. Keyinroq urinib ko'ring.", 502)
    if e.kind == "config":
        log.error("telegram gateway is not configured or token/balance invalid")
    return api_error("gateway_unavailable", "Tasdiqlash xizmati vaqtincha ishlamayapti. Keyinroq urinib ko'ring.",
                     503, headers={"Retry-After": "30"})


class PhoneVerificationService:
    def __init__(self, db: Session, gateway: TelegramGatewayClient):
        self.db = db
        self.gateway = gateway

    # ── Rate limit ──────────────────────────────────────────────────────────
    @staticmethod
    def _limit_send(phone: str, ip: str) -> None:
        if not security.rate_limit_ok(f"otp-send-ip:{ip}", limit=10, window=600):
            raise _too_many("Juda ko'p so'rov. 10 daqiqadan so'ng qayta urinib ko'ring.", 600)
        if not is_review_phone(phone) and not security.rate_limit_ok(f"otp-send-phone:{phone}", limit=5, window=3600):
            raise _too_many("Bu raqamga juda ko'p kod so'raldi. Keyinroq urinib ko'ring.", 3600)

    # ── Kod yuborish ────────────────────────────────────────────────────────
    def _send_new(self, phone: str, ip: str, resend_count: int) -> models.PhoneVerification:
        now = datetime.utcnow()
        old_request_ids = [
            r[0] for r in self.db.query(models.PhoneVerification.gateway_request_id)
            .filter(models.PhoneVerification.phone == phone, models.PhoneVerification.status == "pending",
                    models.PhoneVerification.gateway_request_id.isnot(None)).all()
        ]
        self.db.query(models.PhoneVerification).filter(
            models.PhoneVerification.phone == phone, models.PhoneVerification.status == "pending",
        ).update({"status": "cancelled"}, synchronize_session=False)
        row = models.PhoneVerification(
            public_id=secrets.token_urlsafe(24), phone=phone, status="pending", attempts=0,
            resend_count=resend_count, ip=ip[:64] if ip else None, created_at=now,
            expires_at=now + timedelta(seconds=OTP_TTL_SEC),
        )
        self.db.add(row)
        try:
            self.db.commit()          # rezerv: parallel so'rov shu yerda unikal indeksga uriladi
        except IntegrityError:
            self.db.rollback()
            raise _too_many("Bu raqam uchun so'rov allaqachon bajarilmoqda.", RESEND_COOLDOWN_SEC,
                            code="request_in_progress")

        for rid in old_request_ids:   # eski kodlar Telegram'da ham bekor (best-effort)
            self.gateway.revoke_verification_message(rid)

        if is_review_phone(phone):
            row.gateway_request_id = REVIEW_GATEWAY_ID
            row.last_sent_at = now
            self.db.commit()
            log.info("otp review account verification=%s (gateway skipped)", row.id)
            return row

        try:
            request_id = self.gateway.send_verification_message(phone, CODE_LENGTH, OTP_TTL_SEC)
        except GatewayError as e:
            row.status = "failed"
            self.db.commit()
            raise _gateway_error(e)
        sent = datetime.utcnow()
        row.gateway_request_id = request_id
        row.last_sent_at = sent
        row.expires_at = sent + timedelta(seconds=OTP_TTL_SEC)
        self.db.commit()
        log.info("otp sent phone=%s verification=%s resend=%s", mask_phone(phone), row.id, resend_count)
        return row

    def request_code(self, raw_phone: str, ip: str) -> models.PhoneVerification:
        phone = normalize_e164(raw_phone)
        active = (
            self.db.query(models.PhoneVerification)
            .filter(models.PhoneVerification.phone == phone, models.PhoneVerification.status == "pending")
            .first()
        )
        if active and active.last_sent_at:
            wait = RESEND_COOLDOWN_SEC - (datetime.utcnow() - active.last_sent_at).total_seconds()
            if wait > 0:
                raise _too_many(f"Qayta so'rashdan oldin {int(wait) + 1} soniya kuting.", wait + 1,
                                code="resend_cooldown")
        self._limit_send(phone, ip)
        if not self.gateway.configured and not is_review_phone(phone):
            raise _gateway_error(GatewayError("config"))
        return self._send_new(phone, ip, resend_count=0)

    def _load(self, public_id: str, raw_phone: str) -> models.PhoneVerification:
        phone = normalize_e164(raw_phone)
        row = (
            self.db.query(models.PhoneVerification)
            .filter(models.PhoneVerification.public_id == (public_id or "").strip())
            .first()
        )
        if row is None or row.status == "failed":
            raise api_error("verification_not_found", "Tasdiqlash so'rovi topilmadi. Kodni qaytadan so'rang.", 404)
        if not secrets.compare_digest(row.phone, phone):
            raise api_error("phone_mismatch", "Telefon raqam tasdiqlash so'roviga mos emas", 400,
                            errors={"phoneNumber": ["Kod so'ralgan raqamni kiriting."]})
        return row

    def resend(self, public_id: str, raw_phone: str, ip: str) -> models.PhoneVerification:
        row = self._load(public_id, raw_phone)
        if row.status != "pending":
            raise api_error("verification_not_active", "Bu tasdiqlash so'rovi faol emas. Kodni qaytadan so'rang.", 409)
        if row.resend_count >= MAX_RESENDS:
            raise _too_many("Qayta yuborish limiti tugadi. Keyinroq yangi kod so'rang.", 3600, code="too_many_resends")
        now = datetime.utcnow()
        sent = row.last_sent_at or row.created_at
        wait = RESEND_COOLDOWN_SEC - (now - sent).total_seconds()
        if wait > 0:
            raise _too_many(f"Qayta yuborishdan oldin {int(wait) + 1} soniya kuting.", wait + 1, code="resend_cooldown")
        self._limit_send(row.phone, ip)
        if not self.gateway.configured and not is_review_phone(row.phone):
            raise _gateway_error(GatewayError("config"))
        # Atomik: parallel resend'lardan faqat bittasi o'tadi
        count, phone = row.resend_count, row.phone
        won = (
            self.db.query(models.PhoneVerification)
            .filter(models.PhoneVerification.id == row.id, models.PhoneVerification.status == "pending",
                    models.PhoneVerification.resend_count == count)
            .update({"resend_count": count + 1}, synchronize_session=False)
        )
        self.db.commit()
        if won != 1:
            raise api_error("verification_not_active", "So'rov allaqachon yangilangan", 409)
        return self._send_new(phone, ip, resend_count=count + 1)

    # ── Tekshirish ──────────────────────────────────────────────────────────
    def _mark(self, row: models.PhoneVerification, status: str) -> None:
        self.db.query(models.PhoneVerification).filter(
            models.PhoneVerification.id == row.id, models.PhoneVerification.status == "pending",
        ).update({"status": status}, synchronize_session=False)
        self.db.commit()

    def verify(self, public_id: str, raw_phone: str, code: str, ip: str) -> models.Parent:
        if not security.rate_limit_ok(f"otp-verify-ip:{ip}", limit=30, window=600):
            raise _too_many("Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring.", 600)
        row = self._load(public_id, raw_phone)
        if row.status == "verified":
            raise api_error("verification_already_used", "Bu kod allaqachon ishlatilgan", 409)
        if row.status == "cancelled":
            raise api_error("verification_superseded", "Yangi kod yuborilgan. Oxirgi kodni kiriting.", 409)
        if row.status == "max_attempts" or row.attempts >= MAX_ATTEMPTS:
            raise _too_many("Urinishlar soni tugadi. Yangi kod so'rang.", RESEND_COOLDOWN_SEC,
                            code="code_max_attempts_exceeded")
        if row.status == "expired" or datetime.utcnow() > row.expires_at:
            self._mark(row, "expired")
            raise api_error("code_expired", "Kod muddati tugagan. Yangi kod so'rang.", 401)
        if not row.gateway_request_id:
            raise api_error("verification_not_ready", "Kod hali yuborilmoqda. Birozdan so'ng urinib ko'ring.", 409)

        took = (
            self.db.query(models.PhoneVerification)
            .filter(models.PhoneVerification.id == row.id, models.PhoneVerification.status == "pending",
                    models.PhoneVerification.attempts < MAX_ATTEMPTS)
            .update({"attempts": models.PhoneVerification.attempts + 1}, synchronize_session=False)
        )
        self.db.commit()
        if took != 1:
            self.db.refresh(row)
            if row.status == "verified":
                raise api_error("verification_already_used", "Bu kod allaqachon ishlatilgan", 409)
            raise _too_many("Urinishlar soni tugadi. Yangi kod so'rang.", RESEND_COOLDOWN_SEC,
                            code="code_max_attempts_exceeded")
        self.db.refresh(row)

        if row.gateway_request_id == REVIEW_GATEWAY_ID:
            ok = is_review_phone(row.phone) and secrets.compare_digest(
                code.encode(), os.getenv("PARENT_REVIEW_OTP", "").strip().encode())
            status = "code_valid" if ok else "code_invalid"
        else:
            if len(code) != CODE_LENGTH:
                raise api_error("validation_error", "Kod 6 ta raqamdan iborat bo'lishi kerak", 400,
                                errors={"code": ["6 ta raqam kiriting."]})
            try:
                status = self.gateway.check_verification_status(row.gateway_request_id, code)
            except GatewayError as e:
                raise _gateway_error(e)

        if status == "code_valid":
            return self._complete(row)
        if status == "code_max_attempts_exceeded":
            self._mark(row, "max_attempts")
            raise _too_many("Urinishlar soni tugadi. Yangi kod so'rang.", RESEND_COOLDOWN_SEC,
                            code="code_max_attempts_exceeded")
        if status == "expired":
            self._mark(row, "expired")
            raise api_error("code_expired", "Kod muddati tugagan. Yangi kod so'rang.", 401)
        if status == "code_invalid":
            left = MAX_ATTEMPTS - row.attempts
            if left <= 0:
                self._mark(row, "max_attempts")
                raise _too_many("Urinishlar soni tugadi. Yangi kod so'rang.", RESEND_COOLDOWN_SEC,
                                code="code_max_attempts_exceeded")
            raise api_error("code_invalid", f"Kod noto'g'ri. Yana {left} ta urinish qoldi.", 401,
                            errors={"code": [f"Kod noto'g'ri ({left} ta urinish qoldi)."]})
        log.warning("telegram gateway unexpected verification status for verification=%s", row.id)
        raise api_error("gateway_error", "Tasdiqlash xizmatidan kutilmagan javob", 502)

    def _complete(self, row: models.PhoneVerification) -> models.Parent:
        """Bir martalik iste'mol + login/registratsiya — bitta tranzaksiya (commit chaqiruvchida)."""
        now = datetime.utcnow()
        won = (
            self.db.query(models.PhoneVerification)
            .filter(models.PhoneVerification.id == row.id, models.PhoneVerification.status == "pending")
            .update({"status": "verified", "verified_at": now}, synchronize_session=False)
        )
        if won != 1:
            self.db.rollback()
            raise api_error("verification_already_used", "Bu kod allaqachon ishlatilgan", 409)

        key = normalize_phone(row.phone)
        candidates = (
            self.db.query(models.Parent)
            .filter((models.Parent.phone.like(f"%{key[-2:]}")) | (models.Parent.username.like(f"%{key[-2:]}")))
            .all()
        )
        matches = {p.id: p for p in candidates
                   if normalize_phone(p.phone) == key or normalize_phone(p.username) == key}
        if len(matches) > 1:
            self.db.rollback()
            log.error("phone auth: several parent accounts share phone=%s", mask_phone(row.phone))
            raise api_error("account_conflict", "Bu raqam bir nechta akkauntga biriktirilgan. Administratorga murojaat qiling.", 409)
        parent = next(iter(matches.values()), None)
        if parent is None:
            parent = models.Parent(
                full_name=row.phone, phone=row.phone, username=row.phone,
                hashed_password=security.hash_password(secrets.token_urlsafe(32)),   # parol bilan kirib bo'lmaydi
                is_active=True, created_at=now,
            )
            self.db.add(parent)
            self.db.flush()
            log.info("phone auth: new parent registered phone=%s parent=%s", mask_phone(row.phone), parent.id)
        elif not parent.is_active:
            self.db.rollback()
            raise api_error("account_disabled", "Akkaunt bloklangan. Administratorga murojaat qiling.", 403)
        parent.phone_verified_at = now
        self.db.query(models.PhoneVerification).filter(models.PhoneVerification.id == row.id).update(
            {"parent_id": parent.id}, synchronize_session=False)
        return parent
