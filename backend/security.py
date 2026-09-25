"""Xavfsizlik primitivlari — parol hash, parent JWT, refresh token, rate-limit.

Standalone modul (main.py ga bog'liq emas) — circular import'dan qochish uchun.
Parent tokenlari `role=parent` claim bilan keladi, xodim tokenlaridan ajraladi.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta

import bcrypt as _bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "")
# Standart/bo'sh kalit bilan ishga tushmaymiz: aks holda har kim token soxtalashtira oladi.
if len(SECRET_KEY) < 16 or SECRET_KEY == "change-me-in-production":
    raise RuntimeError("SECRET_KEY .env da berilmagan yoki juda qisqa (kamida 16 belgi)")
ALGORITHM = "HS256"

PARENT_ACCESS_TTL_MIN = int(os.getenv("PARENT_ACCESS_TTL_MIN", "30"))
PARENT_REFRESH_TTL_DAYS = int(os.getenv("PARENT_REFRESH_TTL_DAYS", "30"))


# ── Parollar ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


# Login topilmaganda ham bcrypt ishlaydi — javob vaqtidan login mavjudligini bilib bo'lmasin.
DUMMY_HASH = _bcrypt.hashpw(b"timing-equalizer", _bcrypt.gensalt()).decode()


# ── Parent access JWT ────────────────────────────────────────────────────────

def create_parent_access_token(parent_id: int) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(parent_id),
        "role": "parent",
        "iat": now,
        "exp": now + timedelta(minutes=PARENT_ACCESS_TTL_MIN),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_parent_access_token(token: str) -> int | None:
    """Amal qiluvchi parent tokendan parent_id qaytaradi, aks holda None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("role") != "parent":
        return None
    sub = payload.get("sub")
    return int(sub) if sub and str(sub).isdigit() else None


# ── Refresh tokenlar (opaque, hashlangan holda saqlanadi) ────────────────────

def new_refresh_token() -> tuple[str, str]:
    """(ochiq_token, sha256_hash) — ochiq token faqat mijozga beriladi."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.utcnow() + timedelta(days=PARENT_REFRESH_TTL_DAYS)


# ── Oddiy in-process rate limiter (pm2 fork single-process) ──────────────────
# Xotirada — qayta ishga tushganda nolga tushadi (bitta jarayon uchun yetarli).
# `.env`: RATE_LIMIT_ENABLED=false — butunlay o'chirish (masalan yuklama testlari uchun).

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
_MAX_WINDOW = 3600          # eng uzun ishlatiladigan oyna (soniya)
_PRUNE_EVERY = 1000         # har shuncha chaqiruvda eskirgan kalitlar tozalanadi

_hits: dict[str, list[float]] = defaultdict(list)
_calls = 0


def _prune(now: float) -> None:
    """Oxirgi urinishi eng uzun oynadan eski bo'lgan kalitlarni o'chiradi —
    aks holda har bir yangi IP/login lug'atda abadiy qolib, xotira o'sib boradi."""
    for key in [k for k, v in _hits.items() if not v or now - v[-1] >= _MAX_WINDOW]:
        del _hits[key]


def rate_limit_ok(key: str, *, limit: int, window: int) -> bool:
    """True — ruxsat; False — limit oshdi."""
    global _calls
    if not RATE_LIMIT_ENABLED:
        return True
    now = time.time()
    _calls += 1
    if _calls % _PRUNE_EVERY == 0:
        _prune(now)
    hits = [t for t in _hits[key] if now - t < window]
    if len(hits) >= limit:
        _hits[key] = hits
        return False
    hits.append(now)
    _hits[key] = hits
    return True
