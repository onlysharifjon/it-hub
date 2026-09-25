import calendar
import hashlib
import html
import json
import os
import re
from uuid import uuid4
from datetime import datetime, timedelta, date, timezone
from decimal import Decimal
from typing import List, Optional
import io

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse
import fastapi.encoders as _fastapi_encoders
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import func, extract, or_
from sqlalchemy.orm import Session, selectinload, joinedload

from . import models, schemas, core_calc, bot_client, work_center, tz
from .database import get_db
from .models import UserRole

load_dotenv()

# ── Vaqt zonasi ──────────────────────────────────────────────────────────────
# Bazadagi barcha datetime'lar naive UTC (`tz.utcnow()`) sifatida saqlanadi —
# JWT va ichki taqqoslashlar shunga tayanadi, bu o'zgarmaydi. Foydalanuvchiga
# ko'rinadigan hamma narsa Toshkent (+05:00):
#   * API javoblari — quyidagi global encoder offset qo'shadi;
#   * "bugun"/"shu oy" — `tz.today()` va `tz.now()` (`date.today()` EMAS,
#     u serverda UTC bo'lgani uchun 00:00–05:00 orasida kechagi kunni beradi);
#   * sana filtrlari — `tz.day_bounds()` / `tz.month_bounds()`.
# Batafsil: backend/tz.py
_fastapi_encoders.ENCODERS_BY_TYPE[datetime] = tz.isoformat

from .security import SECRET_KEY  # bo'sh/standart kalit bilan ishga tushmaydi
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # default 12h
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")

# Admin seed (parol faqat env orqali — kodda default parol yo'q)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")            # bo'lmasa admin yaratilmaydi
SEED_DEMO_USERS = os.getenv("SEED_DEMO_USERS", "false").lower() == "true"

auth_scheme = HTTPBearer(auto_error=False)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
AVATARS_DIR = f"{UPLOAD_DIR}/avatars"
CERTIFICATES_DIR = f"{UPLOAD_DIR}/certificates"
STUDENTS_DIR = f"{UPLOAD_DIR}/students"
STUDENT_PHOTOS_DIR = f"{UPLOAD_DIR}/student_photos"
STAFF_PHOTOS_DIR = f"{UPLOAD_DIR}/staff_photos"
os.makedirs(AVATARS_DIR, exist_ok=True)
os.makedirs(CERTIFICATES_DIR, exist_ok=True)
os.makedirs(STUDENTS_DIR, exist_ok=True)
os.makedirs(STUDENT_PHOTOS_DIR, exist_ok=True)
os.makedirs(STAFF_PHOTOS_DIR, exist_ok=True)

CAMERA_API_KEY = os.getenv("CAMERA_API_KEY", "")

# Fon rejalashtiruvchilari (investor statistikasi, eslatmalar). Docker'da ular alohida
# `worker` servisida (backend/worker.py) ishlaydi, API konteynerlarida esa
# SCHEDULERS_ENABLED=false — shunda crm-api'ni bir nechta nusxada ishga tushirsa ham
# xabarlar ikki marta yuborilmaydi. PM2 (flag'siz) — eski xatti-harakat.
SCHEDULERS_ENABLED = os.getenv("SCHEDULERS_ENABLED", "true").lower() != "false"

# Standart docs'ni o'chiramiz — nginx `/api/` prefiksi bilan mos kelmaydi va o'rniga
# parol bilan himoyalangan variantini beramiz (openapi.json ham himoyalangan).
# openapi_url=None — FastAPI'ning himoyasiz built-in /openapi.json marshrutini o'chiradi.
DOCS_PASSWORD = os.getenv("DOCS_PASSWORD", "")  # bo'sh — /docs butunlay yopiq
import logging
from contextlib import asynccontextmanager

log = logging.getLogger("ithub")

# Startup vazifalari (seederlar, fon rejalashtiruvchilari) — `@_on_startup` bilan
# ro'yxatga olinadi va lifespan'da tartib bilan ishga tushadi (eskirgan
# `@app.on_event("startup")` o'rniga).
_startup_hooks: list = []


def _on_startup(fn):
    _startup_hooks.append(fn)
    return fn


@asynccontextmanager
async def _lifespan(_app):
    for fn in _startup_hooks:
        fn()
    yield


app = FastAPI(
    title="IT Hub — LMS API", version="3.0.0",
    docs_url=None, redoc_url=None, openapi_url=None,
    lifespan=_lifespan,
)

# Public bazaviy yo'l (nginx orqali): https://crm.minaracademy.uz/api
PUBLIC_API_PREFIX = os.getenv("PUBLIC_API_PREFIX", "/api")
# Tashqi (mobil ilova) uchun to'liq URL yasashda ishlatiladi — masalan sertifikat PDF linki
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://crm.minaracademy.uz").rstrip("/")


# ── Hujjatlar himoyasi (HTTP Basic — parol: DOCS_PASSWORD, default "1107") ────
# Brauzer parol so'raydi; login (username) e'tiborga olinmaydi, faqat parol tekshiriladi.
# Muvaffaqiyatli kirilgach brauzer Basic ma'lumotlarni /openapi.json'ga ham avtomatik yuboradi.
import secrets as _sec
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_docs_basic = HTTPBasic(auto_error=False)


def require_docs_auth(creds: Optional[HTTPBasicCredentials] = Depends(_docs_basic)) -> bool:
    unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Hujjatlar uchun parol kerak",
        headers={"WWW-Authenticate": 'Basic realm="Minar CRM Docs"'},
    )
    if not DOCS_PASSWORD or not creds or not _sec.compare_digest(
            creds.password.encode(), DOCS_PASSWORD.encode()):
        raise unauth
    return True


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui(_: bool = Depends(require_docs_auth)):
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url=f"{PUBLIC_API_PREFIX}/openapi.json",
        title="Minar CRM API — Swagger",
    )


@app.get("/redoc", include_in_schema=False)
def custom_redoc(_: bool = Depends(require_docs_auth)):
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(
        openapi_url=f"{PUBLIC_API_PREFIX}/openapi.json",
        title="Minar CRM API — ReDoc",
    )


@app.get("/openapi.json", include_in_schema=False)
def protected_openapi(_: bool = Depends(require_docs_auth)):
    from fastapi.responses import JSONResponse
    return JSONResponse(app.openapi())

# ── Default users ──────────────────────────────────────────────────────────────

# Demo akkountlar faqat SEED_DEMO_USERS=true bo'lsa (dev muhitda) yaratiladi —
# parollar env orqali beriladi, kodda qattiq kodlangan parol yo'q.
DEMO_USERS = [
    {"username": "metodist",    "role": UserRole.metodist.value,    "full_name": "Metodist"},
    {"username": "teacher1",    "role": UserRole.teacher.value,     "full_name": "Sarvar Toshmatov"},
    {"username": "hunter1",     "role": UserRole.hunter.value,      "full_name": "Hunter 1"},
    {"username": "callcenter1", "role": UserRole.call_center.value, "full_name": "Call Center 1"},
]


# ── Default lead pipeline ────────────────────────────────────────────────────
# slug'lar eski LeadStatus enum qiymatlariga mos — status ustuni bilan sinxron.

DEFAULT_STAGES = [
    {"slug": "new",       "name": "Yangi",             "order": 10, "color": "sky",     "icon": "sparkles",       "kind": "lead"},
    {"slug": "called",    "name": "Qo'ng'iroq qilindi","order": 20, "color": "indigo",  "icon": "phone",          "kind": "lead"},
    # "Javob bermadi" — lid yo'qolgani EMAS: raqam ko'tarilmadi, ya'ni uni
    # yana chaqirish kerak. Shuning uchun kind="lead" (voronkada qoladi) va
    # "Qayta qo'ng'iroq"dan oldin turadi: avval javob yo'q, keyin kelishilgan
    # qayta qo'ng'iroq. Slug ish markazidagi "no_answer" natijasi bilan bir xil.
    {"slug": "no_answer", "name": "Javob bermadi",     "order": 25, "color": "slate",   "icon": "phone-slash",    "kind": "lead"},
    {"slug": "callback",  "name": "Qayta qo'ng'iroq",  "order": 30, "color": "amber",   "icon": "phone-incoming", "kind": "lead"},
    {"slug": "will_come", "name": "Keladi",            "order": 40, "color": "violet",  "icon": "calendar",       "kind": "lead"},
    {"slug": "demo",      "name": "Demo",              "order": 45, "color": "purple",  "icon": "video",          "kind": "lead"},
    {"slug": "enrolled",  "name": "To'landi",          "order": 50, "color": "emerald", "icon": "graduation-cap", "kind": "won"},
    {"slug": "rejected",  "name": "Rad etildi",        "order": 60, "color": "red",     "icon": "x-circle",       "kind": "lost"},
]

DEFAULT_SOURCES = [
    {"name": "Instagram",  "is_campaign": False},
    {"name": "Telegram",   "is_campaign": False},
    {"name": "Walk-in",    "is_campaign": False, "is_default": True},
    {"name": "Website",    "is_campaign": False},
    {"name": "Referral",   "is_campaign": False},
    {"name": "Qo'ng'iroq", "is_campaign": False},
    {"name": "Boshqa",     "is_campaign": False},
]


@_on_startup
def ensure_default_users() -> None:
    """Faqat admin akkountini ta'minlaydi (parol env orqali). Mavjud parollarga tegmaydi."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        # Admin — faqat ADMIN_PASSWORD berilgan bo'lsa va admin hali yo'q bo'lsa
        if ADMIN_PASSWORD:
            exists = db.query(models.User).filter(models.User.username == ADMIN_USERNAME).first()
            if not exists:
                db.add(models.User(
                    username=ADMIN_USERNAME,
                    hashed_password=hash_password(ADMIN_PASSWORD),
                    role=UserRole.admin.value,
                    full_name="Administrator",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ))
        # Demo akkountlar — faqat aniq yoqilgan bo'lsa (dev muhit)
        if SEED_DEMO_USERS:
            demo_pw = os.getenv("DEMO_PASSWORD", "")
            if demo_pw:
                for u in DEMO_USERS:
                    if not db.query(models.User).filter(models.User.username == u["username"]).first():
                        db.add(models.User(
                            username=u["username"],
                            hashed_password=hash_password(demo_pw),
                            role=u["role"], full_name=u["full_name"],
                            is_active=True, created_at=datetime.utcnow(),
                        ))
        db.commit()
    finally:
        db.close()


@_on_startup
def ensure_default_pipeline() -> None:
    """Standart pipeline bosqichlari va lid manbalarini yaratadi (bir marta)."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(models.LeadStage).count() == 0:
            for s in DEFAULT_STAGES:
                db.add(models.LeadStage(**s, created_at=datetime.utcnow()))
        if db.query(models.LeadSource).count() == 0:
            for s in DEFAULT_SOURCES:
                db.add(models.LeadSource(
                    name=s["name"],
                    is_campaign=s.get("is_campaign", False),
                    is_default=s.get("is_default", False),
                    is_active=True,
                    created_at=datetime.utcnow(),
                ))
        db.commit()
    except Exception:
        log.exception("Startup: standart pipeline/manbalarni yaratib bo'lmadi")
        db.rollback()
    finally:
        db.close()


# Har bir tizimда doim mavjud bo'ladigan standart tariflar (guruh formasida default tanlov)
DEFAULT_TARIFFS = [
    {"name": "Pro",     "price": 700000},
    {"name": "Starter", "price": 500000},
]


@_on_startup
def ensure_default_tariffs() -> None:
    """Global 'Pro' va 'Starter' tariflarini ta'minlaydi (nomiga qarab, takrorlamaydi)."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        for t in DEFAULT_TARIFFS:
            exists = (
                db.query(models.Tariff)
                .filter(func.lower(func.trim(models.Tariff.name)) == t["name"].lower())
                .first()
            )
            if not exists:
                db.add(models.Tariff(name=t["name"], price=t["price"], is_active=True))
        db.commit()
    except Exception:
        log.exception("Startup: standart tariflarni yaratib bo'lmadi")
        db.rollback()
    finally:
        db.close()


_cors_origins = CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from . import uploads_sign


@app.get("/uploads/{rel_path:path}", include_in_schema=False)
def serve_upload(rel_path: str, exp: Optional[str] = None, sig: Optional[str] = None):
    """Yuklangan fayllar. Sertifikat PDF'lari (uuid nomli) ochiq; qolgan hamma narsa
    (avatarlar, talaba va yuz rasmlari) faqat backend bergan imzoli, muddatli havola
    bilan ochiladi — ko'ring: uploads_sign. Avval bu papka butunlay ochiq edi va
    `student_photos/{id}.jpg` kabi yo'llarni ketma-ket terib yuz rasmlarini olish mumkin edi."""
    base = os.path.realpath(UPLOAD_DIR)
    path = os.path.realpath(os.path.join(base, rel_path))
    if not path.startswith(base + os.sep):
        raise HTTPException(status_code=404)
    if not rel_path.startswith(uploads_sign.PUBLIC_PREFIXES) and not uploads_sign.verify(rel_path, exp, sig):
        raise HTTPException(status_code=403, detail="Havola yaroqsiz yoki muddati o'tgan")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, headers={
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    })

# Ota-ona mobil ilovasi API (/parent/...) — alohida paketda
from .parent.router_parent import router as parent_router
from .parent.notifications import notify_parents_of_student
app.include_router(parent_router)

# Facebook Lead Ads webhook (Make.com -> /leads/facebook) — alohida paketda
from .phone_utils import normalize_phone, dedup_key, is_placeholder_phone, format_phone
from .facebook_leads import router as facebook_leads_router
app.include_router(facebook_leads_router)


# ── Rate limiting (in-memory; single-process pm2 fork) ───────────────────────
from . import security as _security


def _client_ip(request: Request) -> str:
    # nginx `proxy_set_header X-Real-IP $remote_addr;` bilan haqiqiy IP'ni qo'yadi va uni
    # qayta yozadi — shuning uchun ishonchli. X-Forwarded-For'ning eng chap qiymati mijoz
    # tomonidan soxtalashtiriladi (rate-limit'ni aylanib o'tishga imkon berardi), unga ishonmaymiz.
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def rate_limit(key: str, *, limit: int, window: int):
    """Sliding-window limiter (security.rate_limit_ok — yagona ombor). Limitdan oshsa 429."""
    if not _security.rate_limit_ok(key, limit=limit, window=window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring.",
        )


# ── Auth helpers ──────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    # Buzuq/bo'sh hash bcrypt'da ValueError beradi — 500 o'rniga "parol xato" (False) qaytaramiz.
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def _pw_version(hashed_password: Optional[str]) -> str:
    """Parol "versiyasi" — hash'dan olingan qisqa barmoq izi. Tokenga `pv` sifatida
    yoziladi: parol almashsa hash ham o'zgaradi va eski tokenlar darhol yaroqsiz bo'ladi."""
    return hashlib.sha256((hashed_password or "").encode()).hexdigest()[:16]


# Login topilmaganda ham bcrypt ishlaydi — javob vaqtidan login bor-yo'qligini bilib bo'lmasin.
_DUMMY_HASH = _bcrypt.hashpw(b"timing-equalizer", _bcrypt.gensalt()).decode()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Yuklab olish (chek/Excel) URL'lariga token query-parametrda beriladi — u nginx logi,
# brauzer tarixi va Referer orqali sizib chiqishi mumkin. Shuning uchun uzoq muddatli
# kirish tokeni emas, `typ=download` bo'lgan qisqa muddatli (2 daqiqa) token ishlatiladi.
DOWNLOAD_TOKEN_TTL_SECONDS = 120


def create_download_token(user: models.User) -> str:
    now = datetime.utcnow()
    return jwt.encode(
        {"sub": user.username, "typ": "download", "pv": _pw_version(user.hashed_password),
         "exp": now + timedelta(seconds=DOWNLOAD_TOKEN_TTL_SECONDS)},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token xato yoki muddati o'tgan",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials or credentials.scheme.lower() != "bearer":
        raise exc
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    if payload.get("typ") is not None:
        # Yuklab-olish (typ=download) va boshqa maxsus tokenlar API uchun emas
        raise exc
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise exc
    if not _sec.compare_digest(str(payload.get("pv", "")), _pw_version(user.hashed_password)):
        raise exc  # parol almashtirilgan — eski token bekor
    # Check expiry on each request
    if user.expires_at and datetime.utcnow() > user.expires_at:
        user.is_active = False
        user.blocked_reason = user.blocked_reason or "Akkount muddati tugadi"
        user.blocked_at = datetime.utcnow()
        db.commit()
        raise exc
    return user


def require_staff(user: models.User = Depends(require_auth)) -> models.User:
    """Har qanday tizimga kirgan xodim (rol cheklovisiz)."""
    return user


def require_metodist(user: models.User = Depends(require_auth)) -> models.User:
    if user.role not in (UserRole.metodist.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="Bu amal faqat metodist/admin uchun")
    return user


def require_admin(user: models.User = Depends(require_auth)) -> models.User:
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Bu amal faqat admin uchun")
    return user


def require_hunter(user: models.User = Depends(require_auth)) -> models.User:
    if user.role not in (UserRole.hunter.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="Bu amal faqat hunter/admin uchun")
    return user


def require_call_center(user: models.User = Depends(require_auth)) -> models.User:
    if user.role not in (UserRole.call_center.value, UserRole.hunter.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="Bu amal faqat call_center/hunter/admin uchun")
    return user


def require_crm_access(user: models.User = Depends(require_auth)) -> models.User:
    """Hunter, Sales, Call center va admin lidlarga kirishi mumkin."""
    allowed = (UserRole.hunter.value, UserRole.sales.value,
               UserRole.call_center.value, UserRole.admin.value)
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Bu amal faqat hunter/sales/call_center/admin uchun")
    return user


def require_attendance_editor(user: models.User = Depends(require_auth)) -> models.User:
    """Yo'qlama qilish: admin, metodist, hunter va teacher uchun ruxsat.
    Teacher faqat o'z guruhida — bu endpoint ichida tekshiriladi."""
    allowed = (UserRole.admin.value, UserRole.metodist.value,
               UserRole.hunter.value, UserRole.teacher.value)
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Yo'qlama qilishga ruxsat yo'q")
    return user


def require_lms_write(user: models.User = Depends(require_auth)) -> models.User:
    """Metodist, Hunter, Sales, Call center va admin — talabalar va guruhlar bilan ishlash."""
    allowed = (UserRole.metodist.value, UserRole.hunter.value,
               UserRole.sales.value, UserRole.call_center.value, UserRole.admin.value)
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Bu amal faqat metodist/hunter/sales/call_center/admin uchun")
    return user


def require_feedback_viewer(user: models.User = Depends(require_auth)) -> models.User:
    """Izohlar ro'yxati: admin, metodist, teacher, hunter va call_center."""
    allowed = (UserRole.admin.value, UserRole.metodist.value, UserRole.teacher.value,
               UserRole.hunter.value, UserRole.call_center.value)
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Bu amal faqat metodist/teacher/hunter/call_center/admin uchun")
    return user


def require_feedback_status(user: models.User = Depends(require_auth)) -> models.User:
    """Izoh statusini o'zgartirish (hal qilindi / javob bermadi): hunter, call_center va admin."""
    allowed = (UserRole.hunter.value, UserRole.call_center.value, UserRole.admin.value)
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Bu amal faqat hunter/call_center/admin uchun")
    return user


def require_audit(user: models.User = Depends(require_auth)) -> models.User:
    """Xodimlarga ogohlantirish berish: audit va admin."""
    allowed = (UserRole.audit.value, UserRole.admin.value)
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Bu amal faqat audit/admin uchun")
    return user


def _resolve_token(raw_token: str, db: Session, *, expect_download: bool) -> models.User:
    """Decode a raw JWT string and return the authenticated admin user.

    expect_download=True — token query-parametrda kelgan; faqat `typ=download` bo'lgan
    qisqa muddatli token qabul qilinadi (uzoq muddatli kirish tokeni URL'da yuborilmasin).
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token xato yoki muddati o'tgan",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    is_download = payload.get("typ") == "download"
    if expect_download and not is_download:
        raise exc
    if not expect_download and is_download:
        # Yuklab-olish tokeni oddiy API chaqiruvlari uchun ishlatilmasin.
        raise exc
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise exc
    if not _sec.compare_digest(str(payload.get("pv", "")), _pw_version(user.hashed_password)):
        raise exc
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Bu amal faqat admin uchun")
    return user


def require_admin_download(
    _token: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """File-download auth: Bearer header (oddiy token) YOKI ?_token= (qisqa download tokeni)."""
    if credentials and credentials.scheme.lower() == "bearer":
        return _resolve_token(credentials.credentials, db, expect_download=False)
    if _token:
        return _resolve_token(_token, db, expect_download=True)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token xato yoki muddati o'tgan",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ── Audit log helper ──────────────────────────────────────────────────────────

def write_audit(db, *, entity_type, entity_id, action, changed_by_id, old_value=None, new_value=None):
    log = models.AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_by_id=changed_by_id,
        changed_at=datetime.utcnow(),
        old_value=json.dumps(old_value, ensure_ascii=False, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None,
    )
    db.add(log)


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    # Brute-force himoyasi: IP bo'yicha 10/min, login bo'yicha 5/min
    rate_limit(f"login-ip:{ip}", limit=10, window=60)
    # Login bo'yicha limit IP bilan birga — begona odam ataylab xato parol terib
    # xodimning akkauntini bloklab qo'ya olmasin; umumiy (IP'siz) limit esa ko'p
    # IP'dan taqsimlangan brute-force'ni cheklaydi.
    uname = payload.username.lower()
    rate_limit(f"login-user-ip:{uname}:{ip}", limit=5, window=60)
    rate_limit(f"login-user:{uname}", limit=30, window=60)

    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user:
        verify_password(payload.password, _DUMMY_HASH)  # vaqt bir xil bo'lsin
        raise HTTPException(status_code=401, detail="Login yoki parol xato")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Login yoki parol xato")

    # Muddati tugagan — avtomatik bloklash
    if user.expires_at and datetime.utcnow() > user.expires_at:
        if user.is_active:
            user.is_active = False
            user.blocked_reason = "Akkount muddati tugadi"
            user.blocked_at = datetime.utcnow()
            db.commit()
        raise HTTPException(status_code=403, detail={
            "code": "expired",
            "reason": user.blocked_reason or "Akkount muddati tugadi",
            "contact": user.blocked_contact or "",
        })

    # Bloklangan
    if not user.is_active:
        raise HTTPException(status_code=403, detail={
            "code": "blocked",
            "reason": user.blocked_reason or "Akkount faol emas",
            "contact": user.blocked_contact or "",
        })

    token = create_access_token({"sub": user.username, "role": user.role,
                                 "pv": _pw_version(user.hashed_password)})
    return schemas.TokenResponse(access_token=token)


@app.get("/auth/me", response_model=schemas.UserRead)
def me(user: models.User = Depends(require_auth)):
    return user


@app.get("/auth/download-token")
def download_token(user: models.User = Depends(require_admin)):
    """Chek/Excel URL'lari uchun qisqa muddatli (2 daqiqa) token beradi.
    Uzoq muddatli kirish tokeni URL query-parametrida yuborilmasligi uchun."""
    return {"token": create_download_token(user), "expires_in": DOWNLOAD_TOKEN_TTL_SECONDS}


@app.put("/me", response_model=schemas.UserRead)
def update_me(payload: schemas.ProfileUpdate, db: Session = Depends(get_db), user: models.User = Depends(require_auth)):
    """Har qanday foydalanuvchi o'z profil ma'lumotlarini (ism, parol) o'zgartiradi."""
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    if payload.password is not None:
        # Parol o'zgartirilsa — joriy parol tasdiqlanishi shart
        if not payload.current_password or not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Joriy parol noto'g'ri")
        user.hashed_password = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


def _image_ext(contents: bytes, allow_gif: bool = True) -> Optional[str]:
    """Fayl ichidagi magic bytes bo'yicha rasm turini aniqlaydi — fayl nomi va
    content-type'ga ishonmaymiz. Rasm bo'lmasa None."""
    if contents.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "webp"
    if allow_gif and contents[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


async def _read_image_upload(file: UploadFile, *, allow_gif: bool = True) -> tuple:
    """Rasmni o'qiydi, hajm (5 MB) va ichidagi turini tekshiradi -> (bytes, ext)."""
    contents = await file.read(MAX_AVATAR_BYTES + 1)
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(400, "Fayl hajmi 5 MB dan oshmasin")
    ext = _image_ext(contents, allow_gif=allow_gif)
    if not ext:
        raise HTTPException(400, "Faqat JPEG, PNG, WebP" + (" yoki GIF" if allow_gif else "") + " rasm yuklash mumkin")
    return contents, ext


def _store_upload(subdir: str, ext: str, contents: bytes, old_rel: Optional[str]) -> str:
    """Faylni tasodifiy (uuid) nom bilan saqlaydi, eskisini o'chiradi -> nisbiy yo'l."""
    rel = f"{subdir}/{uuid4().hex}.{ext}"
    with open(os.path.join(UPLOAD_DIR, rel), "wb") as f:
        f.write(contents)
    if old_rel and old_rel != rel and "/" in old_rel and ".." not in old_rel:
        try:
            os.remove(os.path.join(UPLOAD_DIR, old_rel))
        except OSError:
            pass
    return rel


@app.post("/me/avatar", response_model=schemas.UserRead)
async def upload_avatar(
    file: UploadFile = File(...),
    user: models.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    # Kengaytmani fayl ichidan aniqlaymiz — foydalanuvchi fayl nomiga ISHONMAYMIZ
    # (aks holda .html/.svg yuklab stored-XSS qilish mumkin edi)
    contents, ext = await _read_image_upload(file)
    user.avatar = _store_upload("avatars", ext, contents, user.avatar)
    db.commit()
    db.refresh(user)
    return user


# ── Users endpoints ───────────────────────────────────────────────────────────

@app.get("/users", response_model=List[schemas.UserRead])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    q = db.query(models.User)
    if search:
        q = q.filter(models.User.username.ilike(f"%{search}%") | models.User.full_name.ilike(f"%{search}%"))
    return q.order_by(models.User.id).offset((page - 1) * page_size).limit(page_size).all()


@app.get("/teachers", response_model=List[schemas.UserRead])
def list_teachers(db: Session = Depends(get_db), _: models.User = Depends(require_lms_write)):
    """Guruhga biriktirish uchun o'qituvchilar ro'yxati — metodist, hunter va admin uchun."""
    return (
        db.query(models.User)
        .filter(
            models.User.role.in_([UserRole.teacher.value, UserRole.metodist.value]),
            models.User.is_active == True,  # noqa: E712
        )
        .order_by(models.User.full_name, models.User.username)
        .all()
    )


@app.post("/users", response_model=schemas.UserRead, status_code=201)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Bu username allaqachon mavjud")
    user = models.User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role.value,
        full_name=payload.full_name,
        expires_at=payload.expires_at,
        telegram_chat_id=payload.telegram_chat_id,
    )
    db.add(user)
    db.flush()
    write_audit(db, entity_type="user", entity_id=user.id, action="create",
                changed_by_id=actor.id, new_value={"username": user.username, "role": user.role})
    db.commit()
    db.refresh(user)
    return user


@app.put("/users/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    old = {"role": user.role, "is_active": user.is_active}
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role.value
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.expires_at is not None:
        user.expires_at = payload.expires_at
    if payload.blocked_reason is not None:
        user.blocked_reason = payload.blocked_reason
    if payload.blocked_contact is not None:
        user.blocked_contact = payload.blocked_contact
    if payload.telegram_chat_id is not None:
        user.telegram_chat_id = payload.telegram_chat_id
    if payload.salary is not None:
        user.salary = payload.salary
    write_audit(db, entity_type="user", entity_id=user.id, action="update",
                changed_by_id=actor.id, old_value=old, new_value={"role": user.role, "is_active": user.is_active})
    db.commit()
    db.refresh(user)
    return user


@app.post("/users/{user_id}/block", response_model=schemas.UserRead)
def block_user(user_id: int, payload: schemas.BlockUserRequest, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="O'zingizni bloklolmaysiz")
    user.is_active = False
    user.blocked_reason = payload.reason
    user.blocked_contact = payload.contact
    user.blocked_at = datetime.utcnow()
    write_audit(db, entity_type="user", entity_id=user.id, action="block",
                changed_by_id=actor.id, new_value={"reason": payload.reason, "contact": payload.contact})
    db.commit()
    db.refresh(user)
    return user


@app.post("/users/{user_id}/unblock", response_model=schemas.UserRead)
def unblock_user(user_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    user.is_active = True
    user.blocked_reason = None
    user.blocked_contact = None
    user.blocked_at = None
    write_audit(db, entity_type="user", entity_id=user.id, action="unblock",
                changed_by_id=actor.id, new_value={"is_active": True})
    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}/permanent")
def delete_user_permanent(user_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    """Foydalanuvchini bazadan butunlay o'chirish.

    O'chirishdan oldin userning o'zi va unga bog'liq barcha jadvallardagi
    yozuvlar (to'lov, lid, chegirma va h.k. — kim qilganligi) JSON backup
    faylga saqlanadi, so'ng user qatori butunlay o'chiriladi. Bog'liq
    yozuvlarning o'zi o'chirilmaydi — faqat "kim qildi" bog'lanishi
    tarixiy backup faylda qoladi (users.id qayta ishlatilmaydi, chunki
    autoincrement).
    """
    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="O'zingizni butunlay o'chirolmaysiz")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if user.role == UserRole.admin.value:
        remaining_admins = db.query(models.User).filter(
            models.User.role == UserRole.admin.value, models.User.id != user_id,
        ).count()
        if remaining_admins == 0:
            raise HTTPException(status_code=400, detail="Oxirgi admin akkauntini o'chirib bo'lmaydi")

    user_snapshot = {c.name: getattr(user, c.name) for c in models.User.__table__.columns}

    related_records = {}
    for mapper in models.Base.registry.mappers:
        table = mapper.local_table
        if table is None or table.name == "users":
            continue
        for col in table.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name == "users" and fk.column.name == "id":
                    rows = db.query(table).filter(col == user_id).all()
                    if rows:
                        related_records.setdefault(table.name, []).extend(
                            dict(row._mapping) for row in rows
                        )

    backup_dir = os.path.join(os.path.dirname(__file__), "deleted_users_backup")
    os.makedirs(backup_dir, exist_ok=True)
    backup_filename = f"user_{user_id}_{user.username}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
    with open(os.path.join(backup_dir, backup_filename), "w", encoding="utf-8") as f:
        json.dump(
            {"user": user_snapshot, "related_records": related_records,
             "deleted_by": actor.username, "deleted_at": datetime.utcnow().isoformat()},
            f, ensure_ascii=False, indent=2, default=str,
        )

    write_audit(db, entity_type="user", entity_id=user_id, action="permanent_delete",
                changed_by_id=actor.id,
                old_value={"username": user.username, "role": user.role, "backup_file": backup_filename})
    db.query(models.User).filter(models.User.id == user_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True, "backup_file": backup_filename}


# ── Lessons endpoints ─────────────────────────────────────────────────────────

@app.get("/lessons", response_model=List[schemas.LessonRead])
def list_lessons(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_auth),
):
    q = db.query(models.Lesson)
    if category:
        q = q.filter(models.Lesson.category == category.lower())
    return q.order_by(models.Lesson.lesson_number).all()


@app.get("/lessons/{lesson_id}", response_model=schemas.LessonRead)
def get_lesson(lesson_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    return lesson


@app.post("/lessons", response_model=schemas.LessonRead, status_code=201)
def create_lesson(payload: schemas.LessonCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    if payload.category not in schemas.LESSON_CATEGORIES:
        raise HTTPException(status_code=400, detail="Noto'g'ri kategoriya")
    if db.query(models.Lesson).filter(
        models.Lesson.category == payload.category,
        models.Lesson.lesson_number == payload.lesson_number
    ).first():
        raise HTTPException(status_code=400, detail="Bu kategoriyada ushbu dars raqami allaqachon mavjud")
    lesson = models.Lesson(**payload.dict(), updated_at=datetime.utcnow(), updated_by_id=actor.id)
    db.add(lesson)
    db.flush()
    write_audit(db, entity_type="lesson", entity_id=lesson.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(lesson)
    return lesson


@app.put("/lessons/reorder", response_model=List[schemas.LessonRead])
def reorder_lessons(payload: schemas.ReorderRequest, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    old_order = {}
    lessons_map = {}
    for item in payload.items:
        lesson = db.query(models.Lesson).filter(models.Lesson.id == item.id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail=f"Dars {item.id} topilmadi")
        old_order[item.id] = lesson.lesson_number
        lessons_map[item.id] = (lesson, item.lesson_number)
    OFFSET = 100_000
    now = datetime.utcnow()
    for lesson, _ in lessons_map.values():
        lesson.lesson_number = lesson.lesson_number + OFFSET
    db.flush()
    for lesson, new_num in lessons_map.values():
        lesson.lesson_number = new_num
        lesson.updated_at = now
        lesson.updated_by_id = actor.id
    write_audit(db, entity_type="lesson", entity_id=None, action="reorder",
                changed_by_id=actor.id,
                old_value={str(k): v for k, v in old_order.items()},
                new_value={str(i.id): i.lesson_number for i in payload.items})
    db.commit()
    updated = [lessons_map[item.id][0] for item in payload.items]
    for lesson in updated:
        db.refresh(lesson)
    return updated


@app.put("/lessons/{lesson_id}", response_model=schemas.LessonRead)
def update_lesson(lesson_id: int, payload: schemas.LessonUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    changes = payload.dict(exclude_unset=True)
    old_value = {k: getattr(lesson, k) for k in changes}
    for field, value in changes.items():
        setattr(lesson, field, value)
    lesson.updated_at = datetime.utcnow()
    lesson.updated_by_id = actor.id
    write_audit(db, entity_type="lesson", entity_id=lesson.id, action="update",
                changed_by_id=actor.id, old_value=old_value, new_value=changes)
    db.commit()
    db.refresh(lesson)
    return lesson


@app.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    write_audit(db, entity_type="lesson", entity_id=lesson_id, action="delete",
                changed_by_id=actor.id, old_value={"title": lesson.title})
    db.delete(lesson)
    db.commit()


# ── Audit log endpoints ───────────────────────────────────────────────────────

@app.get("/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    q = db.query(models.AuditLog).order_by(models.AuditLog.changed_at.desc())
    if date_from:
        q = q.filter(models.AuditLog.changed_at >= tz.day_bounds(date_from)[0])
    if date_to:
        q = q.filter(models.AuditLog.changed_at < tz.day_bounds(date_to)[1])
    total = q.count()
    logs = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [schemas.AuditLogRead.from_orm(l) for l in logs],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    }


@app.get("/audit-logs/lesson/{lesson_id}", response_model=List[schemas.AuditLogRead])
def lesson_audit_logs(lesson_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    return (db.query(models.AuditLog)
            .filter(models.AuditLog.entity_type == "lesson", models.AuditLog.entity_id == lesson_id)
            .order_by(models.AuditLog.changed_at.desc()).all())


# ── Tariffs endpoints ─────────────────────────────────────────────────────────

@app.get("/tariffs", response_model=List[schemas.TariffRead])
def list_tariffs(db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    return db.query(models.Tariff).order_by(models.Tariff.name).all()


@app.post("/tariffs", response_model=schemas.TariffRead, status_code=201)
def create_tariff(payload: schemas.TariffCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_hunter)):
    t = models.Tariff(**payload.dict())
    db.add(t)
    db.flush()
    write_audit(db, entity_type="tariff", entity_id=t.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(t)
    return t


@app.put("/tariffs/{tariff_id}", response_model=schemas.TariffRead)
def update_tariff(tariff_id: int, payload: schemas.TariffUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_hunter)):
    t = db.query(models.Tariff).filter(models.Tariff.id == tariff_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarif topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(t, k)) for k in changes}
    for k, v in changes.items():
        setattr(t, k, v)
    write_audit(db, entity_type="tariff", entity_id=t.id, action="update",
                changed_by_id=actor.id, old_value=old, new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(t)
    return t


@app.delete("/tariffs/{tariff_id}", status_code=204)
def delete_tariff(tariff_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_hunter)):
    t = db.query(models.Tariff).filter(models.Tariff.id == tariff_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarif topilmadi")
    if db.query(models.GroupStudent).filter(models.GroupStudent.tariff_id == tariff_id).first():
        raise HTTPException(status_code=400, detail="Bu tarifdan foydalanayotgan talabalar mavjud")
    write_audit(db, entity_type="tariff", entity_id=t.id, action="delete",
                changed_by_id=actor.id, old_value={"name": t.name, "price": str(t.price)})
    db.delete(t)
    db.commit()


# ── Courses endpoints ─────────────────────────────────────────────────────────

@app.get("/courses", response_model=List[schemas.CourseRead])
def list_courses(db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    return db.query(models.Course).order_by(models.Course.name).all()


@app.post("/courses", response_model=schemas.CourseRead, status_code=201)
def create_course(payload: schemas.CourseCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    c = models.Course(**payload.dict())
    db.add(c)
    db.flush()
    write_audit(db, entity_type="course", entity_id=c.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(c)
    return c


@app.put("/courses/{course_id}", response_model=schemas.CourseRead)
def update_course(course_id: int, payload: schemas.CourseUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    c = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Kurs topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(c, k)) for k in changes}
    for k, v in changes.items():
        setattr(c, k, v)
    write_audit(db, entity_type="course", entity_id=c.id, action="update",
                changed_by_id=actor.id, old_value=old, new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(c)
    return c


@app.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    c = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Kurs topilmadi")
    if db.query(models.Group).filter(models.Group.course_id == course_id).first():
        raise HTTPException(status_code=400, detail="Bu kursga bog'liq guruhlar mavjud")
    write_audit(db, entity_type="course", entity_id=c.id, action="delete",
                changed_by_id=actor.id, old_value={"name": c.name})
    db.delete(c)
    db.commit()


# ── Students endpoints ────────────────────────────────────────────────────────

def _student_owed_total(db: Session, s: models.Student, month: int = None, year: int = None,
                        discounts: list = None, vacations: list = None) -> Decimal:
    """Talabaning oylik to'liq summasi — faol guruhlar bo'yicha (tarif yoki guruh narxi).
    _student_month_owed bilan bir xil mantiq — ta'til va Special chegirmalar qo'llanadi."""
    total = Decimal(0)
    active_group_ids = {m.group.id for m in s.group_memberships
                        if m.group and m.group.is_active and m.left_at is None}
    primary_group_id = min(active_group_ids) if active_group_ids else None
    for m in s.group_memberships:
        g = m.group
        if not g:
            continue
        if month is not None and year is not None:
            if not core_calc.group_billable_in(g, month, year):
                continue  # guruh so'ralgan oydan oldin arxivlangan
        elif not g.is_active:
            continue
        # Talaba shu (oy,yil)da haqiqatan shu guruh a'zosi bo'lganmi (keyinroq
        # boshqa guruhga o'tkazilgan/chiqarilgan bo'lsa, endi eski a'zolik
        # yozuvi o'chirilmaydi — shuning uchun bu tekshiruv shart, aks holda
        # allaqachon tark etilgan guruh uchun ham qarz hisoblanaveradi).
        if month is not None and year is not None:
            if not core_calc.bills_month(m, month, year):
                continue
        elif m.left_at is not None:
            continue
        if g.start_date:
            if month is not None and year is not None:
                if (g.start_date.year, g.start_date.month) > (year, month):
                    continue  # guruh so'ralgan oyda hali boshlanmagan edi
            elif g.start_date.date() > tz.today():
                continue  # guruh hali boshlanmagan — talaba hali qarzdor emas
        if m.tariff:
            price = Decimal(str(m.tariff.price))
        elif g.course_price and Decimal(str(g.course_price)) > 0:
            price = Decimal(str(g.course_price))
        else:
            continue
        if vacations:
            price = core_calc.apply_vacations_to_price(db, s.id, g, month, year, price, vacations)
        if discounts:
            apply_global = primary_group_id is None or primary_group_id == g.id
            price = core_calc.apply_special_discounts(price, discounts, g.id, month, year,
                                                       apply_global=apply_global,
                                                       active_group_ids=active_group_ids)
        total += price
    return total.quantize(Decimal('1'))


def _students_payment_map(db: Session, students, month: int, year: int) -> dict:
    """Har talaba uchun (owed, paid, debt, status, balance) — bir marta agregat so'rov bilan.

    `owed`/`paid` — shu OYNING narxi/to'lovi (ma'lumot uchun, guruh narxini ko'rsatadi).
    `debt`/`status`/`balance` — JAMLANGAN (kumulyativ) hisob: ro'yxatdan o'tgandan
    bugungacha jami qarz vs jami to'lov. Bitta oyda ortiqcha to'langan summa
    boshqa oydagi qarzni avtomatik yopadi (`core_calc.student_cumulative_balance`)."""
    ids = [s.id for s in students]
    paid_by = {}
    total_paid_by = {}
    discounts_by = {}
    vacations_by = {}
    if ids:
        rows = (
            db.query(models.Payment.student_id, func.sum(models.Payment.amount))
            .filter(models.Payment.student_id.in_(ids),
                    models.Payment.month == month, models.Payment.year == year)
            .group_by(models.Payment.student_id).all()
        )
        paid_by = {sid: Decimal(str(amt or 0)) for sid, amt in rows}
        total_rows = (
            db.query(models.Payment.student_id, func.sum(models.Payment.amount))
            .filter(models.Payment.student_id.in_(ids))
            .group_by(models.Payment.student_id).all()
        )
        total_paid_by = {sid: Decimal(str(amt or 0)) for sid, amt in total_rows}
        # Special chegirmalar — bitta so'rovda
        for d in db.query(models.SpecialDiscount).filter(
            models.SpecialDiscount.student_id.in_(ids),
            models.SpecialDiscount.is_active == True,
        ).all():
            discounts_by.setdefault(d.student_id, []).append(d)
        # Ta'til oraliqlari — bitta so'rovda
        for v in db.query(models.StudentVacation).filter(
            models.StudentVacation.student_id.in_(ids),
        ).all():
            vacations_by.setdefault(v.student_id, []).append(v)
    out = {}
    for s in students:
        owed = _student_owed_total(db, s, month, year, discounts_by.get(s.id), vacations_by.get(s.id))
        paid = paid_by.get(s.id, Decimal(0))
        cum_owed = core_calc.student_cumulative_owed(
            db, s, upto_year=year, upto_month=month,
            discounts=discounts_by.get(s.id, []), vacations=vacations_by.get(s.id, []),
        )
        cum_paid = total_paid_by.get(s.id, Decimal(0)) + Decimal(str(s.advance_balance or 0))
        balance = cum_paid - cum_owed
        debt = max(Decimal(0), -balance)
        advance_applied = max(Decimal(0), balance)
        if cum_owed <= 0:
            status = "none"
        elif debt <= 0:
            status = "paid"
        else:
            status = "debtor"
        out[s.id] = (owed, paid, debt, status, advance_applied)
    return out


def _student_read(s: models.Student, pay: Optional[tuple] = None) -> schemas.StudentRead:
    owed = paid = debt = pstatus = advance_applied = None
    if pay is not None:
        owed, paid, debt, pstatus, advance_applied = pay
    return schemas.StudentRead(
        id=s.id, full_name=s.full_name, phone1=s.phone1,
        father_name=s.father_name, father_phone=s.father_phone,
        mother_name=s.mother_name, mother_phone=s.mother_phone,
        telegram_id=s.telegram_id, telegram_user_id=s.telegram_user_id,
        photo=uploads_sign.sign(s.photo), notes=s.notes, is_active=s.is_active,
        is_archived=s.is_archived, is_demo=s.is_demo, advance_balance=s.advance_balance,
        sales_credited=s.sales_credited_at is not None,
        created_at=s.created_at, updated_at=s.updated_at,
        group_count=sum(1 for m in s.group_memberships if m.left_at is None),
        group_names=[m.group.name for m in s.group_memberships if m.group and m.left_at is None],
        owed_month=owed, paid_month=paid, debt=debt, payment_status=pstatus,
        advance_applied=advance_applied,
        photo_url=f"/uploads/{uploads_sign.sign(s.photo_path)}" if s.photo_path else None,
    )


@app.get("/students")
def list_students(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_archived: Optional[bool] = Query(None),
    is_demo: Optional[bool] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    payment: Optional[str] = Query(None, description="debtor | partial | paid | unpaid"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_lms_write),
):
    now = tz.now()  # joriy oy — Toshkent vaqti bo'yicha
    month = month or now.month
    year = year or now.year

    q = db.query(models.Student).options(
        joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.tariff),
        joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.group),
    )
    # by default exclude archived unless explicitly requested
    if is_archived is None:
        q = q.filter(models.Student.is_archived == False)
    else:
        q = q.filter(models.Student.is_archived == is_archived)
    if is_active is not None:
        q = q.filter(models.Student.is_active == is_active)
    # by default exclude demo (hali demo darsga kelmagan) unless explicitly requested
    if is_demo is None:
        q = q.filter(models.Student.is_demo == False)
    else:
        q = q.filter(models.Student.is_demo == is_demo)
    if search:
        q = q.filter(
            models.Student.full_name.ilike(f"%{search}%") |
            models.Student.phone1.ilike(f"%{search}%") |
            models.Student.father_phone.ilike(f"%{search}%") |
            models.Student.mother_phone.ilike(f"%{search}%")
        )
    if date_from:
        q = q.filter(models.Student.created_at >= tz.day_bounds(date_from)[0])
    if date_to:
        q = q.filter(models.Student.created_at < tz.day_bounds(date_to)[1])
    q = q.order_by(models.Student.full_name)

    if payment:
        # To'lov holati bo'yicha filtr — butun to'plamni hisoblab, keyin sahifalash
        alls = q.all()
        pmap = _students_payment_map(db, alls, month, year)
        want = {"unpaid": {"debtor", "partial"}}.get(payment, {payment})
        filtered = [s for s in alls if pmap[s.id][3] in want]
        total = len(filtered)
        students = filtered[(page - 1) * page_size: page * page_size]
        page_map = pmap
    else:
        total = q.count()
        students = q.offset((page - 1) * page_size).limit(page_size).all()
        page_map = _students_payment_map(db, students, month, year)

    return {
        "items": [_student_read(s, page_map.get(s.id)) for s in students],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "month": month,
            "year": year,
        }
    }


@app.get("/students/{student_id}", response_model=schemas.StudentRead)
def get_student(student_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_lms_write)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    return _student_read(s)


@app.post("/students", response_model=schemas.StudentRead, status_code=201)
def create_student(payload: schemas.StudentCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    data = payload.dict()
    advance = data.pop("advance", 0) or 0
    s = models.Student(**data, advance_balance=advance)
    db.add(s)
    db.flush()
    write_audit(db, entity_type="student", entity_id=s.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(s)
    return _student_read(s)


@app.put("/students/{student_id}", response_model=schemas.StudentRead)
def update_student(student_id: int, payload: schemas.StudentUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    changes = payload.dict(exclude_unset=True)
    if changes.get("is_demo") and not s.is_demo:
        if any(m.group and m.group.is_active and m.left_at is None for m in s.group_memberships):
            raise HTTPException(status_code=400, detail="Aktiv guruhda o'qiyotgan talabani Demo bo'limiga o'tkazib bo'lmaydi")
    if "advance_balance" in changes and actor.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Avans balansini faqat admin o'zgartira oladi")
    for k, v in changes.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return _student_read(s)


@app.post("/students/{student_id}/telegram-check")
def check_student_telegram(student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    """Talabaning Telegram ID'siga sinov xabari yuborib, yetkazib bo'lish mumkinligini tekshiradi."""
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    if not s.telegram_user_id:
        raise HTTPException(status_code=400, detail="Talabaga Telegram ID biriktirilmagan")
    ok, err = send_telegram_message(s.telegram_user_id, "Assalomu alaykum")
    return {"ok": ok, "detail": err}


@app.post("/students/{student_id}/archive", response_model=schemas.StudentRead)
def archive_student(student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    s.is_archived = True
    s.is_active = False
    db.commit()
    db.refresh(s)
    write_audit(db, entity_type="student", entity_id=s.id, action="archive",
                changed_by_id=actor.id, new_value={"is_archived": True})
    db.commit()
    return _student_read(s)


@app.post("/students/{student_id}/unarchive", response_model=schemas.StudentRead)
def unarchive_student(student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    s.is_archived = False
    s.is_active = True
    db.commit()
    db.refresh(s)
    write_audit(db, entity_type="student", entity_id=s.id, action="unarchive",
                changed_by_id=actor.id, new_value={"is_archived": False})
    db.commit()
    return _student_read(s)


# ── Groups endpoints ──────────────────────────────────────────────────────────

def _group_read(g: models.Group, db: Session = None) -> schemas.GroupRead:
    stage = g.stage or 'foundation'
    total = g.course.total_lessons if g.course else schemas.STAGE_TOTAL_LESSONS.get(stage, 24)
    completed = 0
    if db is not None:
        completed = core_calc.group_completed_lessons(db, [g.id]).get(g.id, 0)
    remaining = max(0, total - completed)
    pct = round(completed / total * 100, 1) if total > 0 else 0.0
    return schemas.GroupRead(
        id=g.id, name=g.name, stage=stage,
        course_id=g.course_id, course_name=g.course.name if g.course else None,
        teacher_id=g.teacher_id,
        teacher_name=g.teacher.full_name or g.teacher.username if g.teacher else None,
        course_price=g.course_price, schedule=g.schedule, lesson_time=g.lesson_time,
        start_date=g.start_date, is_active=g.is_active,
        telegram_chat_id=g.telegram_chat_id,
        created_at=g.created_at, student_count=sum(1 for m in g.members if m.left_at is None),
        total_lessons=total, completed_lessons=completed,
        remaining_lessons=remaining, progress_pct=pct,
    )


def _group_detail(g: models.Group, db: Session = None) -> schemas.GroupDetail:
    members = [
        schemas.GroupStudentRead(
            id=m.id, student_id=m.student_id,
            student_name=m.student.full_name,
            student_phone=m.student.phone1,
            joined_at=m.joined_at,
            tariff_id=m.tariff_id,
            tariff_name=m.tariff.name if m.tariff else None,
            tariff_price=m.tariff.price if m.tariff else None,
        ) for m in g.members if m.left_at is None
    ]
    base = _group_read(g, db=db)
    return schemas.GroupDetail(**base.dict(), members=members)


@app.get("/groups")
def list_groups(
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    schedule: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_lms_write),
):
    q = db.query(models.Group)
    if is_active is not None:
        q = q.filter(models.Group.is_active == is_active)
    if search:
        q = q.filter(models.Group.name.ilike(f"%{search}%"))
    if schedule:
        q = q.filter(models.Group.schedule == schedule)
    if date_from:
        q = q.filter(models.Group.start_date >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to:
        q = q.filter(models.Group.start_date < datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1))
    total = q.count()
    order_by = (
        (func.coalesce(models.Group.lesson_time, '99:99'), models.Group.name)
        if schedule else
        (models.Group.name,)
    )
    groups = (
        q.options(
            joinedload(models.Group.teacher),
            joinedload(models.Group.course),
            selectinload(models.Group.members),
        )
        .order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_group_read(g, db=db) for g in groups],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    }


@app.get("/groups/{group_id}", response_model=schemas.GroupDetail)
def get_group(group_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_auth)):
    g = (
        db.query(models.Group)
        .options(
            joinedload(models.Group.teacher),
            joinedload(models.Group.course),
            selectinload(models.Group.members).joinedload(models.GroupStudent.student),
            selectinload(models.Group.members).joinedload(models.GroupStudent.tariff),
        )
        .filter(models.Group.id == group_id)
        .first()
    )
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    # Teacher faqat o'z guruhini ko'ra oladi
    if actor.role == UserRole.teacher.value and g.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")
    return _group_detail(g, db=db)


@app.post("/groups", response_model=schemas.GroupRead, status_code=201)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    data = payload.dict()
    data.setdefault('stage', 'foundation')
    g = models.Group(**data)
    db.add(g)
    db.flush()
    write_audit(db, entity_type="group", entity_id=g.id, action="create",
                changed_by_id=actor.id, new_value=data)
    db.commit()
    db.refresh(g)
    return _group_read(g, db=db)


@app.put("/groups/{group_id}", response_model=schemas.GroupRead)
def update_group(group_id: int, payload: schemas.GroupUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(g, k)) for k in changes}
    if "is_active" in changes and changes["is_active"] != g.is_active:
        # Arxivlash sanasi — qarz hisobi shu oygacha davom etadi (core_calc.group_billable_in)
        g.closed_at = None if changes["is_active"] else datetime.utcnow()
    for k, v in changes.items():
        setattr(g, k, v)
    write_audit(db, entity_type="group", entity_id=g.id, action="update",
                changed_by_id=actor.id, old_value=old,
                new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(g)
    return _group_read(g, db=db)


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    db.delete(g)
    db.commit()


@app.post("/groups/{group_id}/students", status_code=201)
def add_student_to_group(group_id: int, payload: schemas.AddStudentToGroup, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    s = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    exists = db.query(models.GroupStudent).filter(
        models.GroupStudent.group_id == group_id,
        models.GroupStudent.student_id == payload.student_id,
        models.GroupStudent.left_at.is_(None),
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Talaba bu guruhda allaqachon mavjud")
    tariff_id = payload.tariff_id
    tariff_name = None
    if tariff_id:
        tariff = db.query(models.Tariff).filter(models.Tariff.id == tariff_id).first()
        if not tariff:
            raise HTTPException(status_code=404, detail="Tarif topilmadi")
        tariff_name = tariff.name
    elif g.course_price and g.course_price > 0:
        # Auto-assign a tariff matching the group's course_price
        matched = db.query(models.Tariff).filter(
            models.Tariff.price == g.course_price,
            models.Tariff.is_active == True,
        ).first()
        tariff_id = matched.id if matched else None
        tariff_name = matched.name if matched else None
    gs = models.GroupStudent(group_id=group_id, student_id=payload.student_id, tariff_id=tariff_id)
    db.add(gs)
    if s.is_demo:
        s.is_demo = False
    db.commit()
    notify_investor_new_student(s.full_name, g.name, tariff_name)
    return {"message": "Talaba guruhga qo'shildi"}


@app.delete("/groups/{group_id}/students/{student_id}", status_code=204)
def remove_student_from_group(group_id: int, student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    gs = db.query(models.GroupStudent).filter(
        models.GroupStudent.group_id == group_id,
        models.GroupStudent.student_id == student_id,
        models.GroupStudent.left_at.is_(None),
    ).first()
    if not gs:
        raise HTTPException(status_code=404, detail="Topilmadi")
    # Qator o'CHIRILMAYDI — shunchaki "tark etgan" deb belgilanadi, shunda
    # o'sha davrdagi qarz/to'lov tarixi (core_calc, _finance_month) saqlanib qoladi.
    gs.left_at = datetime.utcnow()
    db.commit()


# ── Payments endpoints ────────────────────────────────────────────────────────

# To'lov hisobi core_calc.py da (yagona manba) — bu yerda faqat delegatsiya.
_student_month_owed = core_calc.student_month_owed
_student_month_paid = core_calc.student_month_paid


def _payment_read(p: models.Payment, db: Optional[Session] = None) -> schemas.PaymentRead:
    expected = paid_total = remaining = None
    status = None
    if db is not None:
        expected = _student_month_owed(db, p.student_id, p.group_id, p.month, p.year)
        paid_total = _student_month_paid(db, p.student_id, p.group_id, p.month, p.year)
        if expected and expected > 0:
            remaining = max(Decimal(0), expected - paid_total)
            status = "paid" if paid_total >= expected else "partial"
    return schemas.PaymentRead(
        id=p.id, student_id=p.student_id,
        student_name=p.student.full_name if p.student else None,
        group_id=p.group_id,
        group_name=p.group.name if p.group else None,
        amount=p.amount, month=p.month, year=p.year,
        paid_at=p.paid_at, notes=p.notes,
        recorded_by_name=(p.recorded_by.full_name or p.recorded_by.username) if p.recorded_by else None,
        via_sales=p.via_sales,
        expected=expected, paid_total=paid_total, remaining=remaining, status=status,
    )


@app.get("/payments/expected")
def payment_expected(
    student_id: int = Query(...),
    group_id: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_crm_access),
):
    """Talabaning shu oy uchun to'liq summasi, to'langani va qolgani."""
    expected = _student_month_owed(db, student_id, group_id, month, year)
    paid = _student_month_paid(db, student_id, group_id, month, year)
    remaining = max(Decimal(0), expected - paid) if expected > 0 else Decimal(0)
    return {
        "expected": float(expected),
        "paid": float(paid),
        "remaining": float(remaining),
    }


@app.get("/students/{student_id}/payments/summary", response_model=schemas.StudentPaymentSummary)
def student_payment_summary(
    student_id: int,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_crm_access),
):
    """Talabaning joriy oy uchun to'lov xulosasi — guruhlar kesimida qarz, avans va so'nggi to'lovlar."""
    now = tz.now()  # joriy oy — Toshkent vaqti bo'yicha
    month, year = month or now.month, year or now.year

    s = (
        db.query(models.Student)
        .options(
            joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.group),
            joinedload(models.Student.group_memberships).joinedload(models.GroupStudent.tariff),
        )
        .filter(models.Student.id == student_id).first()
    )
    if not s:
        raise HTTPException(404, "Talaba topilmadi")

    groups: list[schemas.StudentGroupFee] = []
    total_owed = total_paid = Decimal(0)
    for m in s.group_memberships:
        g = m.group
        if not g or not core_calc.group_billable_in(g, month, year):
            continue
        if not core_calc.covers_month(m, month, year):
            continue  # talaba so'ralgan oyda shu guruh a'zosi bo'lmagan (boshqa guruhga o'tgan/chiqarilgan)
        owed = _student_month_owed(db, s.id, g.id, month, year)
        paid = _student_month_paid(db, s.id, g.id, month, year)
        total_owed += owed
        total_paid += paid
        groups.append(schemas.StudentGroupFee(
            group_id=g.id, group_name=g.name, owed=owed, paid=paid,
            remaining=max(Decimal(0), owed - paid),
        ))

    # debt/status/advance_balance — JAMLANGAN (kumulyativ) hisob: bitta oyda ortiqcha
    # to'langan summa boshqa oydagi qarzni avtomatik yopadi (yagona manba, Payments.jsx
    # bilan bir xil natija ko'rsatishi uchun `core_calc.student_cumulative_balance`).
    cum_owed = core_calc.student_cumulative_owed(db, s, upto_year=year, upto_month=month)
    balance = core_calc.student_cumulative_balance(db, s, upto_year=year, upto_month=month)
    debt = max(Decimal(0), -balance)
    advance_display = max(Decimal(0), balance)
    if cum_owed <= 0:
        status = "none"
    elif debt <= 0:
        status = "paid"
    else:
        status = "debtor"

    recent = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.group),
            joinedload(models.Payment.student),
            joinedload(models.Payment.recorded_by),
        )
        .filter(models.Payment.student_id == student_id)
        .order_by(models.Payment.paid_at.desc()).limit(10).all()
    )
    return schemas.StudentPaymentSummary(
        student_id=s.id, student_name=s.full_name, month=month, year=year,
        advance_balance=advance_display, total_owed=total_owed, total_paid=total_paid,
        debt=debt, payment_status=status, groups=groups,
        recent_payments=[_payment_read(p, db) for p in recent],
    )


@app.get("/payments")
def list_payments(
    student_id: Optional[int] = Query(None),
    group_id: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_crm_access),
):
    q = db.query(models.Payment)
    if student_id:
        q = q.filter(models.Payment.student_id == student_id)
    if group_id:
        q = q.filter(models.Payment.group_id == group_id)
    if month:
        q = q.filter(models.Payment.month == month)
    if year:
        q = q.filter(models.Payment.year == year)
    if date_from:
        q = q.filter(models.Payment.paid_at >= tz.day_bounds(date_from)[0])
    if date_to:
        q = q.filter(models.Payment.paid_at < tz.day_bounds(date_to)[1])
    total = q.count()
    payments = q.order_by(models.Payment.paid_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_payment_read(p, db) for p in payments],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    }


def _credit_sales_payment(db: Session, student_id: int, actor: models.User) -> None:
    """"Sales" belgisi qo'yilganda kredit beriladi: to'lovni yozayotgan xodim
    o'zi sales bo'lsa — o'ziga, aks holda birinchi faol sales xodimiga.
    Atomic UPDATE (WHERE sales_credited_at IS NULL) — ikkita parallel so'rov
    bir xil talabani ikki marta kredit qilib yubormasligi uchun."""
    credited_user_id = actor.id if actor.role == UserRole.sales.value else None
    if not credited_user_id:
        sales_user = (
            db.query(models.User)
            .filter(models.User.role == UserRole.sales.value, models.User.is_active == True)  # noqa: E712
            .order_by(models.User.id)
            .first()
        )
        credited_user_id = sales_user.id if sales_user else None
    if not credited_user_id:
        return
    updated = (
        db.query(models.Student)
        .filter(models.Student.id == student_id, models.Student.sales_credited_at.is_(None))
        .update({"sales_credited_at": datetime.utcnow(), "sales_credited_by_id": credited_user_id},
                synchronize_session=False)
    )
    if updated:
        _bump_referral_stat(db, credited_user_id, paid_delta=1)


def _reverse_sales_credit_if_orphaned(db: Session, student_id: int) -> None:
    """To'lov o'chirilganda: agar bu talabaning boshqa via_sales to'lovi
    qolmagan bo'lsa, berilgan kredit qaytariladi — aks holda xodim keyinchalik
    to'g'ri to'lov yozilganda qayta kredit ololmay qoladi (flag abadiy band)."""
    still_has_sales_payment = (
        db.query(models.Payment)
        .filter(models.Payment.student_id == student_id, models.Payment.via_sales == True)  # noqa: E712
        .first()
    )
    if still_has_sales_payment:
        return
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if student and student.sales_credited_by_id:
        _bump_referral_stat(db, student.sales_credited_by_id, paid_delta=-1)
        student.sales_credited_at = None
        student.sales_credited_by_id = None


@app.post("/payments", response_model=schemas.PaymentRead, status_code=201)
def create_payment(payload: schemas.PaymentCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_crm_access)):
    student = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    group = db.query(models.Group).filter(models.Group.id == payload.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    is_member = (
        db.query(models.GroupStudent)
        .filter(models.GroupStudent.student_id == payload.student_id,
                models.GroupStudent.group_id == payload.group_id)
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=400, detail="Talaba shu guruhga biriktirilmagan")

    p = models.Payment(**payload.dict(), paid_at=datetime.utcnow(), recorded_by_id=actor.id)
    db.add(p)
    db.flush()
    write_audit(db, entity_type="payment", entity_id=p.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    # "Sales" tugmasi bosilgan bo'lsa — sales rolidagi xodimga har talaba uchun
    # FAQAT BIR MARTA (referral tizimidagi kabi) paid_count +1 qo'shiladi.
    if payload.via_sales:
        _credit_sales_payment(db, payload.student_id, actor)
    # Ota-onalarga bildirishnoma
    _amount = int(Decimal(str(payload.amount)))
    notify_parents_of_student(
        db, student_id=payload.student_id, ntype="payment",
        title="To'lov qabul qilindi",
        body=f"{_amount:,} so'm to'lov qabul qilindi".replace(",", " "),
    )
    db.commit()
    db.refresh(p)
    return _payment_read(p, db)


@app.put("/payments/{payment_id}", response_model=schemas.PaymentRead)
def update_payment(payment_id: int, payload: schemas.PaymentUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    p = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(p, k)) for k in changes}
    for k, v in changes.items():
        setattr(p, k, v)
    write_audit(db, entity_type="payment", entity_id=p.id, action="update",
                changed_by_id=actor.id, old_value=old,
                new_value={k: str(v) for k, v in changes.items()})
    # To'lab bo'lingan (bo'lib-bo'lib to'lagan) talabalar uchun ham "Sales"
    # belgisi keyinroq tahrirlanishi mumkin — create'dagi kabi FAQAT BIR MARTA hisoblanadi.
    if changes.get("via_sales"):
        _credit_sales_payment(db, p.student_id, actor)
    elif changes.get("via_sales") is False:
        _reverse_sales_credit_if_orphaned(db, p.student_id)
    db.commit()
    db.refresh(p)
    return _payment_read(p, db)


@app.delete("/payments/{payment_id}", status_code=204)
def delete_payment(payment_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    p = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    write_audit(db, entity_type="payment", entity_id=p.id, action="delete",
                changed_by_id=actor.id,
                old_value={"student_id": p.student_id, "group_id": p.group_id,
                           "amount": str(p.amount), "month": p.month, "year": p.year})
    was_sales = bool(p.via_sales)
    student_id = p.student_id
    db.delete(p)
    db.flush()
    if was_sales:
        _reverse_sales_credit_if_orphaned(db, student_id)
    db.commit()


# ── Salary helper ─────────────────────────────────────────────────────────────

def _group_salary(db: Session, group: models.Group, month: int, year: int):
    """
    O'qituvchi maoshini hisoblaydi — bitta manba (`_teacher_salary_breakdown`
    bilan bir xil formula): 50 000 so'm / shu oyda o'tilgan darslar soni ×
    talaba kelgan darslar soni. Qaytaradi: (jami summa, talabalar ro'yxati,
    shu oyda o'tilgan darslar soni).
    """
    lessons_held = db.query(
        func.count(func.distinct(models.Attendance.lesson_date))
    ).filter(
        models.Attendance.group_id == group.id,
        extract('month', models.Attendance.lesson_date) == month,
        extract('year', models.Attendance.lesson_date) == year,
    ).scalar() or 0
    if lessons_held <= 0:
        return Decimal(0), [], 0

    # 1-query: guruh a'zolari va ismlari — shu OY davomida haqiqatan a'zo
    # bo'lganlar (keyinroq chiqarilgan/o'tkazilgan bo'lsa ham, ko'ring: left_at).
    all_members = (
        db.query(models.GroupStudent, models.Student.full_name)
        .join(models.Student, models.Student.id == models.GroupStudent.student_id)
        .filter(models.GroupStudent.group_id == group.id)
        .order_by(models.GroupStudent.id)
        .all()
    )
    member_rows = [(gs, name) for gs, name in all_members if core_calc.covers_month(gs, month, year)]
    if not member_rows:
        return Decimal(0), [], lessons_held

    student_ids = [gs.student_id for gs, _ in member_rows]
    name_map    = {gs.student_id: name for gs, name in member_rows}

    # 2-query: bir oyda har talaba uchun kelgan darslar soni (GROUP BY)
    att_rows = (
        db.query(
            models.Attendance.student_id,
            func.count(models.Attendance.id).label('cnt'),
        )
        .filter(
            models.Attendance.group_id  == group.id,
            models.Attendance.is_present == True,
            extract('month', models.Attendance.lesson_date) == month,
            extract('year',  models.Attendance.lesson_date) == year,
            models.Attendance.student_id.in_(student_ids),
        )
        .group_by(models.Attendance.student_id)
        .all()
    )
    attended_map = {r.student_id: r.cnt for r in att_rows}

    per_lesson = TEACHER_STUDENT_BONUS_UNIT / Decimal(lessons_held)
    total    = Decimal(0)
    students = []
    for sid, sname in name_map.items():
        attended = attended_map.get(sid, 0)
        share    = (per_lesson * Decimal(str(attended))).quantize(Decimal('1'))
        total   += share
        students.append({
            "student_id":   sid,
            "student_name": sname,
            "attended":     attended,
            "salary_share": float(share),
        })
    return total, students, lessons_held


def _batch_salary_by_month(db: Session, groups: list, year: int) -> dict:
    """
    Barcha guruhlar uchun 12 oylik maoshni ("talaba ulushi" formulasi bilan,
    `_teacher_salary_breakdown` bilan bir xil) 2 query da hisoblaydi.
    Qaytaradi: {month: total_salary}
    """
    taught = [g for g in groups if g.teacher_id]
    result = {m: Decimal(0) for m in range(1, 13)}
    if not taught:
        return result

    group_ids = [g.id for g in taught]

    # Har (oy, guruh) uchun shu oyda o'tilgan darslar soni
    held_rows = (
        db.query(
            extract('month', models.Attendance.lesson_date).label('mon'),
            models.Attendance.group_id,
            func.count(func.distinct(models.Attendance.lesson_date)).label('cnt'),
        )
        .filter(
            models.Attendance.group_id.in_(group_ids),
            extract('year', models.Attendance.lesson_date) == year,
        )
        .group_by(extract('month', models.Attendance.lesson_date), models.Attendance.group_id)
        .all()
    )
    held_map = {(int(r.mon), r.group_id): r.cnt for r in held_rows}

    rows = (
        db.query(
            extract('month', models.Attendance.lesson_date).label('mon'),
            models.Attendance.group_id,
            models.Attendance.student_id,
            func.count(models.Attendance.id).label('cnt'),
        )
        .filter(
            models.Attendance.group_id.in_(group_ids),
            models.Attendance.is_present == True,
            extract('year', models.Attendance.lesson_date) == year,
        )
        .group_by(
            extract('month', models.Attendance.lesson_date),
            models.Attendance.group_id,
            models.Attendance.student_id,
        )
        .all()
    )
    for row in rows:
        held = held_map.get((int(row.mon), row.group_id), 0)
        if held <= 0:
            continue
        per_lesson = TEACHER_STUDENT_BONUS_UNIT / Decimal(held)
        result[int(row.mon)] += (per_lesson * Decimal(str(row.cnt))).quantize(Decimal('1'))
    return result


# ── Statistics endpoints ──────────────────────────────────────────────────────

@app.get("/stats/student-growth")
def stats_student_growth(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """
    Oylik o'quvchi o'sishi — dashboard uchun.

    Nima uchun alohida endpoint: /stats/overview faqat JORIY holatni beradi
    ("hozir 240 talaba bor"), lekin boshqaruv uchun muhim savol — "o'sayapmizmi
    yoki qisqaryapmizmi". Buni frontendda hisoblash uchun butun talaba bazasini
    yuklab olish kerak bo'lardi; bu yerda esa bitta guruhlangan so'rov.

    Har oy uchun:
      • joined   — shu oyda ro'yxatdan o'tgan talabalar
      • archived — shu oyda arxivlanganlar (chiqib ketganlar)
      • active   — oy oxiriga qadar faol bo'lgan talabalar (kumulyativ)
    """
    sel_year = year or tz.today().year

    # extract() — SQLite'da ham, PostgreSQL'da ham ishlaydi (strftime faqat SQLite'da bor)
    year_expr = extract('year', models.Student.created_at)
    month_expr = extract('month', models.Student.created_at)
    rows = (
        db.query(month_expr.label('m'), func.count(models.Student.id))
        .filter(year_expr == sel_year)
        .group_by(month_expr)
        .all()
    )
    joined_by_month = {int(m): c for m, c in rows if m}

    # Arxivlanganlar: arxiv sanasi alohida saqlanmaydi, shuning uchun faqat
    # umumiy arxiv soni beriladi — oylik taqsimotni soxta ko'rsatmaymiz.
    archived_total = (
        db.query(func.count(models.Student.id))
        .filter(models.Student.is_archived == True)
        .scalar()
    ) or 0

    # Yil boshigacha bo'lgan talabalar — kumulyativ hisobning boshlanish nuqtasi
    before = (
        db.query(func.count(models.Student.id))
        .filter(year_expr < sel_year)
        .scalar()
    ) or 0

    months = []
    running = before
    for m in range(1, 13):
        joined = joined_by_month.get(m, 0)
        running += joined
        months.append({"month": m, "joined": joined, "cumulative": running})

    return {
        "year": sel_year,
        "starting_total": before,
        "archived_total": archived_total,
        "months": months,
    }


@app.get("/stats/overview", response_model=schemas.StatsOverview)
def stats_overview(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    now = tz.now()  # joriy oy — Toshkent vaqti bo'yicha
    cur_month, cur_year = now.month, now.year
    sel_year = year or cur_year

    prev_month = cur_month - 1 if cur_month > 1 else 12
    prev_year = cur_year if cur_month > 1 else cur_year - 1

    total_students = db.query(func.count(models.Student.id)).scalar()
    active_students = db.query(func.count(models.Student.id)).filter(models.Student.is_active == True).scalar()
    total_groups = db.query(func.count(models.Group.id)).scalar()
    active_groups_count = db.query(func.count(models.Group.id)).filter(models.Group.is_active == True).scalar()

    # Load active groups (1 query)
    active_grps = db.query(models.Group).filter(models.Group.is_active == True).all()

    # Batch: barcha to'lovlar yil bo'yicha (1 query)
    pay_rows = (
        db.query(models.Payment.month, models.Payment.year,
                 func.sum(models.Payment.amount).label('total'),
                 func.count(models.Payment.id).label('cnt'))
        .filter(models.Payment.year.in_([sel_year, cur_year, prev_year]))
        .group_by(models.Payment.month, models.Payment.year)
        .all()
    )
    pay_map = {(r.month, r.year): (r.total or Decimal(0), r.cnt) for r in pay_rows}

    # Batch: barcha xarajatlar yil bo'yicha (1 query)
    exp_rows = (
        db.query(models.Expense.month, models.Expense.year,
                 func.sum(models.Expense.amount).label('total'))
        .filter(models.Expense.year.in_([sel_year, cur_year, prev_year]))
        .group_by(models.Expense.month, models.Expense.year)
        .all()
    )
    exp_map = {(r.month, r.year): r.total or Decimal(0) for r in exp_rows}

    # Batch: 12 oylik maosh (1 query)
    salary_cur_year = _batch_salary_by_month(db, active_grps, cur_year)
    salary_sel_year = salary_cur_year if sel_year == cur_year else _batch_salary_by_month(db, active_grps, sel_year)

    this_income = pay_map.get((cur_month, cur_year), (Decimal(0), 0))[0]
    last_income = pay_map.get((prev_month, prev_year), (Decimal(0), 0))[0]
    change_pct  = float((this_income - last_income) / last_income * 100) if last_income else 0.0

    # Joriy oy davomat foizi — belgilangan (present/absent) yozuvlardan nechtasi
    # "keldi". Belgilanmagan (is_present IS NULL) kunlar hisobga olinmaydi, aks
    # holda hali o'tmagan darslar foizni sun'iy ravishda pasaytirardi.
    att_marked = db.query(func.count(models.Attendance.id)).filter(
        extract('month', models.Attendance.lesson_date) == cur_month,
        extract('year', models.Attendance.lesson_date) == cur_year,
        models.Attendance.is_present.isnot(None),
    ).scalar() or 0
    att_present = db.query(func.count(models.Attendance.id)).filter(
        extract('month', models.Attendance.lesson_date) == cur_month,
        extract('year', models.Attendance.lesson_date) == cur_year,
        models.Attendance.is_present.is_(True),
    ).scalar() or 0
    attendance_rate = round(att_present / att_marked * 100, 1) if att_marked else 0.0

    total_teachers = db.query(func.count(models.User.id)).filter(
        models.User.role == UserRole.teacher.value,
        models.User.is_active == True,
    ).scalar() or 0

    cur_teacher_salary = salary_cur_year[cur_month]
    cur_external       = exp_map.get((cur_month, cur_year), Decimal(0))
    cur_total_exp      = cur_teacher_salary + cur_external
    cur_net_profit     = this_income - cur_total_exp

    history = []
    for m in range(1, 13):
        income    = pay_map.get((m, sel_year), (Decimal(0), 0))[0]
        pcount    = pay_map.get((m, sel_year), (Decimal(0), 0))[1]
        ext_exp   = exp_map.get((m, sel_year), Decimal(0))
        t_salary  = salary_sel_year[m]
        total_exp = t_salary + ext_exp
        history.append(schemas.MonthlyStats(
            year=sel_year, month=m, total_income=income,
            payment_count=pcount,
            active_students=active_students,
            active_groups=active_groups_count,
            teacher_salary=t_salary,
            external_expenses=ext_exp,
            total_expenses=total_exp,
            net_profit=income - total_exp,
        ))

    return schemas.StatsOverview(
        total_students=total_students,
        active_students=active_students,
        total_groups=total_groups,
        active_groups=active_groups_count,
        this_month_income=this_income,
        last_month_income=last_income,
        income_change_pct=change_pct,
        teacher_salary=cur_teacher_salary,
        external_expenses=cur_external,
        total_expenses=cur_total_exp,
        net_profit=cur_net_profit,
        attendance_rate=attendance_rate,
        total_teachers=total_teachers,
        monthly_history=history,
    )


# ── Teacher salaries breakdown ────────────────────────────────────────────────

@app.get("/stats/teacher-salaries")
def teacher_salaries_breakdown(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """
    Per-teacher salary breakdown based on attendance.
    Formula: 50 000 so'm / shu oyda o'tilgan darslar soni × talaba kelgan
    darslar soni (`_group_salary` / `_teacher_salary_breakdown` bilan bir xil).
    """
    groups = db.query(models.Group).filter(models.Group.is_active == True).order_by(models.Group.id).all()
    teachers: dict = {}
    grand_total = Decimal(0)

    for g in groups:
        group_salary, student_details, total_lessons_held = _group_salary(db, g, month, year)
        if group_salary == 0 and not student_details:
            continue

        per_lesson = (TEACHER_STUDENT_BONUS_UNIT / Decimal(total_lessons_held)).quantize(Decimal('1')) \
            if total_lessons_held else Decimal(0)

        grand_total += group_salary
        tid = g.teacher_id  # may be None
        if tid not in teachers:
            if tid is not None and g.teacher:
                tname = g.teacher.full_name or g.teacher.username
            else:
                tname = "O'qituvchi tayinlanmagan"
            teachers[tid] = {
                "teacher_id": tid,
                "teacher_name": tname,
                "groups": [],
                "total_salary": Decimal(0),
            }
        teachers[tid]["groups"].append({
            "group_id": g.id,
            "group_name": g.name,
            "stage": g.stage or "foundation",
            "per_lesson": float(per_lesson),
            "total_lessons_held": total_lessons_held,
            "students": student_details,
            "total_attended": sum(s["attended"] for s in student_details),
            "group_salary": float(group_salary),
        })
        teachers[tid]["total_salary"] += group_salary

    result = sorted(
        [
            {**t, "total_salary": float(t["total_salary"])}
            for t in teachers.values()
        ],
        key=lambda t: t["total_salary"],
        reverse=True,
    )
    return {
        "month": month,
        "year": year,
        "total_teacher_salary": float(grand_total),
        "teachers": result,
    }


# ── Teacher: My dashboard ─────────────────────────────────────────────────────

@app.get("/teacher/dashboard")
def teacher_my_dashboard(
    month: int = Query(None, ge=1, le=12),
    year:  int = Query(None, ge=2020),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """
    Teacher sees their own groups + estimated salary for the given month.
    Admin/metodist can also call this for any teacher_id (optional query param).
    """
    _today = tz.today()
    sel_month = month or _today.month
    sel_year  = year  or _today.year

    # Faol va yopiq (masalan, 100% tugagan/arxivlangan) guruhlar — hammasi
    # ko'rinadi, aks holda kurs tugab guruh yopilgach o'qituvchi hisobidan
    # butunlay yo'qolib qolardi (jumladan sertifikat generatsiyasi uchun ham
    # kerak). Faol guruhlar avval, keyin yopilganlari ko'rsatiladi.
    groups = (
        db.query(models.Group)
        .options(selectinload(models.Group.members))
        .filter(models.Group.teacher_id == actor.id)
        .order_by(models.Group.is_active.desc(), models.Group.name)
        .all()
    )
    if not groups:
        return {"teacher_id": actor.id, "teacher_name": actor.full_name or actor.username,
                "month": sel_month, "year": sel_year, "total_groups": 0,
                "total_students": 0, "total_salary": 0.0, "groups": []}

    group_ids = [g.id for g in groups]

    # Batch 1: completed lessons per group, AS OF THE END OF THE SELECTED MONTH —
    # tanlangan oy o'zgarganda "Kurs progressi" ham o'sha oy oxiriga qarab
    # yangilanishi uchun (avval oyga bog'liq bo'lmagan umumiy hisob edi).
    month_end_day = calendar.monthrange(sel_year, sel_month)[1]
    progress_cutoff = date(sel_year, sel_month, month_end_day)
    completed_map = core_calc.group_completed_lessons(db, group_ids, upto=progress_cutoff)

    # Batch 2: this-month lessons per group (1 query)
    mless_rows = (
        db.query(models.Attendance.group_id,
                 func.count(func.distinct(models.Attendance.lesson_date)).label('cnt'))
        .filter(
            models.Attendance.group_id.in_(group_ids),
            extract('month', models.Attendance.lesson_date) == sel_month,
            extract('year',  models.Attendance.lesson_date) == sel_year,
        )
        .group_by(models.Attendance.group_id)
        .all()
    )
    month_lessons_map = {r.group_id: r.cnt for r in mless_rows}

    # Batch 3: all attendance for salary (1 query)
    att_rows = (
        db.query(models.Attendance.group_id, models.Attendance.student_id,
                 func.count(models.Attendance.id).label('cnt'))
        .filter(
            models.Attendance.group_id.in_(group_ids),
            models.Attendance.is_present == True,
            extract('month', models.Attendance.lesson_date) == sel_month,
            extract('year',  models.Attendance.lesson_date) == sel_year,
        )
        .group_by(models.Attendance.group_id, models.Attendance.student_id)
        .all()
    )
    # {group_id: {student_id: attended_count}}
    att_map: dict = {}
    for r in att_rows:
        att_map.setdefault(r.group_id, {})[r.student_id] = r.cnt

    # Batch 4: student names (1 query)
    all_student_ids = [m.student_id for g in groups for m in g.members]
    name_rows = (
        db.query(models.Student.id, models.Student.full_name)
        .filter(models.Student.id.in_(all_student_ids))
        .all()
    )
    student_name_map = {r.id: r.full_name for r in name_rows}

    total_salary   = Decimal(0)
    total_students = 0
    groups_out     = []

    for g in groups:
        stage     = g.stage or 'foundation'
        total_less = schemas.STAGE_TOTAL_LESSONS.get(stage, 24)
        completed  = completed_map.get(g.id, 0)
        pct        = round(completed / total_less * 100, 1) if total_less > 0 else 0.0
        held      = month_lessons_map.get(g.id, 0)
        per_lesson = (TEACHER_STUDENT_BONUS_UNIT / Decimal(held)) if held > 0 else Decimal(0)

        # Hozirgi a'zolar emas — sel_month/sel_year davomida haqiqatan a'zo
        # bo'lganlar: aks holda shu oyda dars qatnashib, keyin guruhdan
        # chiqarilgan/boshqa guruhga o'tkazilgan talaba uchun o'qituvchi
        # maoshidan judo bo'lardi (davomat yozuvi saqlanib qolgan bo'lsa ham).
        month_members = core_calc.members_covering_month(g.members, sel_month, sel_year)

        group_salary    = Decimal(0)
        student_salaries = []
        g_att = att_map.get(g.id, {})

        for mem in month_members:
            attended = g_att.get(mem.student_id, 0)
            share    = (per_lesson * Decimal(str(attended))).quantize(Decimal('1'))
            group_salary += share
            student_salaries.append({
                "student_id":   mem.student_id,
                "student_name": student_name_map.get(mem.student_id, ""),
                "attended":     attended,
                "salary_share": float(share),
            })

        total_salary   += group_salary
        total_students += len(month_members)

        groups_out.append({
            "id":                      g.id,
            "name":                    g.name,
            "is_active":               g.is_active,
            "stage":                   stage,
            "schedule":                g.schedule or "",
            "lesson_time":             g.lesson_time or "",
            "start_date":              str(g.start_date) if g.start_date else None,
            "student_count":           len(month_members),
            "total_lessons":           total_less,
            "completed_lessons":       completed,
            "progress_pct":            pct,
            "per_lesson":              float(per_lesson.quantize(Decimal('1'))),
            "month_salary":            float(group_salary),
            "month_lessons_held":      month_lessons_map.get(g.id, 0),
            "student_salaries":        student_salaries,
        })

    return {
        "teacher_id":    actor.id,
        "teacher_name":  actor.full_name or actor.username,
        "month":         sel_month,
        "year":          sel_year,
        "total_groups":  len(groups_out),
        "total_students": total_students,
        "total_salary":  float(total_salary),
        "groups":        groups_out,
    }


@app.get("/teacher/certificates")
def teacher_my_certificate_groups(
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """O'qituvchining barcha guruhlari (faol va yopiq) va har birida
    tayyorlangan sertifikatlar soni — "Sertifikatlar" bo'limida ro'yxat
    ko'rsatish uchun (qaysi guruh uchun sertifikat tayyor, qaysi biriga
    hali generatsiya qilinmagan)."""
    groups = (
        db.query(models.Group)
        .filter(models.Group.teacher_id == actor.id)
        .order_by(models.Group.is_active.desc(), models.Group.name)
        .all()
    )
    if not groups:
        return []
    group_ids = [g.id for g in groups]
    cert_counts = dict(
        db.query(models.GroupCertificate.group_id, func.count(models.GroupCertificate.id))
        .filter(models.GroupCertificate.group_id.in_(group_ids))
        .group_by(models.GroupCertificate.group_id)
        .all()
    )
    member_counts = dict(
        db.query(models.GroupStudent.group_id, func.count(models.GroupStudent.id))
        .filter(models.GroupStudent.group_id.in_(group_ids), models.GroupStudent.left_at.is_(None))
        .group_by(models.GroupStudent.group_id)
        .all()
    )
    return [
        {
            "id": g.id, "name": g.name, "stage": g.stage, "is_active": g.is_active,
            "student_count": member_counts.get(g.id, 0),
            "certificate_count": cert_counts.get(g.id, 0),
        }
        for g in groups
    ]


# ── Expenses endpoints ────────────────────────────────────────────────────────

@app.get("/expenses", response_model=List[schemas.ExpenseRead])
def list_expenses(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    q = db.query(models.Expense)
    if month is not None:
        q = q.filter(models.Expense.month == month)
    if year is not None:
        q = q.filter(models.Expense.year == year)
    return q.order_by(models.Expense.year.desc(), models.Expense.month.desc(), models.Expense.id.desc()).all()


@app.get("/expenses/staff-options", response_model=List[schemas.StaffOption])
def list_expense_staff_options(db: Session = Depends(get_db), _: models.User = Depends(require_hunter)):
    """"Oylik" turidagi xarajat qo'shishda xodim tanlagich — hunter/admin uchun.

    Bloklangan xodimlar ham chiqadi: ishdan bo'shagan/bloklangan xodimga
    oxirgi oyligini xarajat sifatida yozish kerak bo'ladi. Ro'yxatda aktivlar
    birinchi turadi, bloklanganlar UI'da belgilanadi."""
    return (
        db.query(models.User)
        .order_by(models.User.is_active.desc(), models.User.full_name, models.User.username)
        .all()
    )


def _validate_salary_expense(db: Session, category: Optional[str], staff_id: Optional[int]) -> None:
    if category != 'salary':
        return
    if not staff_id:
        raise HTTPException(status_code=400, detail="Oylik xarajati uchun xodim tanlang")
    staff = db.query(models.User).filter(models.User.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")


@app.post("/expenses", response_model=schemas.ExpenseRead, status_code=201)
def create_expense(payload: schemas.ExpenseCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_hunter)):
    """Xarajat qo'shish — hunter/admin. Tahrirlash va o'chirish faqat adminda
    qoladi (kiritilgan xarajatni keyin o'zgartirish audit talab qiladi)."""
    data = payload.dict()
    _validate_salary_expense(db, data.get('category'), data.get('staff_id'))
    if data.get('category') != 'salary':
        data['staff_id'] = None
    exp = models.Expense(**data)
    db.add(exp)
    db.flush()
    write_audit(db, entity_type="expense", entity_id=exp.id, action="create",
                changed_by_id=actor.id, new_value=data)
    db.commit()
    db.refresh(exp)
    return exp


@app.put("/expenses/{expense_id}", response_model=schemas.ExpenseRead)
def update_expense(expense_id: int, payload: schemas.ExpenseUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Xarajat topilmadi")
    changes = payload.dict(exclude_unset=True)
    new_category = changes.get('category', exp.category)
    new_staff_id = changes.get('staff_id', exp.staff_id)
    _validate_salary_expense(db, new_category, new_staff_id)
    if new_category != 'salary':
        changes['staff_id'] = None
    old = {k: str(getattr(exp, k)) for k in changes}
    for k, v in changes.items():
        setattr(exp, k, v)
    write_audit(db, entity_type="expense", entity_id=exp.id, action="update",
                changed_by_id=actor.id, old_value=old, new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(exp)
    return exp


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Xarajat topilmadi")
    write_audit(db, entity_type="expense", entity_id=exp.id, action="delete",
                changed_by_id=actor.id,
                old_value={"name": exp.name, "amount": str(exp.amount), "month": exp.month, "year": exp.year})
    db.delete(exp)
    db.commit()


# ── Salary (xodimlar oyligi) ──────────────────────────────────────────────────

TEACHER_BASE_SALARY = Decimal('5000000')       # FIX oylik
TEACHER_STUDENT_BONUS_UNIT = Decimal('50000')  # talaba shu oydagi BARCHA darsga qatnasa oladigan to'liq ulush


def _teacher_salary_breakdown(db: Session, month: int, year: int) -> dict:
    """Har bir o'qituvchi uchun shu oydagi "talaba ulushi" haqqoniy taqsimoti,
    guruh darajasida hisoblanadi:

        lessons_held  = guruhda shu oyda haqiqatda o'tilgan (Attendance
                         yozuvi mavjud) noyob dars sanalari soni
        per_lesson    = 50 000 / lessons_held
        talaba ulushi = per_lesson × (talaba shu guruhda qatnashgan darslar soni)

    Guruhning o'qituvchisi (Group.teacher_id) shu guruhdagi barcha talabalar
    ulushini oladi. Talaba oy ichida bir guruhdan (demak bir o'qituvchidan)
    ikkinchisiga o'tkazilgan bo'lsa, har ikki guruh o'z ulushini alohida
    hisoblaydi — shuning uchun ikkala o'qituvchi ham o'z darslariga mos
    ulushini oladi (hech kim "yutib olmaydi"). Talaba oy oxirida arxivga
    o'tkazilgan bo'lsa ham, shu oydagi haqiqiy davomat asosida hisoblanadi.

    Qaytaradi: {teacher_id: {"total": Decimal, "items": [ {...}, ... ]}}
    """
    groups = (
        db.query(models.Group)
        .filter(models.Group.teacher_id.isnot(None))
        .all()
    )
    if not groups:
        return {}
    group_ids = [g.id for g in groups]
    teacher_by_group = {g.id: g.teacher_id for g in groups}
    name_by_group = {g.id: g.name for g in groups}

    lesson_date_rows = (
        db.query(models.Attendance.group_id, models.Attendance.lesson_date)
        .filter(
            models.Attendance.group_id.in_(group_ids),
            extract('month', models.Attendance.lesson_date) == month,
            extract('year', models.Attendance.lesson_date) == year,
        )
        .distinct()
        .all()
    )
    lessons_held: dict = {}
    for gid, _ld in lesson_date_rows:
        lessons_held[gid] = lessons_held.get(gid, 0) + 1

    att_rows = (
        db.query(
            models.Attendance.group_id,
            models.Attendance.student_id,
            models.Student.full_name,
            func.count(models.Attendance.id).label('cnt'),
        )
        .join(models.Student, models.Student.id == models.Attendance.student_id)
        .filter(
            models.Attendance.group_id.in_(group_ids),
            models.Attendance.is_present.is_(True),
            extract('month', models.Attendance.lesson_date) == month,
            extract('year', models.Attendance.lesson_date) == year,
        )
        .group_by(models.Attendance.group_id, models.Attendance.student_id, models.Student.full_name)
        .all()
    )

    breakdown: dict = {}
    for gid, sid, sname, attended in att_rows:
        held = lessons_held.get(gid, 0)
        if held <= 0 or not attended:
            continue
        teacher_id = teacher_by_group.get(gid)
        if teacher_id is None:
            continue
        per_lesson = TEACHER_STUDENT_BONUS_UNIT / Decimal(held)
        share = (per_lesson * Decimal(attended)).quantize(Decimal('1'))
        entry = breakdown.setdefault(teacher_id, {"total": Decimal('0'), "items": []})
        entry["total"] += share
        entry["items"].append({
            "group_id": gid, "group_name": name_by_group.get(gid, ''),
            "student_id": sid, "student_name": sname,
            "lessons_held": held, "attended": attended,
            "per_lesson": per_lesson, "share": share,
        })
    return breakdown


def _teacher_auto_salary(db: Session, teacher_id: int, month: int, year: int,
                          breakdown_map: Optional[dict] = None) -> tuple:
    if breakdown_map is None:
        breakdown_map = _teacher_salary_breakdown(db, month, year)
    entry = breakdown_map.get(teacher_id)
    total = entry["total"] if entry else Decimal('0')
    student_count = len({it["student_id"] for it in entry["items"]}) if entry else 0
    salary = TEACHER_BASE_SALARY + total
    return salary, student_count


def _salary_row_for(db: Session, u: models.User, month: int, year: int,
                     paid: Decimal, override: Optional[models.SalaryOverride],
                     breakdown_map: Optional[dict] = None) -> schemas.SalaryStaffRow:
    is_internship = bool(override and override.is_internship)
    if u.role == UserRole.teacher.value:
        auto_salary, student_count = _teacher_auto_salary(db, u.id, month, year, breakdown_map)
    else:
        auto_salary = None
        student_count = None
    base_salary = auto_salary if auto_salary is not None else (u.salary or Decimal('0'))
    if override is not None:
        salary = Decimal('0') if is_internship else override.amount
        is_auto = False
    else:
        salary = base_salary
        is_auto = (u.role == UserRole.teacher.value)
    return schemas.SalaryStaffRow(
        staff_id=u.id, full_name=u.full_name or u.username, role=u.role,
        salary=salary, paid=paid, remaining=salary - paid,
        auto=is_auto, student_count=student_count, auto_salary=auto_salary,
        is_internship=is_internship, has_override=override is not None,
        is_active=bool(u.is_active),
    )


@app.get("/salary", response_model=schemas.SalaryOverview)
def salary_overview(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Har bir xodimning belgilangan oyligi va shu oyda "oylik" turida
    to'langan xarajatlar (hunter kiritgan) yig'indisi — superadmin ko'radi."""
    paid_rows = (
        db.query(models.Expense.staff_id, func.sum(models.Expense.amount).label('total'))
        .filter(
            models.Expense.category == 'salary',
            models.Expense.staff_id.isnot(None),
            models.Expense.month == month,
            models.Expense.year == year,
        )
        .group_by(models.Expense.staff_id)
        .all()
    )
    paid_map = {r.staff_id: r.total for r in paid_rows}
    override_map = {
        o.staff_id: o
        for o in db.query(models.SalaryOverride).filter(
            models.SalaryOverride.month == month, models.SalaryOverride.year == year,
        ).all()
    }

    # Aktiv xodimlar + bloklangan bo'lsa ham shu oyda oyligi to'langan yoki
    # qo'lda oylik belgilangan xodimlar (aks holda to'lov "yo'qolib" qolardi).
    extra_ids = set(paid_map) | set(override_map)
    staff_q = db.query(models.User)
    if extra_ids:
        staff_q = staff_q.filter(or_(models.User.is_active.is_(True), models.User.id.in_(extra_ids)))
    else:
        staff_q = staff_q.filter(models.User.is_active.is_(True))
    staff = staff_q.order_by(
        models.User.is_active.desc(), models.User.full_name, models.User.username
    ).all()

    breakdown_map = _teacher_salary_breakdown(db, month, year)
    rows = []
    total_salary = Decimal('0')
    total_paid = Decimal('0')
    for u in staff:
        row = _salary_row_for(db, u, month, year, paid_map.get(u.id) or Decimal('0'),
                               override_map.get(u.id), breakdown_map)
        total_salary += row.salary
        total_paid += row.paid
        rows.append(row)
    return schemas.SalaryOverview(month=month, year=year, rows=rows,
                                   total_salary=total_salary, total_paid=total_paid)


@app.get("/salary/me", response_model=schemas.SalaryStaffRow)
def my_salary(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """O'z oyligini ko'rish — har qanday tizimga kirgan xodim uchun (masalan,
    o'qituvchi o'z hisobida FIX + talaba boshiga hisoblangan oyligini ko'radi)."""
    paid = (
        db.query(func.sum(models.Expense.amount))
        .filter(
            models.Expense.category == 'salary',
            models.Expense.staff_id == actor.id,
            models.Expense.month == month,
            models.Expense.year == year,
        )
        .scalar()
    ) or Decimal('0')
    override = db.query(models.SalaryOverride).filter(
        models.SalaryOverride.staff_id == actor.id,
        models.SalaryOverride.month == month,
        models.SalaryOverride.year == year,
    ).first()
    return _salary_row_for(db, actor, month, year, paid, override)


@app.get("/salary/{user_id}/breakdown", response_model=schemas.SalaryBreakdown)
def salary_breakdown(
    user_id: int,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """O'qituvchining shu oydagi "talaba ulushi" formulasi bo'yicha to'liq
    tafsiloti — har bir guruh/talaba uchun necha dars o'tilgani, talaba
    nechtasiga qatnashgani va shundan qancha ulush chiqqani. Superadmin
    istalgan o'qituvchi uchun, o'qituvchining o'zi esa faqat o'zi uchun
    ko'ra oladi."""
    if actor.role != UserRole.admin.value and actor.id != user_id:
        raise HTTPException(status_code=403, detail="Faqat o'zingizning breakdown'ingizni ko'rishingiz mumkin")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    breakdown_map = _teacher_salary_breakdown(db, month, year)
    entry = breakdown_map.get(user_id)
    items = entry["items"] if entry else []
    total = entry["total"] if entry else Decimal('0')
    items_sorted = sorted(items, key=lambda it: (it["group_name"], it["student_name"]))
    return schemas.SalaryBreakdown(
        staff_id=user_id, month=month, year=year,
        base_salary=TEACHER_BASE_SALARY if user.role == UserRole.teacher.value else Decimal('0'),
        per_student_total=total,
        student_bonus_unit=TEACHER_STUDENT_BONUS_UNIT,
        items=[schemas.SalaryBreakdownItem(**it) for it in items_sorted],
        total=(TEACHER_BASE_SALARY if user.role == UserRole.teacher.value else Decimal('0')) + total,
    )


@app.put("/salary/{user_id}", response_model=schemas.SalaryStaffRow)
def set_staff_salary(
    user_id: int,
    payload: schemas.SalarySetRequest,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    """Xodimning oyligini o'rnatish/o'zgartirish — faqat admin.

    O'qituvchi (role=teacher) oyligi avtomatik hisoblanadi (FIX 5 mln +
    talaba ulushi); admin buni shu oy (month/year) uchun qo'lda override
    qilishi mumkin — boshqa oylar formulaga ko'ra hisoblanishda davom etadi.
    Boshqa rollar uchun — oddiy belgilangan oylik (month/year e'tiborga
    olinmaydi).

    `is_internship=true` (har qanday rol uchun, month/year majburiy) — shu
    oy uchun xodimni "stajirovka" deb belgilaydi: darsga/ishga hech qanday
    cheklovsiz, lekin o'sha oy uchun oylik 0 bo'ladi. Bekor qilish uchun
    DELETE /salary/{user_id}/override chaqiriladi (formulaga/asosiy oylikka
    qaytaradi)."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    if payload.is_internship:
        if month is None or year is None:
            raise HTTPException(status_code=400, detail="Stajirovka belgilash uchun oy/yil kerak")
        override = db.query(models.SalaryOverride).filter(
            models.SalaryOverride.staff_id == user.id,
            models.SalaryOverride.month == month,
            models.SalaryOverride.year == year,
        ).first()
        old_val = {"amount": str(override.amount), "is_internship": override.is_internship} if override else None
        if override:
            override.amount = Decimal('0')
            override.is_internship = True
            override.set_by_id = actor.id
        else:
            override = models.SalaryOverride(
                staff_id=user.id, month=month, year=year,
                amount=Decimal('0'), is_internship=True, set_by_id=actor.id,
            )
            db.add(override)
        write_audit(db, entity_type="salary_override", entity_id=user.id, action="update",
                    changed_by_id=actor.id,
                    old_value=old_val,
                    new_value={"amount": "0", "is_internship": True, "month": month, "year": year})
        db.commit()
        return _salary_row_for(db, user, month, year, Decimal('0'), override)

    if user.role == UserRole.teacher.value:
        if month is None or year is None:
            raise HTTPException(status_code=400, detail="O'qituvchi oyligini override qilish uchun oy/yil kerak")
        override = db.query(models.SalaryOverride).filter(
            models.SalaryOverride.staff_id == user.id,
            models.SalaryOverride.month == month,
            models.SalaryOverride.year == year,
        ).first()
        old_val = {"amount": str(override.amount), "is_internship": override.is_internship} if override else None
        if override:
            override.amount = payload.salary
            override.is_internship = False
            override.set_by_id = actor.id
        else:
            override = models.SalaryOverride(
                staff_id=user.id, month=month, year=year,
                amount=payload.salary, is_internship=False, set_by_id=actor.id,
            )
            db.add(override)
        write_audit(db, entity_type="salary_override", entity_id=user.id, action="update",
                    changed_by_id=actor.id,
                    old_value=old_val,
                    new_value={"amount": str(payload.salary), "is_internship": False, "month": month, "year": year})
        db.commit()
        return _salary_row_for(db, user, month, year, Decimal('0'), override)

    old_salary = user.salary
    user.salary = payload.salary
    write_audit(db, entity_type="user_salary", entity_id=user.id, action="update",
                changed_by_id=actor.id,
                old_value={"salary": str(old_salary) if old_salary is not None else None},
                new_value={"salary": str(payload.salary)})
    # Agar shu oy uchun avval "stajirovka" (yoki boshqa override) belgilangan
    # bo'lsa — asosiy oylik qo'lda tahrirlanganda bekor qilinadi, aks holda
    # override doim ustunlik qilib, yangi qiymat ko'rinmay qoladi.
    if month is not None and year is not None:
        stale_override = db.query(models.SalaryOverride).filter(
            models.SalaryOverride.staff_id == user.id,
            models.SalaryOverride.month == month,
            models.SalaryOverride.year == year,
        ).first()
        if stale_override:
            db.delete(stale_override)
    db.commit()
    db.refresh(user)
    return schemas.SalaryStaffRow(
        staff_id=user.id, full_name=user.full_name or user.username, role=user.role,
        salary=user.salary or Decimal('0'), paid=Decimal('0'), remaining=user.salary or Decimal('0'),
    )


@app.delete("/salary/{user_id}/override", status_code=204)
def clear_teacher_salary_override(
    user_id: int,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    """Xodimning (o'qituvchi yoki boshqa rol) shu oy uchun qo'lda override
    qilingan oyligini (jumladan "stajirovka" belgisini) bekor qiladi —
    keyingi o'qishda yana formula/asosiy oylik bo'yicha hisoblanadi
    ("Recalculate")."""
    override = db.query(models.SalaryOverride).filter(
        models.SalaryOverride.staff_id == user_id,
        models.SalaryOverride.month == month,
        models.SalaryOverride.year == year,
    ).first()
    if not override:
        return
    write_audit(db, entity_type="salary_override", entity_id=user_id, action="delete",
                changed_by_id=actor.id,
                old_value={"amount": str(override.amount), "month": month, "year": year})
    db.delete(override)
    db.commit()


# ── Group certificates (guruh sertifikatlari, dizaynli shablon) ──────────────
# Eslatma: `models.Certificate` (talaba profilidagi PDF-fayl havolali
# sertifikat, /certificates endpointlari) dan farqli, alohida funksiya.

def _certificate_access_check(actor: models.User, group: models.Group) -> None:
    if actor.role in (UserRole.admin.value, UserRole.hunter.value):
        return
    if actor.role == UserRole.teacher.value and group.teacher_id == actor.id:
        return
    raise HTTPException(status_code=403, detail="Sertifikatlarga kirish huquqi yo'q")


@app.get("/groups/{group_id}/certificates", response_model=List[schemas.GroupCertificateOut])
def list_group_certificates(
    group_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """Guruh uchun avval generatsiya qilingan sertifikatlarni qaytaradi
    (bo'lmasa — bo'sh ro'yxat; sahifa ochilganda oldingi holatni tiklash
    uchun ishlatiladi)."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    _certificate_access_check(actor, group)
    return (
        db.query(models.GroupCertificate)
        .filter(models.GroupCertificate.group_id == group_id)
        .all()
    )


@app.post("/groups/{group_id}/certificates/generate", response_model=List[schemas.GroupCertificateOut])
def generate_group_certificates(
    group_id: int,
    payload: schemas.GroupCertificateGenerateRequest,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """Guruhdagi (yoki tanlangan) o'quvchilar uchun sertifikat yozuvlarini
    yaratadi — admin, hunter yoki shu guruhning o'qituvchisi chaqira oladi.
    Allaqachon mavjud (group, student) yozuvi bo'lsa, o'zgartirilmay
    qaytariladi — "qayta generatsiya" avvalgi tahrirlarni yo'qotmaydi."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    _certificate_access_check(actor, group)

    member_rows = (
        db.query(models.GroupStudent, models.Student)
        .join(models.Student, models.Student.id == models.GroupStudent.student_id)
        .filter(models.GroupStudent.group_id == group_id)
        .all()
    )
    target_ids = set(payload.student_ids) if payload.student_ids is not None else None
    year = tz.today().year

    existing_rows = (
        db.query(models.GroupCertificate)
        .filter(models.GroupCertificate.group_id == group_id)
        .all()
    )
    existing_by_student = {c.student_id: c for c in existing_rows}

    result = []
    for gs, student in member_rows:
        if target_ids is not None and student.id not in target_ids:
            continue
        existing = existing_by_student.get(student.id)
        if existing:
            result.append(existing)
            continue
        cert = models.GroupCertificate(
            group_id=group_id, student_id=student.id,
            cert_number=f"MIN-{year}-{group_id}-{student.id}",
            student_name=student.full_name,
            course_label=payload.course_label,
            issue_date=payload.issue_date,
            signer_name=payload.signer_name,
            signer_title=payload.signer_title,
            created_by_id=actor.id,
        )
        db.add(cert)
        db.flush()
        result.append(cert)
    db.commit()
    for c in result:
        db.refresh(c)
    return result


@app.put("/groups/{group_id}/certificates", response_model=List[schemas.GroupCertificateOut])
def save_group_certificates(
    group_id: int,
    payload: schemas.GroupCertificateBulkUpdateRequest,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """Sertifikat ustida to'g'ridan-to'g'ri qilingan tahrirlarni (ism, sana,
    imzo, raqam) saqlaydi — admin, hunter yoki shu guruhning o'qituvchisi."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    _certificate_access_check(actor, group)

    ids = [it.id for it in payload.items]
    certs = (
        db.query(models.GroupCertificate)
        .filter(models.GroupCertificate.id.in_(ids), models.GroupCertificate.group_id == group_id)
        .all()
    )
    cert_map = {c.id: c for c in certs}
    for it in payload.items:
        c = cert_map.get(it.id)
        if not c:
            continue
        if it.student_name is not None: c.student_name = it.student_name
        if it.cert_number is not None: c.cert_number = it.cert_number
        if it.course_label is not None: c.course_label = it.course_label
        if it.issue_date is not None: c.issue_date = it.issue_date
        if it.signer_name is not None: c.signer_name = it.signer_name
        if it.signer_title is not None: c.signer_title = it.signer_title
    db.commit()
    for c in certs:
        db.refresh(c)
    return certs


MONTHS_UZ = ['','Yanvar','Fevral','Mart','Aprel','May','Iyun',
             'Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']

@app.get("/payments/{payment_id}/receipt", response_class=HTMLResponse)
def payment_receipt(
    payment_id: int,
    _token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin_download),
):
    p = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")

    student = p.student
    group   = p.group
    month_name = MONTHS_UZ[p.month] if 1 <= p.month <= 12 else str(p.month)
    paid_date  = p.paid_at.strftime('%d.%m.%Y %H:%M') if p.paid_at else '—'
    amount_fmt = f"{int(p.amount):,}".replace(',', ' ')

    # Foydalanuvchi kiritgan matnlar HTML kontekstiga qo'yilishidan oldin escape qilinadi
    # (aks holda talaba ismi / izoh orqali saqlanadigan XSS bo'lardi — chek admin brauzerida ochiladi).
    student_name = html.escape(student.full_name) if student and student.full_name else '—'
    group_name   = html.escape(group.name) if group and group.name else '—'
    notes_html   = html.escape(p.notes) if p.notes else ''

    page = f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<title>Chek #{p.id:05d}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f5f5f5; display:flex;
         justify-content:center; align-items:flex-start; min-height:100vh; padding:20px; }}
  .receipt {{ background:#fff; width:340px; padding:28px 24px 32px;
              border-radius:12px; box-shadow:0 4px 24px rgba(0,0,0,.12); }}
  .brand {{ text-align:center; margin-bottom:20px; }}
  .brand-name {{ font-size:22px; font-weight:800; color:#1d4ed8; letter-spacing:-.5px; }}
  .brand-sub  {{ font-size:11px; color:#737373; margin-top:2px; }}
  .divider {{ border:none; border-top:1px dashed #d4d4d4; margin:16px 0; }}
  .receipt-title {{ text-align:center; font-size:13px; color:#737373; margin-bottom:16px; }}
  .receipt-num {{ font-size:11px; color:#a3a3a3; text-align:center; margin-top:2px; }}
  .row {{ display:flex; justify-content:space-between; align-items:flex-start;
          margin-bottom:10px; gap:8px; }}
  .row .label {{ font-size:12px; color:#737373; white-space:nowrap; }}
  .row .val   {{ font-size:12px; color:#0a0a0a; font-weight:500; text-align:right; }}
  .amount-box {{ background:#eff6ff; border-radius:8px; padding:14px 16px;
                 text-align:center; margin:16px 0; }}
  .amount-box .amt {{ font-size:26px; font-weight:800; color:#1d4ed8; letter-spacing:-1px; }}
  .amount-box .cur {{ font-size:13px; color:#3b82f6; font-weight:600; margin-left:4px; }}
  .status {{ display:inline-flex; align-items:center; gap:6px; background:#dcfce7;
             color:#16a34a; border-radius:20px; padding:4px 14px;
             font-size:12px; font-weight:700; margin:0 auto; display:block; text-align:center; }}
  .footer {{ text-align:center; font-size:10px; color:#a3a3a3; margin-top:20px; line-height:1.5; }}
  @media print {{
    body {{ background:#fff; padding:0; }}
    .receipt {{ box-shadow:none; border-radius:0; }}
    .no-print {{ display:none !important; }}
  }}
  .print-btn {{ display:block; width:100%; margin-top:20px; padding:10px;
                background:#1d4ed8; color:#fff; border:none; border-radius:8px;
                font-size:14px; font-weight:600; cursor:pointer; }}
  .print-btn:hover {{ background:#1e40af; }}
</style>
</head>
<body>
<div class="receipt">
  <div class="brand">
    <div class="brand-name">IT Hub</div>
    <div class="brand-sub">O'quv markazi</div>
  </div>

  <hr class="divider">
  <div class="receipt-title">TO'LOV CHEKI</div>
  <div class="receipt-num"># {p.id:05d}</div>
  <hr class="divider">

  <div class="row">
    <span class="label">O'quvchi</span>
    <span class="val">{student_name}</span>
  </div>
  <div class="row">
    <span class="label">Guruh</span>
    <span class="val">{group_name}</span>
  </div>
  <div class="row">
    <span class="label">Oy</span>
    <span class="val">{month_name} {p.year}</span>
  </div>
  <div class="row">
    <span class="label">Sana</span>
    <span class="val">{paid_date}</span>
  </div>
  {f'<div class="row"><span class="label">Izoh</span><span class="val">{notes_html}</span></div>' if notes_html else ''}

  <hr class="divider">

  <div class="amount-box">
    <span class="amt">{amount_fmt}</span>
    <span class="cur">so'm</span>
  </div>

  <div class="status">&#10003; TO'LANGAN</div>

  <div class="footer">
    Ushbu chek IT Hub o'quv markazi tomonidan<br>
    rasmiy to'lov tasdiqi sifatida berilgan.
  </div>

  <button class="print-btn no-print" onclick="window.print()">&#128438; Chop etish</button>
</div>
</body>
</html>"""
    return HTMLResponse(content=page)


@app.get("/stats/export/excel")
def export_payments_excel(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    _token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin_download),
):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kutubxonasi o'rnatilmagan")

    q = db.query(models.Payment)
    if month:
        q = q.filter(models.Payment.month == month)
    if year:
        q = q.filter(models.Payment.year == year)
    payments = q.order_by(models.Payment.paid_at.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "To'lovlar"

    headers = ["#", "Talaba", "Guruh", "Miqdor (so'm)", "Oy", "Yil", "To'langan sana", "Izoh"]
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    month_names = {1:"Yanvar",2:"Fevral",3:"Mart",4:"Aprel",5:"May",6:"Iyun",
                   7:"Iyul",8:"Avgust",9:"Sentyabr",10:"Oktyabr",11:"Noyabr",12:"Dekabr"}

    for i, p in enumerate(payments, 1):
        ws.append([
            i,
            p.student.full_name if p.student else "",
            p.group.name if p.group else "",
            float(p.amount),
            month_names.get(p.month, p.month),
            p.year,
            p.paid_at.strftime("%d.%m.%Y %H:%M") if p.paid_at else "",
            p.notes or "",
        ])

    # Column widths
    col_widths = [5, 25, 20, 18, 12, 8, 20, 25]
    for col, w in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w

    # Total row
    total = sum(float(p.amount) for p in payments)
    last_row = len(payments) + 2
    ws.cell(row=last_row, column=1, value="JAMI:")
    ws.cell(row=last_row, column=1).font = Font(bold=True)
    ws.cell(row=last_row, column=4, value=total)
    ws.cell(row=last_row, column=4).font = Font(bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"payments_{year or 'all'}_{month or 'all'}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "3.0.0"}


# ── Teacher: Today's groups for quick attendance ───────────────────────────────

# Uzbek day abbreviations → Python weekday (Mon=0)
_DAY_WORDS = {
    'du': 0, 'dush': 0,
    'se': 1, 'sesh': 1,
    'chor': 2,
    'pay': 3,
    'ju': 4, 'jum': 4,
    'shan': 5,
    'yak': 6,
}


def _schedule_has_today(schedule: str, today_wd: int, ref_date: date = None) -> bool:
    if not schedule:
        return False
    s = schedule.lower()
    if 'toq' in s:
        # "Toq kunlar" — oyning toq sanalari (1, 3, 5, ...), hafta kuni emas.
        return bool(ref_date) and ref_date.day % 2 == 1
    if 'juft' in s:
        # "Juft kunlar" — oyning juft sanalari (2, 4, 6, ...), hafta kuni emas.
        return bool(ref_date) and ref_date.day % 2 == 0
    import re
    tokens = re.split(r'[\s,\-/]+', s)
    return any(_DAY_WORDS.get(t) == today_wd for t in tokens)


@app.get("/attendance/today")
def today_groups(
    target_date: Optional[date] = Query(None),  # admin can pick any date
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """
    Groups for quick attendance — faqat shu kunga (target_date yoki bugun)
    jadvali mos keladigan guruhlar (Toq/Juft kunlar oyning sanasi bo'yicha,
    boshqa jadvallar hafta kuni bo'yicha).
    - Admin/metodist/hunter: barcha faol guruhlar, lekin shu kunga mos keladigan.
    - Teacher: only their groups scheduled for today.
    """
    ref_date = target_date or tz.today()
    ref_wd = ref_date.weekday()
    is_admin_or_metodist = actor.role in (UserRole.admin.value, UserRole.metodist.value,
                                          UserRole.hunter.value, UserRole.sales.value)

    q = (
        db.query(models.Group)
        .options(joinedload(models.Group.teacher), selectinload(models.Group.members))
        .filter(models.Group.is_active == True)
    )
    if not is_admin_or_metodist:
        q = q.filter(models.Group.teacher_id == actor.id)
    groups = q.order_by(models.Group.name).all()

    # Batch: barcha guruhlar uchun shu kunda davomat soni (1 query)
    group_ids = [g.id for g in groups]
    taken_rows = (
        db.query(models.Attendance.group_id,
                 func.count(models.Attendance.id).label('cnt'))
        .filter(
            models.Attendance.group_id.in_(group_ids),
            models.Attendance.lesson_date == ref_date,
        )
        .group_by(models.Attendance.group_id)
        .all()
    )
    taken_map = {r.group_id: r.cnt for r in taken_rows}

    result = []
    for g in groups:
        if not _schedule_has_today(g.schedule, ref_wd, ref_date):
            continue
        taken = taken_map.get(g.id, 0)
        result.append({
            "id": g.id,
            "name": g.name,
            "stage": g.stage or 'foundation',
            "schedule": g.schedule,
            "lesson_time": g.lesson_time,
            "teacher_name": g.teacher.full_name or g.teacher.username if g.teacher else None,
            "student_count": len(core_calc.members_covering_date(g.members, ref_date)),
            "attendance_taken": taken > 0,
            "attendance_count": taken,
            "date": str(ref_date),
        })

    result.sort(key=lambda r: (r['lesson_time'] or '99:99', r['name']))
    return result


# ── Finance: monthly summary ───────────────────────────────────────────────────

def _month_offsets(month: int, year: int, count: int):
    """So'ralgan oydan orqaga `count` ta (month, year) juftligi — eskisidan yangisiga."""
    out = []
    m, y = month, year
    for _ in range(count):
        out.append((m, y))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def _attach_unpaid_streaks(db: Session, data: dict, lookback: int = 6) -> None:
    """Har bir to'lamagan o'quvchiga "necha oydan beri to'lov yo'q" belgisini qo'shadi.

    Bu aynan TO'LOV YOZUVI yo'qligini sanaydi (majburiyat qayta hisoblanmaydi —
    o'tgan oylar uchun tarif/ta'til/chegirmani qayta yurgizish qimmat bo'lardi).
    Shuning uchun UI'da ham "to'lov yo'q" deb yoziladi, "qarzdor" deb emas.
    """
    month, year = data["month"], data["year"]
    periods = _month_offsets(month, year, lookback)          # eskisidan yangisiga
    pairs = [(m, y) for m, y in periods]

    targets = []   # (group_id, student_id)
    for g in data["groups"]:
        for st in g.get("unpaid_students", []):
            targets.append((g["group_id"], st["student_id"]))
    if not targets:
        return

    student_ids = {sid for _, sid in targets}
    # Qo'pol prefiltr (yillar bo'yicha) — aniq (oy, yil) mosligi quyida,
    # to'plam a'zoligi orqali tekshiriladi.
    rows = db.query(
        models.Payment.group_id, models.Payment.student_id,
        models.Payment.month, models.Payment.year,
    ).filter(
        models.Payment.student_id.in_(student_ids),
        models.Payment.year.in_({y for _, y in pairs}),
    ).all()
    wanted = set(pairs)
    paid = {(gid, sid, m, y) for gid, sid, m, y in rows if (m, y) in wanted}

    for g in data["groups"]:
        for st in g.get("unpaid_students", []):
            streak = 0
            for m, y in reversed(periods):        # joriy oydan orqaga
                if (g["group_id"], st["student_id"], m, y) in paid:
                    break
                streak += 1
            st["months_without_payment"] = streak


@app.get("/finance/trend")
def finance_trend(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    months: int = Query(6, ge=2, le=12),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Yig'ilish darajasi trendi — jami va har bir guruh kesimida.

    Nima uchun alohida endpoint: `/finance/monthly` har bir chaqiruvda barcha
    o'quvchilar tafsilotini qaytaradi (~250-450 ms). 6 oylik trend uchun uni
    6 marta chaqirish sekin ham, ortiqcha ham — bu yerda faqat yig'ma raqamlar
    hisoblanadi, formula esa `_finance_month` bilan bir xil.
    """
    series = []
    per_group: dict[int, dict] = {}

    for m, y in _month_offsets(month, year, months):
        snap = _finance_month(db, m, y, with_students=False)
        exp, act = snap["total_expected"], snap["total_actual"]
        series.append({
            "month": m, "year": y,
            "expected": exp,
            "actual": act,
            "deficit": snap["total_deficit"],
            "collection_pct": round(act / exp * 100, 1) if exp > 0 else None,
            "unpaid_count": sum(g["unpaid_count"] for g in snap["groups"]),
        })
        for g in snap["groups"]:
            entry = per_group.setdefault(g["group_id"], {
                "group_id": g["group_id"], "group_name": g["group_name"], "points": [],
            })
            entry["group_name"] = g["group_name"]
            entry["points"].append({
                "month": m, "year": y,
                "expected": g["expected"], "actual": g["actual"],
                "collection_pct": round(g["actual"] / g["expected"] * 100, 1) if g["expected"] > 0 else None,
            })

    return {"months": series, "groups": list(per_group.values())}


def _finance_month(db: Session, month: int, year: int, *, with_students: bool = True) -> dict:
    """Bir oylik moliyaviy kesim.

    Tushum formulasi: owed = to'liq oylik tarif (davomatga bog'liq emas) —
    ta'til va special chegirmalar hisobga olinadi. O'qituvchi maoshi alohida,
    davomat asosida hisoblanadi.

    `with_students=False` — faqat yig'ma raqamlar (trend uchun): o'quvchilar
    ro'yxati qaytarilmaydi, chunki 6 oylik trendda u yuzlab ortiqcha qator
    bo'lardi. Formula ikkala rejimda ham AYNAN bir xil — shuning uchun bitta
    funksiyada turibdi.
    """
    groups = db.query(models.Group).filter(models.Group.is_active == True).all()  # noqa: E712
    result = []
    total_expected = Decimal(0)
    total_actual = Decimal(0)

    for g in groups:
        # Guruh so'ralgan oyda hali boshlanmagan bo'lsa — hech kim qarzdor emas
        # (core_calc.student_month_owed bilan bir xil qoida — Students/Payments
        # sahifalari bilan mos kelishi uchun). Guruh baribir ro'yxatda ko'rinadi,
        # faqat expected/owed 0 bo'ladi.
        group_started = not (g.start_date and (g.start_date.year, g.start_date.month) > (year, month))

        actual = db.query(func.sum(models.Payment.amount)).filter(
            models.Payment.group_id == g.id,
            models.Payment.month == month,
            models.Payment.year == year,
        ).scalar() or Decimal(0)

        total_lessons_held = db.query(
            func.count(func.distinct(models.Attendance.lesson_date))
        ).filter(
            models.Attendance.group_id == g.id,
            extract('month', models.Attendance.lesson_date) == month,
            extract('year', models.Attendance.lesson_date) == year,
        ).scalar() or 0

        expected = Decimal(0)
        student_details = []
        unpaid_count = 0

        # Hozirgi a'zolar emas — shu OY davomida haqiqatan a'zo bo'lganlar
        # (guruh o'zgartirgan/tark etgan talabalar ham shu oy uchun hisobga
        # kiradi, ko'ring: models.GroupStudent.left_at).
        month_members = core_calc.members_covering_month(g.members, month, year)
        for m in month_members:
            attended = 0
            if with_students:
                attended = db.query(func.count(models.Attendance.id)).filter(
                    models.Attendance.group_id == g.id,
                    models.Attendance.student_id == m.student_id,
                    models.Attendance.is_present == True,  # noqa: E712
                    extract('month', models.Attendance.lesson_date) == month,
                    extract('year', models.Attendance.lesson_date) == year,
                ).scalar() or 0

            if not group_started or not core_calc.bills_month(m, month, year):
                # Guruh boshlanmagan, yoki talaba shu oy boshqa guruhga o'tkazilgan
                # (bu oy yangi guruhda hisoblanadi — core_calc.bills_month)
                price = Decimal(0)
                tariff_name = None
            elif m.tariff:
                price = Decimal(str(m.tariff.price))
                tariff_name = m.tariff.name
            elif g.course_price and Decimal(str(g.course_price)) > 0:
                price = Decimal(str(g.course_price))
                tariff_name = "Guruh narxi"
            else:
                price = Decimal(0)
                tariff_name = None

            if price > 0:
                price = core_calc.vacation_adjusted_price(db, m.student_id, g.id, month, year, price)
                m_active_group_ids = core_calc._active_group_ids(db, m.student_id)
                apply_global = not m_active_group_ids or min(m_active_group_ids) == g.id
                price = core_calc.apply_special_discounts(
                    price, core_calc.active_special_discounts(db, m.student_id),
                    g.id, month, year, apply_global=apply_global,
                    active_group_ids=m_active_group_ids,
                )

            if price > 0:
                owed = price.quantize(Decimal('1'))
                tariff_price = float(price)
                paid_amount = db.query(func.sum(models.Payment.amount)).filter(
                    models.Payment.group_id == g.id,
                    models.Payment.student_id == m.student_id,
                    models.Payment.month == month,
                    models.Payment.year == year,
                ).scalar() or Decimal(0)
                advance = core_calc.advance_amount_for_month(m.student, month, year)
                is_paid = (paid_amount + advance) >= owed
                expected += owed
                if not is_paid:
                    unpaid_count += 1
            else:
                owed = Decimal(0)
                tariff_price = 0.0
                is_paid = None  # majburiyat yo'q

            if with_students:
                student_details.append({
                    "student_id": m.student_id,
                    "student_name": m.student.full_name,
                    "phone": m.student.phone1,
                    "tariff_name": tariff_name,
                    "tariff_price": tariff_price,
                    "attended": attended,
                    "total_lessons_held": total_lessons_held,
                    "owed": float(owed),
                    "is_paid": is_paid,
                })

        total_expected += expected
        total_actual += actual

        row = {
            "group_id": g.id,
            "group_name": g.name,
            "student_count": len(month_members),
            "expected": float(expected),
            "actual": float(actual),
            "deficit": float(expected - actual),
            "unpaid_count": unpaid_count,
        }
        if with_students:
            row["unpaid_students"] = [s for s in student_details if s["is_paid"] is False]
            row["all_students"] = student_details
        result.append(row)

    return {
        "month": month,
        "year": year,
        "total_expected": float(total_expected),
        "total_actual": float(total_actual),
        "total_deficit": float(total_expected - total_actual),
        "groups": result,
    }


@app.get("/finance/monthly")
def finance_monthly(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Oylik moliyaviy kesim — o'quvchilar tafsiloti bilan."""
    data = _finance_month(db, month, year, with_students=True)
    _attach_unpaid_streaks(db, data)
    return data


# ── Kassa (naqd oqim) ────────────────────────────────────────────────────────
#
# "Moliya hisoboti" (`/finance/monthly`) HISOB oyi bo'yicha ishlaydi: to'lov
# qaysi oy uchun qilingan bo'lsa, o'sha oyga yoziladi. Kassa esa boshqa
# savolga javob beradi — "bugun sandiqqa qancha tushdi va qancha chiqdi?".
# Shuning uchun bu yerda HAR DOIM haqiqiy harakat sanasi olinadi:
#     kirim  → `payments.paid_at`   (pul qachon qabul qilingan)
#     chiqim → `expenses.created_at` (xarajat qachon yozilgan)
# Masalan avgust oyi uchun 10-sentyabrda kelgan to'lov moliya hisobotida
# avgustda, kassada esa 10-sentyabrda ko'rinadi — ikkalasi ham to'g'ri,
# chunki savol boshqa.
#
# Sanalar bazada naive UTC, foydalanuvchi esa Toshkent kunini ko'radi —
# guruhlash `tz.to_local()` orqali, filtrlar `tz.day_bounds()/month_bounds()`
# orqali (aks holda kechqurun 19:00 dan keyingi harakat ertangi kunga tushardi).


def _cash_totals(db: Session, start: Optional[datetime], end: Optional[datetime]) -> tuple:
    """[start, end) naive UTC oralig'idagi kirim va chiqim yig'indisi.

    `start=None` — boshidan; `end=None` — oxirigacha (umumiy qoldiq uchun)."""
    pay_q = db.query(func.sum(models.Payment.amount))
    exp_q = db.query(func.sum(models.Expense.amount))
    if start is not None:
        pay_q = pay_q.filter(models.Payment.paid_at >= start)
        exp_q = exp_q.filter(models.Expense.created_at >= start)
    if end is not None:
        pay_q = pay_q.filter(models.Payment.paid_at < end)
        exp_q = exp_q.filter(models.Expense.created_at < end)
    return (pay_q.scalar() or Decimal(0), exp_q.scalar() or Decimal(0))


def _cash_day_snapshot(db: Session, d: date) -> dict:
    """Bitta Toshkent kunining kirim/chiqimi (Bugun / Kecha kartalari uchun)."""
    start, end = tz.day_bounds(d)
    income, expense = _cash_totals(db, start, end)
    pay_count = db.query(func.count(models.Payment.id)).filter(
        models.Payment.paid_at >= start, models.Payment.paid_at < end).scalar() or 0
    exp_count = db.query(func.count(models.Expense.id)).filter(
        models.Expense.created_at >= start, models.Expense.created_at < end).scalar() or 0
    return {
        "date": d.isoformat(),
        "income": float(income),
        "expense": float(expense),
        "net": float(income - expense),
        "payment_count": pay_count,
        "expense_count": exp_count,
    }


@app.get("/cashbox")
def cashbox_overview(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Kassa — kun kesimida kirim/chiqim va qoldiq (faqat superadmin).

    `days` — oyning har bir kuni (joriy oyda bugungacha), harakatsiz kunlar
    ham nol bilan qaytadi: "o'sha kuni umuman pul tushmagan" degan javob ham
    hisobot uchun kerak. Har kunning `balance` maydoni — o'sha kun oxiridagi
    kassa qoldig'i (oy boshida 0 dan yurgizilgan — oldingi oylardan qoldiq
    ko'chirilmaydi, har oy kassa 0 dan boshlanadi).
    """
    m_start, m_end = tz.month_bounds(year, month)

    # Kassa har oy 0 dan boshlanadi — oldingi oylarning qoldig'i bu oyga
    # ko'chirilmaydi, faqat shu oyning o'zida qabul qilingan/chiqarilgan pul
    # hisoblanadi.
    opening = Decimal(0)

    pay_rows = (
        db.query(models.Payment.paid_at, models.Payment.amount)
        .filter(models.Payment.paid_at >= m_start, models.Payment.paid_at < m_end)
        .all()
    )
    exp_rows = (
        db.query(models.Expense.created_at, models.Expense.amount, models.Expense.category)
        .filter(models.Expense.created_at >= m_start, models.Expense.created_at < m_end)
        .all()
    )

    buckets: dict[date, dict] = {}

    def bucket(d: date) -> dict:
        return buckets.setdefault(d, {
            "income": Decimal(0), "expense": Decimal(0),
            "payment_count": 0, "expense_count": 0,
        })

    month_income = Decimal(0)
    month_expense = Decimal(0)
    salary_expense = Decimal(0)

    for paid_at, amount in pay_rows:
        b = bucket(tz.to_local(paid_at).date())
        b["income"] += amount
        b["payment_count"] += 1
        month_income += amount

    for created_at, amount, category in exp_rows:
        b = bucket(tz.to_local(created_at).date())
        b["expense"] += amount
        b["expense_count"] += 1
        month_expense += amount
        if category == 'salary':
            salary_expense += amount

    # Oyning kunlari: joriy oyda kelajakdagi (hali kelmagan) kunlar
    # ko'rsatilmaydi — ular bo'sh qator sifatida jadvalni cho'zardi.
    today = tz.today()
    last_day = calendar.monthrange(year, month)[1]
    if (year, month) == (today.year, today.month):
        last_day = today.day
    elif (year, month) > (today.year, today.month):
        last_day = 0

    days = []
    running = opening
    for day_num in range(1, last_day + 1):
        d = date(year, month, day_num)
        b = buckets.get(d)
        income = b["income"] if b else Decimal(0)
        expense = b["expense"] if b else Decimal(0)
        running += income - expense
        days.append({
            "date": d.isoformat(),
            "weekday": d.weekday(),          # 0 — dushanba
            "income": float(income),
            "expense": float(expense),
            "net": float(income - expense),
            "balance": float(running),
            "payment_count": b["payment_count"] if b else 0,
            "expense_count": b["expense_count"] if b else 0,
        })

    total_in, total_out = _cash_totals(db, None, None)

    return {
        "month": month,
        "year": year,
        "today": _cash_day_snapshot(db, today),
        "yesterday": _cash_day_snapshot(db, today - timedelta(days=1)),
        "opening_balance": float(opening),
        "month_income": float(month_income),
        "month_expense": float(month_expense),
        "month_salary_expense": float(salary_expense),
        "month_other_expense": float(month_expense - salary_expense),
        "month_net": float(month_income - month_expense),
        "closing_balance": float(opening + month_income - month_expense),
        # Kassa qoldig'i — FAQAT tanlangan oy bo'yicha (kirim - chiqim).
        # Oldingi oylardan qoldiq ko'chirilmaydi, har oy 0 dan boshlanadi.
        "balance": float(month_income - month_expense),
        "total_income": float(total_in),
        "total_expense": float(total_out),
        "days": days,
    }


@app.get("/cashbox/day")
def cashbox_day(
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Bir kunning kassa tafsiloti — har bir kirim va chiqim alohida qator."""
    start, end = tz.day_bounds(target_date)

    payments = (
        db.query(models.Payment)
        .options(joinedload(models.Payment.student), joinedload(models.Payment.group),
                 joinedload(models.Payment.recorded_by))
        .filter(models.Payment.paid_at >= start, models.Payment.paid_at < end)
        .order_by(models.Payment.paid_at)
        .all()
    )
    expenses = (
        db.query(models.Expense)
        .options(joinedload(models.Expense.staff))
        .filter(models.Expense.created_at >= start, models.Expense.created_at < end)
        .order_by(models.Expense.created_at)
        .all()
    )

    income = sum((p.amount for p in payments), Decimal(0))
    expense = sum((e.amount for e in expenses), Decimal(0))

    return {
        "date": target_date.isoformat(),
        "income": float(income),
        "expense": float(expense),
        "net": float(income - expense),
        "payments": [{
            "id": p.id,
            "paid_at": p.paid_at,
            "amount": float(p.amount),
            "student_id": p.student_id,
            "student_name": p.student.full_name if p.student else None,
            "group_name": p.group.name if p.group else None,
            # To'lov qaysi oy uchun — kassa sanasidan farq qilishi mumkin
            # (avgust oyi uchun sentyabrda to'langan bo'lsa).
            "for_month": p.month,
            "for_year": p.year,
            "recorded_by": (p.recorded_by.full_name or p.recorded_by.username) if p.recorded_by else None,
            "notes": p.notes,
        } for p in payments],
        "expenses": [{
            "id": e.id,
            "created_at": e.created_at,
            "amount": float(e.amount),
            "name": e.name,
            "category": e.category,
            "staff_name": e.staff_name,
            "for_month": e.month,
            "for_year": e.year,
        } for e in expenses],
    }


@app.get("/groups/{group_id}/camera-attendance")
def group_camera_attendance(
    group_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    """Guruh o'quvchilarining kamera keldi/ketdi tarixi (so'nggi N kun)."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)

    member_ids = [
        gs.student_id for gs in
        db.query(models.GroupStudent.student_id)
        .filter(models.GroupStudent.group_id == group_id, models.GroupStudent.left_at.is_(None))
        .all()
    ]
    if not member_ids:
        return []

    rows = (
        db.query(models.CameraAttendance, models.Student.full_name)
        .join(models.Student, models.Student.id == models.CameraAttendance.student_id)
        .filter(
            models.CameraAttendance.student_id.in_(member_ids),
            models.CameraAttendance.detected_at >= since,
        )
        .order_by(models.CameraAttendance.detected_at.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id":           r.CameraAttendance.id,
            "student_id":   r.CameraAttendance.student_id,
            "student_name": r.full_name,
            "event_type":   r.CameraAttendance.event_type,
            "detected_at":  r.CameraAttendance.detected_at.isoformat(),
        }
        for r in rows
    ]


@app.get("/groups/{group_id}/attendance")
def get_attendance(
    group_id: int,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """Return all attendance records for a group in given month/year."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    # Teacher faqat o'z guruhini ko'ra oladi
    if actor.role == UserRole.teacher.value and group.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")

    all_members = (
        db.query(models.GroupStudent)
        .filter(models.GroupStudent.group_id == group_id)
        .all()
    )
    # O'sha (month,year)da haqiqatan a'zo bo'lganlar — keyin boshqa guruhga
    # o'tgan/chiqarilgan talaba ham o'sha oy uchun davomat tarixida ko'rinishi kerak.
    members = core_calc.members_covering_month(all_members, month, year)
    student_ids = [m.student_id for m in members]

    records = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.group_id == group_id,
            extract("month", models.Attendance.lesson_date) == month,
            extract("year", models.Attendance.lesson_date) == year,
        )
        .all()
    )

    # Unique lesson dates this month
    dates = sorted(set(r.lesson_date for r in records))

    # Build lookup: {student_id: {date: is_present}}
    lookup = {}
    for r in records:
        lookup.setdefault(r.student_id, {})[r.lesson_date] = r.is_present

    students_data = []
    for m in members:
        s = m.student
        row = {
            "student_id": s.id,
            "student_name": s.full_name,
            "phone": s.phone1,
            "joined_at": m.joined_at.isoformat(),
            "dates": {str(d): lookup.get(s.id, {}).get(d) for d in dates},
            "present_count": sum(1 for d in dates if lookup.get(s.id, {}).get(d) is True),
            "absent_count": sum(1 for d in dates if lookup.get(s.id, {}).get(d) is False),
            "total_lessons": len(dates),
        }
        students_data.append(row)

    return {
        "group_id": group_id,
        "group_name": group.name,
        "teacher_name": group.teacher.full_name or group.teacher.username if group.teacher else None,
        "schedule": group.schedule,
        "month": month,
        "year": year,
        "dates": [str(d) for d in dates],
        "students": students_data,
    }


@app.post("/groups/{group_id}/attendance/{lesson_date}")
def save_attendance(
    group_id: int,
    lesson_date: str,
    payload: List[dict],
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_attendance_editor),
):
    """Save attendance for a specific date. payload: [{student_id, is_present}]"""
    try:
        d = date.fromisoformat(lesson_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Sana formati xato (YYYY-MM-DD)")

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    # Teacher faqat o'z guruhida yo'qlama qila oladi
    if actor.role == UserRole.teacher.value and group.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")

    newly_absent: list[int] = []
    newly_present: list[int] = []
    for item in payload:
        sid = item.get("student_id")
        present = item.get("is_present", None)  # True / False / None (belgilanmagan)
        existing = (
            db.query(models.Attendance)
            .filter(
                models.Attendance.group_id == group_id,
                models.Attendance.student_id == sid,
                models.Attendance.lesson_date == d,
            )
            .first()
        )
        if existing:
            if existing.is_present is True and present is False:
                newly_absent.append(sid)
            elif existing.is_present is not True and present is True:
                newly_present.append(sid)
            existing.is_present = present
        else:
            if present is False:
                newly_absent.append(sid)
            elif present is True:
                newly_present.append(sid)
            db.add(models.Attendance(
                group_id=group_id,
                student_id=sid,
                lesson_date=d,
                is_present=present,
            ))

    # Yo'q deb belgilangan bolalarning ota-onalariga bildirishnoma
    for sid in newly_absent:
        notify_parents_of_student(
            db, student_id=sid, ntype="attendance",
            title="Bola darsga kelmadi",
            body=f"{d:%d.%m.%Y} — {group.name} darsida qatnashmadi",
        )
    # "Keldi" belgilanganlarga — Telegram (biriktirilgan user ID bo'lsa)
    if newly_present:
        students_map = {
            s.id: s for s in db.query(models.Student)
            .filter(models.Student.id.in_(newly_present)).all()
        }
        for sid in newly_present:
            s = students_map.get(sid)
            if s and s.telegram_user_id:
                notify_student_telegram(
                    s,
                    f"📚 <b>{s.full_name}</b> bugun darsda qatnashdi\n"
                    f"👥 {group.name}\n📅 {d.strftime('%d.%m.%Y')}",
                )
    db.commit()
    return {"saved": len(payload), "date": lesson_date}


@app.delete("/groups/{group_id}/attendance/{lesson_date}")
def delete_attendance_date(
    group_id: int,
    lesson_date: str,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_attendance_editor),
):
    """Delete all attendance records for a specific date."""
    try:
        d = date.fromisoformat(lesson_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Sana formati xato")

    # Teacher faqat o'z guruhida
    if actor.role == UserRole.teacher.value:
        group = db.query(models.Group).filter(models.Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Guruh topilmadi")
        if group.teacher_id != actor.id:
            raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")

    db.query(models.Attendance).filter(
        models.Attendance.group_id == group_id,
        models.Attendance.lesson_date == d,
    ).delete()
    db.commit()
    return {"deleted": True, "date": lesson_date}


# ── Student visits — Notifications (keldi/ketdi) ─────────────────────────────

def _visit_read(v: models.StudentVisit) -> schemas.StudentVisitRead:
    return schemas.StudentVisitRead(
        id=v.id, student_id=v.student_id,
        student_name=v.student.full_name if v.student else None,
        student_photo=uploads_sign.sign(v.student.photo) if v.student else None,
        kind=v.kind,
        noted_by_name=(v.noted_by.full_name or v.noted_by.username) if v.noted_by else None,
        telegram_sent=v.telegram_sent, telegram_error=v.telegram_error,
        created_at=v.created_at,
    )


@app.get("/visits", response_model=List[schemas.StudentVisitRead])
def list_visits(
    visit_date: Optional[date] = Query(None),
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_crm_access),
):
    q = db.query(models.StudentVisit).options(
        joinedload(models.StudentVisit.student),
        joinedload(models.StudentVisit.noted_by),
    )
    if student_id:
        q = q.filter(models.StudentVisit.student_id == student_id)
    else:
        d = visit_date or tz.today()
        start = datetime(d.year, d.month, d.day)
        q = q.filter(models.StudentVisit.created_at >= start,
                     models.StudentVisit.created_at < start + timedelta(days=1))
    return [_visit_read(v) for v in q.order_by(models.StudentVisit.created_at.desc()).limit(200).all()]


@app.post("/visits", response_model=schemas.StudentVisitRead, status_code=201)
def create_visit(
    payload: schemas.StudentVisitCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_crm_access),
):
    """Keldi/ketdi belgilash + biriktirilgan Telegram ID'ga xabar (rasmi bo'lsa rasm bilan)."""
    s = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")

    v = models.StudentVisit(student_id=s.id, kind=payload.kind, noted_by_id=actor.id)

    time_str = tz.now().strftime("%H:%M")
    if payload.kind == "arrived":
        caption = f"✅ <b>{s.full_name}</b> o'quv markazga keldi\n🕐 {time_str}"
    else:
        caption = f"🏠 <b>{s.full_name}</b> o'quv markazdan ketdi\n🕐 {time_str}"
    ok, err = notify_student_telegram(s, caption)
    v.telegram_sent = ok
    v.telegram_error = err

    db.add(v)
    db.flush()
    write_audit(db, entity_type="student_visit", entity_id=v.id, action="create",
                changed_by_id=actor.id,
                new_value={"student_id": s.id, "kind": payload.kind, "telegram_sent": ok})
    db.commit()
    db.refresh(v)
    return _visit_read(v)


@app.post("/students/{student_id}/photo", response_model=schemas.StudentRead)
async def upload_student_photo(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_crm_access),
):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    contents, ext = await _read_image_upload(file)
    s.photo = _store_upload("students", ext, contents, s.photo)
    db.commit()
    db.refresh(s)
    return _student_read(s)


# ── Special chegirmalar ───────────────────────────────────────────────────────

def _special_read(d: models.SpecialDiscount) -> schemas.SpecialDiscountRead:
    return schemas.SpecialDiscountRead(
        id=d.id, student_id=d.student_id,
        student_name=d.student.full_name if d.student else None,
        group_id=d.group_id,
        group_name=d.group.name if d.group else None,
        kind=d.kind, amount=d.amount, month=d.month, year=d.year,
        reason=d.reason, is_active=d.is_active,
        created_by_name=(d.created_by.full_name or d.created_by.username) if d.created_by else None,
        created_at=d.created_at,
    )


@app.get("/special-discounts", response_model=List[schemas.SpecialDiscountRead])
def list_special_discounts(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    q = db.query(models.SpecialDiscount).options(
        joinedload(models.SpecialDiscount.student),
        joinedload(models.SpecialDiscount.group),
        joinedload(models.SpecialDiscount.created_by),
    )
    if student_id:
        q = q.filter(models.SpecialDiscount.student_id == student_id)
    return [_special_read(d) for d in q.order_by(models.SpecialDiscount.created_at.desc()).all()]


@app.post("/special-discounts", response_model=schemas.SpecialDiscountRead, status_code=201)
def create_special_discount(
    payload: schemas.SpecialDiscountCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_hunter),
):
    s = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    if payload.group_id:
        if not db.query(models.Group).filter(models.Group.id == payload.group_id).first():
            raise HTTPException(status_code=404, detail="Guruh topilmadi")
    if payload.kind == "free_month":
        if not payload.month or not payload.year:
            raise HTTPException(status_code=400, detail="Bepul oy uchun oy va yil kiritilishi kerak")
    if payload.kind == "monthly" and not payload.amount:
        raise HTTPException(status_code=400, detail="Oylik chegirma uchun summa kiritilishi kerak")
    if payload.kind == "one_time":
        if not payload.amount:
            raise HTTPException(status_code=400, detail="Bir martalik chegirma uchun summa kiritilishi kerak")
        if not payload.month or not payload.year:
            raise HTTPException(status_code=400, detail="Bir martalik chegirma uchun oy va yil kiritilishi kerak")

    # Bir xil talaba/guruh/turga ikkinchi marta aktiv chegirma qo'shilib
    # ketmasligi uchun (aks holda ikkalasi ham qo'llanadi — narx ikki marta
    # kamayadi). free_month/one_time uchun oy/yil ham solishtiriladi.
    dup_q = db.query(models.SpecialDiscount).filter(
        models.SpecialDiscount.student_id == payload.student_id,
        models.SpecialDiscount.group_id == payload.group_id,
        models.SpecialDiscount.kind == payload.kind,
        models.SpecialDiscount.is_active == True,  # noqa: E712
    )
    if payload.kind in ("free_month", "one_time"):
        dup_q = dup_q.filter(models.SpecialDiscount.month == payload.month,
                              models.SpecialDiscount.year == payload.year)
    if dup_q.first():
        raise HTTPException(status_code=400, detail="Bu talaba/guruh uchun shunday aktiv chegirma allaqachon mavjud")

    d = models.SpecialDiscount(
        student_id=payload.student_id,
        group_id=payload.group_id,
        kind=payload.kind,
        amount=payload.amount if payload.kind in ("monthly", "one_time") else None,
        month=payload.month if payload.kind in ("free_month", "one_time") else None,
        year=payload.year if payload.kind in ("free_month", "one_time") else None,
        reason=payload.reason,
        created_by_id=actor.id,
    )
    db.add(d)
    db.flush()
    write_audit(db, entity_type="special_discount", entity_id=d.id, action="create",
                changed_by_id=actor.id,
                new_value={"student_id": d.student_id, "group_id": d.group_id, "kind": d.kind,
                           "amount": str(d.amount) if d.amount else None,
                           "month": d.month, "year": d.year, "reason": d.reason})
    db.commit()
    db.refresh(d)
    return _special_read(d)


@app.patch("/special-discounts/{discount_id}", response_model=schemas.SpecialDiscountRead)
def update_special_discount(
    discount_id: int,
    payload: schemas.SpecialDiscountUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_hunter),
):
    d = db.query(models.SpecialDiscount).filter(models.SpecialDiscount.id == discount_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Chegirma topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(d, k)) for k in changes}
    for k, v in changes.items():
        setattr(d, k, v)
    write_audit(db, entity_type="special_discount", entity_id=d.id, action="update",
                changed_by_id=actor.id, old_value=old,
                new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(d)
    return _special_read(d)


@app.delete("/special-discounts/{discount_id}", status_code=204)
def delete_special_discount(discount_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_hunter)):
    d = db.query(models.SpecialDiscount).filter(models.SpecialDiscount.id == discount_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Chegirma topilmadi")
    write_audit(db, entity_type="special_discount", entity_id=d.id, action="delete",
                changed_by_id=actor.id,
                old_value={"student_id": d.student_id, "kind": d.kind,
                           "amount": str(d.amount) if d.amount else None,
                           "month": d.month, "year": d.year})
    db.delete(d)
    db.commit()


# ── Student vacations (talaba ta'tili) ────────────────────────────────────────

def _vacation_read(v: models.StudentVacation) -> schemas.StudentVacationRead:
    return schemas.StudentVacationRead(
        id=v.id, student_id=v.student_id,
        start_date=v.start_date, end_date=v.end_date, reason=v.reason,
        created_by_name=(v.created_by.full_name or v.created_by.username) if v.created_by else None,
        created_at=v.created_at,
    )


@app.get("/students/{student_id}/vacations", response_model=List[schemas.StudentVacationRead])
def list_student_vacations(
    student_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    if not db.query(models.Student).filter(models.Student.id == student_id).first():
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    q = (
        db.query(models.StudentVacation)
        .options(joinedload(models.StudentVacation.created_by))
        .filter(models.StudentVacation.student_id == student_id)
        .order_by(models.StudentVacation.start_date.desc())
    )
    return [_vacation_read(v) for v in q.all()]


@app.post("/students/{student_id}/vacations", response_model=schemas.StudentVacationRead, status_code=201)
def create_student_vacation(
    student_id: int,
    payload: schemas.StudentVacationCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_hunter),
):
    if not db.query(models.Student).filter(models.Student.id == student_id).first():
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    v = models.StudentVacation(
        student_id=student_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        created_by_id=actor.id,
    )
    db.add(v)
    db.flush()
    write_audit(db, entity_type="student_vacation", entity_id=v.id, action="create",
                changed_by_id=actor.id,
                new_value={"student_id": student_id, "start_date": str(v.start_date),
                           "end_date": str(v.end_date), "reason": v.reason})
    db.commit()
    db.refresh(v)
    return _vacation_read(v)


@app.delete("/students/{student_id}/vacations/{vacation_id}", status_code=204)
def delete_student_vacation(
    student_id: int,
    vacation_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_hunter),
):
    v = (
        db.query(models.StudentVacation)
        .filter(models.StudentVacation.id == vacation_id, models.StudentVacation.student_id == student_id)
        .first()
    )
    if not v:
        raise HTTPException(status_code=404, detail="Ta'til yozuvi topilmadi")
    write_audit(db, entity_type="student_vacation", entity_id=v.id, action="delete",
                changed_by_id=actor.id,
                old_value={"student_id": v.student_id, "start_date": str(v.start_date), "end_date": str(v.end_date)})
    db.delete(v)
    db.commit()


# ── Holidays (dam olish kunlari) ──────────────────────────────────────────────

def _holiday_read(h: models.Holiday) -> schemas.HolidayRead:
    return schemas.HolidayRead(
        id=h.id, name=h.name, start_date=h.start_date, end_date=h.end_date,
        created_by_name=(h.created_by.full_name or h.created_by.username) if h.created_by else None,
        created_at=h.created_at,
    )


@app.get("/holidays", response_model=List[schemas.HolidayRead])
def list_holidays(
    year: Optional[int] = Query(None, ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_auth),
):
    q = db.query(models.Holiday).options(joinedload(models.Holiday.created_by))
    if year:
        q = q.filter(models.Holiday.end_date >= date(year, 1, 1),
                     models.Holiday.start_date <= date(year, 12, 31))
    return [_holiday_read(h) for h in q.order_by(models.Holiday.start_date.desc()).all()]


@app.post("/holidays", response_model=schemas.HolidayRead, status_code=201)
def create_holiday(payload: schemas.HolidayCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas")
    h = models.Holiday(
        name=payload.name, start_date=payload.start_date, end_date=payload.end_date,
        created_by_id=actor.id,
    )
    db.add(h)
    db.flush()
    write_audit(db, entity_type="holiday", entity_id=h.id, action="create",
                changed_by_id=actor.id,
                new_value={"name": h.name, "start_date": str(h.start_date), "end_date": str(h.end_date)})
    db.commit()
    db.refresh(h)
    return _holiday_read(h)


@app.delete("/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    h = db.query(models.Holiday).filter(models.Holiday.id == holiday_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Dam olish kuni topilmadi")
    write_audit(db, entity_type="holiday", entity_id=h.id, action="delete",
                changed_by_id=actor.id,
                old_value={"name": h.name, "start_date": str(h.start_date), "end_date": str(h.end_date)})
    db.delete(h)
    db.commit()


# ── Homework (uy vazifasi) + Telegram ─────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def send_telegram_message(chat_id: str, text: str):
    """Guruh Telegram chatiga xabar yuboradi. (ok, error) qaytaradi."""
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN sozlanmagan (.env)"
    try:
        import httpx
        r = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        body = r.json()
        ok = r.status_code == 200 and body.get("ok")
        err = None if ok else str(body.get("description", r.text))[:400]
        bot_client.log_bot_message(chat_id, "out", text=text, message_type="auto_notify", sent_ok=bool(ok))
        return bool(ok), err
    except Exception as e:
        bot_client.log_bot_message(chat_id, "out", text=text, message_type="auto_notify", sent_ok=False)
        return False, str(e)[:400]


def send_telegram_photo(chat_id: str, photo_path: str, caption: str):
    """Rasm + izoh yuboradi. (ok, error) qaytaradi."""
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN sozlanmagan (.env)"
    try:
        import httpx
        with open(photo_path, "rb") as f:
            r = httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
                timeout=15,
            )
        body = r.json()
        ok = r.status_code == 200 and body.get("ok")
        err = None if ok else str(body.get("description", r.text))[:400]
        bot_client.log_bot_message(chat_id, "out", text=caption, message_type="photo", sent_ok=bool(ok))
        return bool(ok), err
    except Exception as e:
        bot_client.log_bot_message(chat_id, "out", text=caption, message_type="photo", sent_ok=False)
        return False, str(e)[:400]


def notify_student_telegram(student: models.Student, caption: str):
    """Talabaga biriktirilgan Telegram ID'ga xabar: rasmi bo'lsa rasm bilan, bo'lmasa matn."""
    if not student.telegram_user_id:
        return False, "Talabaga Telegram user ID biriktirilmagan"
    if student.photo:
        path = os.path.join(UPLOAD_DIR, student.photo)
        if os.path.exists(path):
            return send_telegram_photo(student.telegram_user_id, path, caption)
    return send_telegram_message(student.telegram_user_id, caption)


# ── Investorlar guruhi: kunlik statistika + yangi talaba xabarnomasi ──────────
# Sozlamalar bot.db'dagi umumiy BotSetting (key/value) jadvalida saqlanadi —
# /bot/settings/{key} orqali (require_admin, ya'ni superadmin) CRM'dan boshqariladi.

def _investor_setting(key: str, default: str = "") -> str:
    db = bot_client.BotSessionLocal()
    try:
        row = db.query(bot_client.BotSetting).filter(bot_client.BotSetting.key == key).first()
        return row.value if row and row.value is not None else default
    finally:
        db.close()


def _investor_setting_set(key: str, value: str) -> None:
    db = bot_client.BotSessionLocal()
    try:
        row = db.query(bot_client.BotSetting).filter(bot_client.BotSetting.key == key).first()
        if row is None:
            db.add(bot_client.BotSetting(key=key, value=value))
        else:
            row.value = value
        db.commit()
    finally:
        db.close()


def notify_investor_new_student(student_full_name: str, group_name: str, tariff_name: Optional[str] = None) -> None:
    """Guruhga yangi talaba qo'shilganda investorlar guruhiga xabar yuboradi (sozlamada yoqilgan bo'lsa)."""
    if _investor_setting("investor_new_student_enabled") != "1":
        return
    chat_id = _investor_setting("investor_chat_id")
    if not chat_id:
        return
    lines = [
        "🎓 <b>Yangi talaba qo'shildi</b>",
        f"👤 {student_full_name}",
        f"📚 Guruh: {group_name}",
    ]
    if tariff_name:
        lines.append(f"💳 Tarif: {tariff_name}")
    send_telegram_message(chat_id, "\n".join(lines))


def build_investor_daily_stats_message() -> str:
    """Investorlar uchun kunlik statistika matnini tuzadi (asosiy CRM bazasidan)."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        now = tz.now()
        today = now.date()

        total_students = db.query(func.count(models.Student.id)).scalar() or 0
        active_students = db.query(func.count(models.Student.id)).filter(models.Student.is_active == True).scalar() or 0
        active_groups = db.query(func.count(models.Group.id)).filter(models.Group.is_active == True).scalar() or 0
        new_leads_today = (
            db.query(func.count(models.Lead.id))
            .filter(func.date(models.Lead.created_at) == today)
            .scalar() or 0
        )
        new_students_today = (
            db.query(func.count(models.GroupStudent.id))
            .filter(func.date(models.GroupStudent.joined_at) == today)
            .scalar() or 0
        )
        today_income = (
            db.query(func.sum(models.Payment.amount))
            .filter(func.date(models.Payment.paid_at) == today)
            .scalar() or Decimal(0)
        )
        month_income = (
            db.query(func.sum(models.Payment.amount))
            .filter(models.Payment.month == now.month, models.Payment.year == now.year)
            .scalar() or Decimal(0)
        )

        lines = [
            f"📊 <b>Kunlik statistika — {today.strftime('%d.%m.%Y')}</b>",
            "",
            f"👥 Jami talabalar: {total_students} (faol: {active_students})",
            f"🏫 Faol guruhlar: {active_groups}",
            f"🆕 Bugungi yangi lidlar: {new_leads_today}",
            f"🎓 Bugun qo'shilgan talabalar: {new_students_today}",
            "",
            f"💰 Bugungi tushum: {today_income:,.0f} so'm",
            f"💵 {MONTHS_UZ[now.month]} oyi tushumi: {month_income:,.0f} so'm",
        ]
        return "\n".join(lines)
    finally:
        db.close()


def _investor_scheduler_loop() -> None:
    """Har daqiqada tekshiradi: kunlik statistika yoqilgan va belgilangan vaqt yetgan
    bo'lsa, bugun hali yuborilmagan bo'lsa — yuboradi. pm2 fork rejimida (bitta
    process) ishlaydi, shuning uchun oddiy background thread yetarli."""
    import time
    while True:
        try:
            if _investor_setting("investor_daily_stats_enabled") == "1":
                chat_id = _investor_setting("investor_chat_id")
                target_time = _investor_setting("investor_daily_stats_time", "09:00")
                now = tz.now()
                today_str = now.strftime("%Y-%m-%d")
                if (chat_id and now.strftime("%H:%M") >= target_time
                        and _investor_setting("investor_daily_stats_last_sent") != today_str):
                    send_telegram_message(chat_id, build_investor_daily_stats_message())
                    _investor_setting_set("investor_daily_stats_last_sent", today_str)
        except Exception:
            log.exception("Investor rejalashtiruvchisi xatosi")
        time.sleep(60)


@_on_startup
def start_investor_scheduler(force: bool = False) -> "threading.Thread | None":
    import threading
    if not (SCHEDULERS_ENABLED or force):
        return None
    t = threading.Thread(target=_investor_scheduler_loop, name="investor_scheduler", daemon=True)
    t.start()
    return t


def _homework_read(hw: models.Homework) -> schemas.HomeworkRead:
    return schemas.HomeworkRead(
        id=hw.id, group_id=hw.group_id,
        group_name=hw.group.name if hw.group else None,
        lesson_id=hw.lesson_id, lesson_number=hw.lesson_number,
        lesson_title=hw.lesson_title, text=hw.text, lesson_date=hw.lesson_date,
        created_by_name=(hw.created_by.full_name or hw.created_by.username) if hw.created_by else None,
        created_at=hw.created_at,
        telegram_sent=hw.telegram_sent, telegram_error=hw.telegram_error,
    )


def _check_group_access(db: Session, group_id: int, actor: models.User) -> models.Group:
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    if actor.role == UserRole.teacher.value and group.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")
    return group


@app.get("/groups/{group_id}/next-lesson", response_model=schemas.NextLessonInfo)
def group_next_lesson(group_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    """Metodika bo'yicha navbatdagi dars: raqami, nomi va uy vazifasi (lessons jadvalidan)."""
    group = _check_group_access(db, group_id, actor)
    category = group.stage or 'foundation'
    total = group.course.total_lessons if group.course else schemas.STAGE_TOTAL_LESSONS.get(category, 24)
    completed = core_calc.group_completed_lessons(db, [group_id]).get(group_id, 0)
    next_num = completed + 1
    lesson = db.query(models.Lesson).filter(
        models.Lesson.category == category,
        models.Lesson.lesson_number == next_num,
    ).first()
    return schemas.NextLessonInfo(
        lesson_id=lesson.id if lesson else None,
        lesson_number=next_num,
        lesson_title=lesson.title if lesson else None,
        homework=lesson.homework if lesson else None,
        category=category,
        completed_lessons=completed,
        total_lessons=total,
    )


@app.get("/groups/{group_id}/homeworks", response_model=List[schemas.HomeworkRead])
def list_homeworks(group_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    _check_group_access(db, group_id, actor)
    hws = (
        db.query(models.Homework)
        .options(joinedload(models.Homework.group), joinedload(models.Homework.created_by))
        .filter(models.Homework.group_id == group_id)
        .order_by(models.Homework.lesson_date.desc(), models.Homework.id.desc())
        .limit(30).all()
    )
    return [_homework_read(hw) for hw in hws]


@app.post("/groups/{group_id}/homeworks", response_model=schemas.HomeworkRead, status_code=201)
def create_homework(
    group_id: int,
    payload: schemas.HomeworkCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_attendance_editor),
):
    """Uy vazifasini saqlaydi va guruh Telegram chatiga yuboradi."""
    group = _check_group_access(db, group_id, actor)
    lesson_date = payload.lesson_date or tz.today()

    hw = models.Homework(
        group_id=group_id,
        lesson_id=payload.lesson_id,
        lesson_number=payload.lesson_number,
        lesson_title=payload.lesson_title,
        text=payload.text,
        lesson_date=lesson_date,
        created_by_id=actor.id,
    )

    # Telegram xabari
    lines = [f"📚 <b>{group.name}</b>"]
    if payload.lesson_number:
        title_part = f" — {payload.lesson_title}" if payload.lesson_title else ""
        lines.append(f"📖 {payload.lesson_number}-dars{title_part}")
    elif payload.lesson_title:
        lines.append(f"📖 {payload.lesson_title}")
    lines.append(f"📅 {lesson_date.strftime('%d.%m.%Y')}")
    lines.append("")
    lines.append("📝 <b>Uy vazifasi:</b>")
    lines.append(payload.text)
    message = "\n".join(lines)

    if group.telegram_chat_id:
        ok, err = send_telegram_message(group.telegram_chat_id, message)
        hw.telegram_sent = ok
        hw.telegram_error = err
    else:
        hw.telegram_sent = False
        hw.telegram_error = "Guruhga Telegram chat ID biriktirilmagan"

    db.add(hw)
    db.flush()
    write_audit(db, entity_type="homework", entity_id=hw.id, action="create",
                changed_by_id=actor.id,
                new_value={"group_id": group_id, "lesson_number": payload.lesson_number,
                           "lesson_date": str(lesson_date), "telegram_sent": hw.telegram_sent})
    db.commit()
    db.refresh(hw)
    return _homework_read(hw)


# ── Akademik: baholar / izohlar / sertifikatlar / tadbirlar ──────────────────

def _teacher_group_ids(db: Session, actor: models.User) -> set:
    return {gid for (gid,) in db.query(models.Group.id).filter(models.Group.teacher_id == actor.id).all()}


def _check_academic_target(db: Session, actor: models.User, student_id: int, group_id: Optional[int]) -> None:
    """Talaba/guruh mavjudligini va teacher faqat o'z guruhida ishlashini tekshiradi."""
    if not db.query(models.Student).filter(models.Student.id == student_id).first():
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    if group_id and not db.query(models.Group).filter(models.Group.id == group_id).first():
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    if actor.role == UserRole.teacher.value:
        if not group_id:
            raise HTTPException(status_code=400, detail="O'qituvchi uchun guruh tanlanishi shart")
        if group_id not in _teacher_group_ids(db, actor):
            raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")
        enrolled = db.query(models.GroupStudent).filter(
            models.GroupStudent.group_id == group_id,
            models.GroupStudent.student_id == student_id,
            models.GroupStudent.left_at.is_(None),
        ).first()
        if not enrolled:
            raise HTTPException(status_code=404, detail="Talaba bu guruhda emas")


def _check_academic_owner(db: Session, actor: models.User, group_id: Optional[int]) -> None:
    """Teacher faqat o'z guruhidagi yozuvni o'zgartira oladi/o'chira oladi."""
    if actor.role == UserRole.teacher.value:
        if not group_id or group_id not in _teacher_group_ids(db, actor):
            raise HTTPException(status_code=403, detail="Bu yozuv sizga tegishli emas")


@app.get("/academic/options", response_model=List[schemas.AcademicGroupOption])
def academic_options(db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    """Baho/izoh kiritish uchun guruh→talabalar ro'yxati (teacher — faqat o'z guruhlari)."""
    q = db.query(models.Group).filter(models.Group.is_active.is_(True))
    if actor.role == UserRole.teacher.value:
        q = q.filter(models.Group.teacher_id == actor.id)
    out = []
    for g in q.order_by(models.Group.name.asc()).all():
        students = sorted(
            (m.student for m in g.members
             if m.left_at is None and m.student and m.student.is_active and not m.student.is_archived),
            key=lambda s: s.full_name,
        )
        out.append(schemas.AcademicGroupOption(
            group_id=g.id, group_name=g.name,
            students=[schemas.StudentBrief(id=s.id, full_name=s.full_name) for s in students],
        ))
    return out


# ── Baholar ──

def _grade_read(g: models.Grade) -> schemas.GradeRead:
    return schemas.GradeRead(
        id=g.id, student_id=g.student_id,
        student_name=g.student.full_name if g.student else None,
        group_id=g.group_id, group_name=g.group.name if g.group else None,
        subject=g.subject, score=g.score, max_score=g.max_score,
        exam_type=g.exam_type, exam_date=g.exam_date, comment=g.comment,
        created_by_name=(g.created_by.full_name or g.created_by.username) if g.created_by else None,
        created_at=g.created_at,
    )


@app.get("/grades", response_model=List[schemas.GradeRead])
def list_grades(
    student_id: Optional[int] = Query(None),
    group_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_attendance_editor),
):
    q = db.query(models.Grade).options(
        joinedload(models.Grade.student), joinedload(models.Grade.group),
        joinedload(models.Grade.created_by),
    )
    if actor.role == UserRole.teacher.value:
        q = q.filter(models.Grade.group_id.in_(_teacher_group_ids(db, actor) or {0}))
    if student_id:
        q = q.filter(models.Grade.student_id == student_id)
    if group_id:
        q = q.filter(models.Grade.group_id == group_id)
    return [_grade_read(g) for g in q.order_by(models.Grade.exam_date.desc(), models.Grade.id.desc()).limit(300).all()]


@app.post("/grades", response_model=schemas.GradeRead, status_code=201)
def create_grade(payload: schemas.GradeCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    _check_academic_target(db, actor, payload.student_id, payload.group_id)
    if payload.score > payload.max_score:
        raise HTTPException(status_code=400, detail="Ball maksimal balldan katta bo'lishi mumkin emas")
    g = models.Grade(
        student_id=payload.student_id, group_id=payload.group_id,
        subject=payload.subject, score=payload.score, max_score=payload.max_score,
        exam_type=payload.exam_type, exam_date=payload.exam_date or tz.today(),
        comment=payload.comment, created_by_id=actor.id,
    )
    db.add(g)
    db.flush()
    write_audit(db, entity_type="grade", entity_id=g.id, action="create", changed_by_id=actor.id,
                new_value={"student_id": g.student_id, "subject": g.subject,
                           "score": g.score, "max_score": g.max_score, "exam_date": str(g.exam_date)})
    notify_parents_of_student(
        db, student_id=g.student_id, ntype="announcement",
        title=f"Yangi baho: {g.subject}",
        body=f"Natija: {g.score}/{g.max_score}" + (f" — {g.comment}" if g.comment else ""),
    )
    db.commit()
    db.refresh(g)
    return _grade_read(g)


@app.patch("/grades/{grade_id}", response_model=schemas.GradeRead)
def update_grade(grade_id: int, payload: schemas.GradeUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    g = db.query(models.Grade).filter(models.Grade.id == grade_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Baho topilmadi")
    _check_academic_owner(db, actor, g.group_id)
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(g, k)) for k in changes}
    for k, v in changes.items():
        setattr(g, k, v)
    if g.score > g.max_score:
        raise HTTPException(status_code=400, detail="Ball maksimal balldan katta bo'lishi mumkin emas")
    write_audit(db, entity_type="grade", entity_id=g.id, action="update", changed_by_id=actor.id,
                old_value=old, new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(g)
    return _grade_read(g)


@app.delete("/grades/{grade_id}", status_code=204)
def delete_grade(grade_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    g = db.query(models.Grade).filter(models.Grade.id == grade_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Baho topilmadi")
    _check_academic_owner(db, actor, g.group_id)
    write_audit(db, entity_type="grade", entity_id=g.id, action="delete", changed_by_id=actor.id,
                old_value={"student_id": g.student_id, "subject": g.subject, "score": g.score})
    db.delete(g)
    db.commit()


# ── O'qituvchi izohlari ──

def _feedback_read(f: models.TeacherFeedback) -> schemas.TeacherFeedbackRead:
    return schemas.TeacherFeedbackRead(
        id=f.id, student_id=f.student_id,
        student_name=f.student.full_name if f.student else None,
        group_id=f.group_id, group_name=f.group.name if f.group else None,
        teacher_name=(f.teacher.full_name or f.teacher.username) if f.teacher else None,
        comment=f.comment, created_at=f.created_at,
        status=f.status or "new",
        status_updated_by_name=(f.status_updated_by.full_name or f.status_updated_by.username) if f.status_updated_by else None,
        status_updated_at=f.status_updated_at,
    )


@app.get("/teacher-feedbacks", response_model=List[schemas.TeacherFeedbackRead])
def list_teacher_feedbacks(
    student_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),     # new | resolved | no_answer
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_feedback_viewer),
):
    q = db.query(models.TeacherFeedback).options(
        joinedload(models.TeacherFeedback.student), joinedload(models.TeacherFeedback.group),
        joinedload(models.TeacherFeedback.teacher), joinedload(models.TeacherFeedback.status_updated_by),
    )
    if actor.role == UserRole.teacher.value:
        q = q.filter(models.TeacherFeedback.group_id.in_(_teacher_group_ids(db, actor) or {0}))
    if student_id:
        q = q.filter(models.TeacherFeedback.student_id == student_id)
    if status:
        q = q.filter(models.TeacherFeedback.status == status)
    return [_feedback_read(f) for f in q.order_by(models.TeacherFeedback.created_at.desc()).limit(300).all()]


@app.get("/teacher-feedbacks/new-count")
def teacher_feedbacks_new_count(
    _: models.User = Depends(require_feedback_status),
    db: Session = Depends(get_db),
):
    """Yangi (hal qilinmagan) izohlar soni — sidebar'dagi qizil badge uchun."""
    n = (
        db.query(func.count(models.TeacherFeedback.id))
        .filter(models.TeacherFeedback.status == "new")
        .scalar()
    )
    return {"count": n or 0}


@app.post("/teacher-feedbacks", response_model=schemas.TeacherFeedbackRead, status_code=201)
def create_teacher_feedback(payload: schemas.TeacherFeedbackCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    _check_academic_target(db, actor, payload.student_id, payload.group_id)
    f = models.TeacherFeedback(
        student_id=payload.student_id, group_id=payload.group_id,
        teacher_id=actor.id, comment=payload.comment,
    )
    db.add(f)
    db.flush()
    write_audit(db, entity_type="teacher_feedback", entity_id=f.id, action="create", changed_by_id=actor.id,
                new_value={"student_id": f.student_id, "comment": f.comment[:200]})
    notify_parents_of_student(
        db, student_id=f.student_id, ntype="announcement",
        title="O'qituvchi izohi", body=f.comment[:300],
    )
    # Hunter va Call center yangi izohni kuzatib borishi kerak — qizil badge + notification
    student_name = db.query(models.Student.full_name).filter(models.Student.id == f.student_id).scalar()
    _notify(
        db, user_ids=[u[0] for u in db.query(models.User.id).filter(
            models.User.is_active == True,  # noqa: E712
            models.User.role.in_([UserRole.hunter.value, UserRole.call_center.value]),
            models.User.id != actor.id,
        ).all()],
        title="Yangi o'quvchi izohi",
        body=f"{student_name or 'Talaba'}: {f.comment[:250]}",
        link="/feedbacks", ntype="feedback",
    )
    db.commit()
    db.refresh(f)
    return _feedback_read(f)


@app.patch("/teacher-feedbacks/{feedback_id}", response_model=schemas.TeacherFeedbackRead)
def update_teacher_feedback(feedback_id: int, payload: schemas.TeacherFeedbackUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    f = db.query(models.TeacherFeedback).filter(models.TeacherFeedback.id == feedback_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Izoh topilmadi")
    if actor.role == UserRole.teacher.value and f.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu izoh sizga tegishli emas")
    old = f.comment
    f.comment = payload.comment
    write_audit(db, entity_type="teacher_feedback", entity_id=f.id, action="update", changed_by_id=actor.id,
                old_value={"comment": old[:200]}, new_value={"comment": f.comment[:200]})
    db.commit()
    db.refresh(f)
    return _feedback_read(f)


_FEEDBACK_STATUS_LABELS = {
    "new": "Yangi",
    "resolved": "Hal qilindi",
    "no_answer": "Telefonga ota-onasi javob bermadi",
}


@app.patch("/teacher-feedbacks/{feedback_id}/status", response_model=schemas.TeacherFeedbackRead)
def update_teacher_feedback_status(
    feedback_id: int,
    payload: schemas.TeacherFeedbackStatusUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_feedback_status),
):
    """Izoh kuzatuv statusi: hal qilindi / telefonga ota-onasi javob bermadi."""
    f = db.query(models.TeacherFeedback).filter(models.TeacherFeedback.id == feedback_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Izoh topilmadi")
    old = f.status or "new"
    f.status = payload.status
    f.status_updated_by_id = actor.id
    f.status_updated_at = datetime.utcnow()
    write_audit(db, entity_type="teacher_feedback", entity_id=f.id, action="status", changed_by_id=actor.id,
                old_value={"status": old}, new_value={"status": f.status})
    # Izoh egasi (o'qituvchi) natijadan xabardor bo'ladi
    if f.teacher_id and f.teacher_id != actor.id:
        _notify(
            db, user_ids=[f.teacher_id],
            title="Izoh statusi yangilandi",
            body=f"{_FEEDBACK_STATUS_LABELS.get(f.status, f.status)} — {f.comment[:200]}",
            link="/feedbacks", ntype="feedback",
        )
    db.commit()
    db.refresh(f)
    db.refresh(f, attribute_names=["student", "group", "teacher", "status_updated_by"])
    return _feedback_read(f)


@app.delete("/teacher-feedbacks/{feedback_id}", status_code=204)
def delete_teacher_feedback(feedback_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    f = db.query(models.TeacherFeedback).filter(models.TeacherFeedback.id == feedback_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Izoh topilmadi")
    if actor.role == UserRole.teacher.value and f.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu izoh sizga tegishli emas")
    write_audit(db, entity_type="teacher_feedback", entity_id=f.id, action="delete", changed_by_id=actor.id,
                old_value={"student_id": f.student_id, "comment": f.comment[:200]})
    db.delete(f)
    db.commit()


# ── To'lov izohlari (qo'ng'iroq/qarzdorlik eslatmalari) ──

def _payment_note_read(n: models.PaymentNote) -> schemas.PaymentNoteRead:
    return schemas.PaymentNoteRead(
        id=n.id, student_id=n.student_id,
        student_name=n.student.full_name if n.student else None,
        comment=n.comment,
        created_by_name=(n.created_by.full_name or n.created_by.username) if n.created_by else None,
        created_at=n.created_at,
    )


@app.get("/payment-notes", response_model=List[schemas.PaymentNoteRead])
def list_payment_notes(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_crm_access),
):
    q = db.query(models.PaymentNote).options(
        joinedload(models.PaymentNote.student), joinedload(models.PaymentNote.created_by),
    )
    if student_id:
        q = q.filter(models.PaymentNote.student_id == student_id)
    return [_payment_note_read(n) for n in q.order_by(models.PaymentNote.created_at.desc()).limit(300).all()]


@app.post("/payment-notes", response_model=schemas.PaymentNoteRead, status_code=201)
def create_payment_note(payload: schemas.PaymentNoteCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_crm_access)):
    student = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    n = models.PaymentNote(student_id=payload.student_id, comment=payload.comment.strip(), created_by_id=actor.id)
    db.add(n)
    db.flush()
    write_audit(db, entity_type="payment_note", entity_id=n.id, action="create", changed_by_id=actor.id,
                new_value={"student_id": n.student_id, "comment": n.comment[:200]})
    db.commit()
    db.refresh(n)
    db.refresh(n, attribute_names=["student", "created_by"])
    return _payment_note_read(n)


@app.delete("/payment-notes/{note_id}", status_code=204)
def delete_payment_note(note_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_crm_access)):
    n = db.query(models.PaymentNote).filter(models.PaymentNote.id == note_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Izoh topilmadi")
    if actor.role != UserRole.admin.value and n.created_by_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu izoh sizga tegishli emas")
    write_audit(db, entity_type="payment_note", entity_id=n.id, action="delete", changed_by_id=actor.id,
                old_value={"student_id": n.student_id, "comment": n.comment[:200]})
    db.delete(n)
    db.commit()


# ── Sertifikatlar ──

MAX_CERT_PDF_BYTES = 10 * 1024 * 1024  # 10 MB
_CERT_URL_MARKER = "/uploads/certificates/"


def _delete_cert_file_if_local(file_url: str) -> None:
    """Bizning serverga yuklangan PDF bo'lsa — faylni ham o'chiramiz (best-effort)."""
    if _CERT_URL_MARKER not in (file_url or ""):
        return
    filename = file_url.rsplit("/", 1)[-1]
    # Path traversal himoyasi: faqat bizning uuid.pdf formatimiz
    if not filename.endswith(".pdf") or "/" in filename or ".." in filename:
        return
    try:
        os.remove(os.path.join(CERTIFICATES_DIR, filename))
    except OSError:
        pass


@app.post("/certificates/upload")
async def upload_certificate_pdf(
    file: UploadFile = File(...),
    _: models.User = Depends(require_lms_write),
):
    """PDF faylni serverga yuklaydi va public file_url qaytaradi.

    Fayl nomi tasodifiy (uuid) — taxmin qilib bo'lmaydi, shu sababli
    /uploads statikasi authsiz bo'lsa ham sertifikatlar sanab chiqilmaydi.
    """
    contents = await file.read()
    if len(contents) > MAX_CERT_PDF_BYTES:
        raise HTTPException(400, "Fayl hajmi 10 MB dan oshmasin")
    # Content-type'ga ham, fayl nomiga ham ishonmaymiz — magic bytes tekshiramiz
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(400, "Faqat PDF fayl yuklash mumkin")

    filename = f"{uuid4().hex}.pdf"
    with open(os.path.join(CERTIFICATES_DIR, filename), "wb") as f:
        f.write(contents)

    return {"file_url": f"{PUBLIC_BASE_URL}{PUBLIC_API_PREFIX}{_CERT_URL_MARKER}{filename}"}


def _certificate_read(c: models.Certificate) -> schemas.CertificateRead:
    return schemas.CertificateRead(
        id=c.id, student_id=c.student_id,
        student_name=c.student.full_name if c.student else None,
        title=c.title, file_url=c.file_url, issued_at=c.issued_at,
        created_by_name=(c.created_by.full_name or c.created_by.username) if c.created_by else None,
        created_at=c.created_at,
    )


@app.get("/certificates", response_model=List[schemas.CertificateRead])
def list_certificates(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_lms_write),
):
    q = db.query(models.Certificate).options(
        joinedload(models.Certificate.student), joinedload(models.Certificate.created_by),
    )
    if student_id:
        q = q.filter(models.Certificate.student_id == student_id)
    return [_certificate_read(c) for c in q.order_by(models.Certificate.created_at.desc()).limit(300).all()]


@app.post("/certificates", response_model=schemas.CertificateRead, status_code=201)
def create_certificate(payload: schemas.CertificateCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    if not db.query(models.Student).filter(models.Student.id == payload.student_id).first():
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    c = models.Certificate(
        student_id=payload.student_id, title=payload.title,
        file_url=payload.file_url, issued_at=payload.issued_at,
        created_by_id=actor.id,
    )
    db.add(c)
    db.flush()
    write_audit(db, entity_type="certificate", entity_id=c.id, action="create", changed_by_id=actor.id,
                new_value={"student_id": c.student_id, "title": c.title, "file_url": c.file_url})
    notify_parents_of_student(
        db, student_id=c.student_id, ntype="announcement",
        title="Yangi sertifikat", body=c.title,
    )
    db.commit()
    db.refresh(c)
    return _certificate_read(c)


@app.patch("/certificates/{certificate_id}", response_model=schemas.CertificateRead)
def update_certificate(certificate_id: int, payload: schemas.CertificateUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    c = db.query(models.Certificate).filter(models.Certificate.id == certificate_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Sertifikat topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(c, k)) for k in changes}
    old_file_url = c.file_url
    for k, v in changes.items():
        setattr(c, k, v)
    write_audit(db, entity_type="certificate", entity_id=c.id, action="update", changed_by_id=actor.id,
                old_value=old, new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(c)
    if "file_url" in changes and changes["file_url"] != old_file_url:
        _delete_cert_file_if_local(old_file_url)
    return _certificate_read(c)


@app.delete("/certificates/{certificate_id}", status_code=204)
def delete_certificate(certificate_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_lms_write)):
    c = db.query(models.Certificate).filter(models.Certificate.id == certificate_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Sertifikat topilmadi")
    write_audit(db, entity_type="certificate", entity_id=c.id, action="delete", changed_by_id=actor.id,
                old_value={"student_id": c.student_id, "title": c.title})
    file_url = c.file_url
    db.delete(c)
    db.commit()
    _delete_cert_file_if_local(file_url)


# ── Tadbirlar ──

def _event_read(e: models.Event) -> schemas.EventRead:
    return schemas.EventRead(
        id=e.id, title=e.title, description=e.description,
        event_date=e.event_date, location=e.location, is_active=e.is_active,
        created_by_name=(e.created_by.full_name or e.created_by.username) if e.created_by else None,
        created_at=e.created_at,
    )


@app.get("/events", response_model=List[schemas.EventRead])
def list_events(db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    rows = (
        db.query(models.Event).options(joinedload(models.Event.created_by))
        .order_by(models.Event.event_date.desc()).limit(200).all()
    )
    return [_event_read(e) for e in rows]


@app.post("/events", response_model=schemas.EventRead, status_code=201)
def create_event(payload: schemas.EventCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    e = models.Event(
        title=payload.title, description=payload.description,
        event_date=payload.event_date, location=payload.location,
        created_by_id=actor.id,
    )
    db.add(e)
    db.flush()
    write_audit(db, entity_type="event", entity_id=e.id, action="create", changed_by_id=actor.id,
                new_value={"title": e.title, "event_date": str(e.event_date), "location": e.location})
    db.commit()
    db.refresh(e)
    return _event_read(e)


@app.patch("/events/{event_id}", response_model=schemas.EventRead)
def update_event(event_id: int, payload: schemas.EventUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Tadbir topilmadi")
    changes = payload.dict(exclude_unset=True)
    old = {k: str(getattr(e, k)) for k in changes}
    for k, v in changes.items():
        setattr(e, k, v)
    write_audit(db, entity_type="event", entity_id=e.id, action="update", changed_by_id=actor.id,
                old_value=old, new_value={k: str(v) for k, v in changes.items()})
    db.commit()
    db.refresh(e)
    return _event_read(e)


@app.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Tadbir topilmadi")
    write_audit(db, entity_type="event", entity_id=e.id, action="delete", changed_by_id=actor.id,
                old_value={"title": e.title, "event_date": str(e.event_date)})
    db.delete(e)
    db.commit()


# ── Coinlar (o'qituvchi rag'bati) ────────────────────────────────────────────
# Budjet alohida saqlanmaydi: oylik budjet = COINS_PER_STUDENT × o'qituvchining
# faol guruhlaridagi faol talabalar soni; sarf esa joriy kalendar oyda
# berilganlar yig'indisi. Shu sabab har oyning 1-kunida qoldiq o'z-o'zidan
# to'liq budjetga qaytadi — cron kerak emas.

COINS_PER_STUDENT = int(os.getenv("COINS_PER_STUDENT", "50"))


def _teacher_coin_budget(db: Session, teacher_id: int) -> int:
    """Oylik budjet: 50 coin × o'qituvchi guruhlaridagi har bir faol talaba."""
    student_count = (
        db.query(func.count(func.distinct(models.GroupStudent.student_id)))
        .join(models.Group, models.Group.id == models.GroupStudent.group_id)
        .join(models.Student, models.Student.id == models.GroupStudent.student_id)
        .filter(
            models.Group.teacher_id == teacher_id,
            models.Group.is_active.is_(True),
            models.Student.is_active.is_(True),
            models.Student.is_archived.is_(False),
            models.GroupStudent.left_at.is_(None),
        )
        .scalar()
    ) or 0
    return COINS_PER_STUDENT * student_count


def _coins_spent_this_month(db: Session, teacher_id: int, now: Optional[datetime] = None) -> int:
    """Toshkent oyi ichida sarflangan tangalar.

    `created_at` naive UTC saqlanadi, shuning uchun `extract("month", ...)`
    to'g'ridan-to'g'ri ishlatilmaydi — oy boshidagi birinchi 5 soatlik
    tranzaksiyalar oldingi oyga tushib qolardi.
    """
    now = now or tz.now()
    start_utc, end_utc = tz.month_bounds(now.year, now.month)
    return int(
        db.query(func.coalesce(func.sum(models.CoinTransaction.amount), 0))
        .filter(
            models.CoinTransaction.teacher_id == teacher_id,
            models.CoinTransaction.created_at >= start_utc,
            models.CoinTransaction.created_at < end_utc,
        )
        .scalar()
    )


def _coin_tx_read(t: models.CoinTransaction) -> schemas.CoinTransactionRead:
    return schemas.CoinTransactionRead(
        id=t.id, student_id=t.student_id,
        student_name=t.student.full_name if t.student else None,
        group_name=t.group.name if t.group else None,
        teacher_id=t.teacher_id,
        teacher_name=(t.teacher.full_name or t.teacher.username) if t.teacher else None,
        amount=t.amount, reason=t.reason, created_at=t.created_at,
    )


@app.get("/coins/summary", response_model=schemas.CoinSummary)
def coin_summary(db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    now = tz.now()                      # oy/yil Toshkent taqvimi bo'yicha
    spent = _coins_spent_this_month(db, actor.id, now)
    if actor.role == UserRole.teacher.value:
        budget = _teacher_coin_budget(db, actor.id)
        return schemas.CoinSummary(month=now.month, year=now.year, budget=budget,
                                   spent=spent, remaining=max(0, budget - spent))
    return schemas.CoinSummary(month=now.month, year=now.year, budget=None, spent=spent, remaining=None)


@app.post("/coins/give", response_model=schemas.CoinTransactionRead, status_code=201)
def give_coins(payload: schemas.CoinGive, db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    _check_academic_target(db, actor, payload.student_id, payload.group_id)

    # Teacher uchun oylik budjet nazorati (boshqa rollar cheklanmagan)
    if actor.role == UserRole.teacher.value:
        budget = _teacher_coin_budget(db, actor.id)
        remaining = budget - _coins_spent_this_month(db, actor.id)
        if payload.amount > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Coin yetarli emas: qoldiq {max(0, remaining)} (har oy 1-sanada {budget} ga to'ladi)",
            )

    t = models.CoinTransaction(
        student_id=payload.student_id, teacher_id=actor.id, group_id=payload.group_id,
        amount=payload.amount, reason=payload.reason, created_at=datetime.utcnow(),
    )
    db.add(t)
    db.flush()
    write_audit(db, entity_type="coin", entity_id=t.id, action="create", changed_by_id=actor.id,
                new_value={"student_id": t.student_id, "amount": t.amount, "reason": t.reason})
    notify_parents_of_student(
        db, student_id=t.student_id, ntype="announcement",
        title=f"Farzandingiz {t.amount} coin oldi 🎉",
        body=t.reason or "O'qituvchi rag'bati",
    )
    db.commit()
    db.refresh(t)
    return _coin_tx_read(t)


def _student_coin_total(db: Session, student_id: int) -> int:
    return int(
        db.query(func.coalesce(func.sum(models.CoinTransaction.amount), 0))
        .filter(models.CoinTransaction.student_id == student_id)
        .scalar()
    )


@app.post("/coins/deduct", response_model=schemas.CoinTransactionRead, status_code=201)
def deduct_coins(payload: schemas.CoinDeduct, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    """Talabadan coin yechish (jarima/tuzatish) — faqat admin. Manfiy yozuv sifatida saqlanadi."""
    student = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")

    total = _student_coin_total(db, payload.student_id)
    if payload.amount > total:
        raise HTTPException(status_code=400, detail=f"Talabada faqat {max(0, total)} coin bor — balans manfiy bo'lolmaydi")

    t = models.CoinTransaction(
        student_id=payload.student_id, teacher_id=actor.id, group_id=None,
        amount=-payload.amount, reason=payload.reason, created_at=datetime.utcnow(),
    )
    db.add(t)
    db.flush()
    write_audit(db, entity_type="coin", entity_id=t.id, action="deduct", changed_by_id=actor.id,
                new_value={"student_id": t.student_id, "amount": t.amount, "reason": t.reason})
    notify_parents_of_student(
        db, student_id=t.student_id, ntype="announcement",
        title=f"Farzandingizdan {payload.amount} coin yechildi",
        body=t.reason or "Administratsiya qarori",
    )
    db.commit()
    db.refresh(t)
    return _coin_tx_read(t)


@app.delete("/coins/transactions/{transaction_id}", status_code=204)
def cancel_coin_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_attendance_editor),
):
    """Berilgan/yechilgan coin yozuvini bekor qilish (o'chirish). Teacher — faqat o'zi bergan, admin — barchasi."""
    t = db.query(models.CoinTransaction).filter(models.CoinTransaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Coin yozuvi topilmadi")
    if actor.role == UserRole.teacher.value and t.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Faqat o'zingiz bergan coinni bekor qila olasiz")

    write_audit(db, entity_type="coin", entity_id=t.id, action="cancel", changed_by_id=actor.id,
                old_value={"student_id": t.student_id, "amount": t.amount, "reason": t.reason})
    student_id = t.student_id
    amount = t.amount
    db.delete(t)
    db.flush()
    notify_parents_of_student(
        db, student_id=student_id, ntype="announcement",
        title="Coin operatsiyasi bekor qilindi",
        body=f"{abs(amount)} coin{'lik yozuv' if amount >= 0 else ' yechish'} bekor qilindi",
    )
    db.commit()
    return None


@app.get("/coins/transactions", response_model=List[schemas.CoinTransactionRead])
def list_coin_transactions(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_attendance_editor),
):
    q = db.query(models.CoinTransaction).options(
        joinedload(models.CoinTransaction.student),
        joinedload(models.CoinTransaction.group),
        joinedload(models.CoinTransaction.teacher),
    )
    if actor.role == UserRole.teacher.value:
        q = q.filter(models.CoinTransaction.teacher_id == actor.id)
    if student_id:
        q = q.filter(models.CoinTransaction.student_id == student_id)
    return [_coin_tx_read(t) for t in q.order_by(models.CoinTransaction.created_at.desc()).limit(300).all()]


@app.get("/coins/totals", response_model=List[schemas.StudentCoinTotal])
def coin_totals(db: Session = Depends(get_db), actor: models.User = Depends(require_attendance_editor)):
    """Talabalar bo'yicha umumiy coin reytingi (teacher — faqat o'z guruhlari talabalari)."""
    q = (
        db.query(models.Student.id, models.Student.full_name,
                 func.coalesce(func.sum(models.CoinTransaction.amount), 0).label("total"))
        .join(models.CoinTransaction, models.CoinTransaction.student_id == models.Student.id)
        .group_by(models.Student.id)
    )
    if actor.role == UserRole.teacher.value:
        gids = _teacher_group_ids(db, actor) or {0}
        q = q.join(models.GroupStudent, models.GroupStudent.student_id == models.Student.id) \
             .filter(models.GroupStudent.group_id.in_(gids), models.GroupStudent.left_at.is_(None)) \
             .group_by(models.Student.id)
    rows = q.order_by(func.sum(models.CoinTransaction.amount).desc()).limit(100).all()
    return [schemas.StudentCoinTotal(student_id=r[0], student_name=r[1], total=int(r[2])) for r in rows]


# ═══════════════════════════════════════════════════════
#  LEADS  (Hunter & Call Center CRM)
# ═══════════════════════════════════════════════════════

def _next_reminder_map(db: Session, lead_ids: list) -> dict:
    """Har bir lid uchun eng yaqin bajarilmagan eslatma (lead_id -> (body, due_at))."""
    if not lead_ids:
        return {}
    rows = (
        db.query(models.Reminder.lead_id, models.Reminder.body, models.Reminder.due_at)
        .filter(models.Reminder.lead_id.in_(lead_ids), models.Reminder.status == "pending")
        .order_by(models.Reminder.lead_id, models.Reminder.due_at.asc())
        .all()
    )
    out = {}
    for lead_id, body, due_at in rows:
        if lead_id not in out:
            out[lead_id] = (body, due_at)
    return out


def _next_reminder_for(db: Session, lead_id: int):
    return _next_reminder_map(db, [lead_id]).get(lead_id)


def _lead_read(lead: models.Lead, reminder: Optional[tuple] = None) -> schemas.LeadRead:
    st = lead.stage
    src = lead.source
    return schemas.LeadRead(
        id=lead.id,
        full_name=lead.full_name,
        phone=lead.phone,
        course_interest=lead.course_interest,
        status=lead.status,
        stage_id=lead.stage_id,
        stage_name=st.name if st else None,
        stage_color=st.color if st else None,
        stage_icon=st.icon if st else None,
        stage_kind=st.kind if st else None,
        source_id=lead.source_id,
        source_name=src.name if src else None,
        callback_at=lead.callback_at,
        notes=lead.notes,
        date_of_birth=lead.date_of_birth,
        parent_phone=lead.parent_phone,
        parent2_phone=lead.parent2_phone,
        interested_group_id=lead.interested_group_id,
        interested_group_name=lead.interested_group.name if lead.interested_group else None,
        is_shared=lead.is_shared,
        claimed_by_id=lead.claimed_by_id,
        claimed_by_name=(lead.claimed_by.full_name or lead.claimed_by.username) if lead.claimed_by else None,
        created_by_id=lead.created_by_id,
        created_by_name=lead.created_by.full_name or lead.created_by.username if lead.created_by else None,
        updated_by_name=lead.updated_by.full_name or lead.updated_by.username if lead.updated_by else None,
        referred_by_id=lead.referred_by_id,
        referred_by_name=(lead.referred_by.full_name or lead.referred_by.username) if lead.referred_by else None,
        phone_display=format_phone(lead.phone),
        is_overdue=bool(
            lead.callback_at and lead.callback_at < datetime.utcnow()
            and (st.kind if st else "lead") == "lead"
        ),
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        next_reminder_body=reminder[0] if reminder else None,
        next_reminder_due_at=reminder[1] if reminder else None,
    )


def _log_lead_activity(db, *, lead_id, action, description, author_id=None, meta=None):
    db.add(models.LeadActivity(
        lead_id=lead_id,
        action=action,
        description=description,
        author_id=author_id,
        meta_json=json.dumps(meta, ensure_ascii=False, default=str) if meta else None,
        created_at=datetime.utcnow(),
    ))


def _notify(db, *, user_ids, title, body=None, link=None, ntype="new_lead"):
    now = datetime.utcnow()
    for uid in set(user_ids):
        db.add(models.Notification(
            user_id=uid, notification_type=ntype, title=title,
            body=body, link=link, is_read=False, created_at=now,
        ))


def _crm_recipient_ids(db, exclude_id=None):
    """Yangi lid haqida xabardor qilinadigan foydalanuvchilar (admin + call_center)."""
    rows = (
        db.query(models.User.id)
        .filter(
            models.User.is_active == True,  # noqa: E712
            models.User.role.in_([UserRole.admin.value, UserRole.call_center.value]),
        ).all()
    )
    return [r[0] for r in rows if r[0] != exclude_id]


# 2026-07-26'dan boshlab: superadmin/call_center/hunter qo'lda kiritgan lidlar
# Facebook orqali kelgan deb hisoblanadi (manba avtomatik Facebook'ga o'rnatiladi,
# shu orqali Mirsaidga referral sifatida bog'lanadi).
def _default_source(db) -> Optional[models.LeadSource]:
    """Manba tanlanmaganda ishlatiladigan manba (lead_sources.is_default)."""
    return (
        db.query(models.LeadSource)
        .filter(models.LeadSource.is_active == True, models.LeadSource.is_default == True)  # noqa: E712
        .order_by(models.LeadSource.id.asc()).first()
    )


def _facebook_source(db) -> Optional[models.LeadSource]:
    return db.query(models.LeadSource).filter(models.LeadSource.name == "Facebook").first()


def _current_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _bump_referral_stat(db, referrer_id: Optional[int], *, leads_delta: int = 0,
                        paid_delta: int = 0, period: Optional[str] = None) -> None:
    """Manba egasi (masalan Facebook/Instagram'ni yurituvchi sales) uchun oylik
    statistikani o'zgartiradi — tarix saqlanishi uchun har oy alohida qator.

    `period` berilmasa joriy oy. Hisobni qaytarishda (paid_delta manfiy) u
    dastlab hisoblangan oy bo'lishi kerak, aks holda o'tgan oy qatorida
    ortiqcha son qolib ketadi.
    """
    if not referrer_id:
        return
    period = period or _current_period()
    stat = (
        db.query(models.LeadReferralStat)
        .filter(models.LeadReferralStat.referrer_id == referrer_id, models.LeadReferralStat.period == period)
        .first()
    )
    if not stat:
        stat = models.LeadReferralStat(
            referrer_id=referrer_id, period=period, leads_count=0, paid_count=0,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(stat)
        db.flush()
    stat.leads_count = max(0, stat.leads_count + leads_delta)
    stat.paid_count = max(0, stat.paid_count + paid_delta)
    stat.updated_at = datetime.utcnow()


def _revoke_referral_credit(db, lead: models.Lead) -> None:
    """Lid "To'landi"dan chiqarilsa yoki o'chirilsa — referral to'lov hisobini qaytarish.

    Ilgari `_bump_referral_stat` faqat oshirar edi: lid o'chirilsa ham, bosqichdan
    qaytarilsa ham `paid_count` joyida qolib, statistika haqiqatdan uzilib ketardi.
    """
    if not lead.referral_credited_at:
        return
    _bump_referral_stat(
        db, lead.referred_by_id, paid_delta=-1,
        period=lead.referral_credited_at.strftime("%Y-%m"),
    )
    lead.referral_credited_at = None


def _slugify(name: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    base = "-".join(filter(None, base.split("-"))) or "stage"
    return base[:70]


def _default_stage(db) -> Optional[models.LeadStage]:
    return (
        db.query(models.LeadStage)
        .filter(models.LeadStage.is_archived == False, models.LeadStage.kind == "lead")  # noqa: E712
        .order_by(models.LeadStage.order.asc())
        .first()
    )


def _normalize_phone(phone: Optional[str]) -> str:
    """Solishtirish uchun kalit — mantiq phone_utils'da (facebook_leads ham shuni ishlatadi)."""
    return normalize_phone(phone)


def _find_duplicate_lead(db: Session, phone: Optional[str], exclude_id: Optional[int] = None) -> Optional[models.Lead]:
    """Shu telefonli mavjud lid (formatlash farqi hisobga olinmaydi).

    `phone_key` indeksi bo'yicha izlaydi — butun jadvalni o'qimaydi.
    """
    key = dedup_key(phone)
    if not key:
        return None
    q = db.query(models.Lead).filter(models.Lead.phone_key == key)
    if exclude_id is not None:
        q = q.filter(models.Lead.id != exclude_id)
    return q.order_by(models.Lead.created_at.desc()).first()


_LEAD_LOAD = (
    joinedload(models.Lead.created_by),
    joinedload(models.Lead.updated_by),
    joinedload(models.Lead.claimed_by),
    joinedload(models.Lead.referred_by),
    joinedload(models.Lead.stage),
    joinedload(models.Lead.source),
    joinedload(models.Lead.interested_group),
)


# Referral funnel'dagi quti (node) kaliti -> lead.status ro'yxati. "target" — filtrsiz (hammasi).
_FUNNEL_BUCKET_STATUSES = {
    "canceled": ["rejected"],
    "waiting":  ["called", "no_answer", "callback"],
    "comming":  ["will_come", "demo"],
    "payed":    ["enrolled"],
}


@app.get("/leads", response_model=List[schemas.LeadRead])
def list_leads(
    status: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),      # stage.slug bo'yicha filtr
    source_id: Optional[int] = Query(None),
    pool: bool = Query(False),               # faqat umumiy havza (band qilinmagan)
    today: bool = Query(False),              # faqat bugun kelishi/qo'ng'iroq qilinishi kerak bo'lganlar
    overdue: bool = Query(False),            # vaqti o'tib ketgan, hali yopilmagan lidlar
    search: Optional[str] = Query(None),
    referred_by_id: Optional[int] = Query(None),
    bucket: Optional[str] = Query(None),     # referral funnel qutisi: canceled|waiting|comming|payed|target
    limit: Optional[int] = Query(None, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    q = db.query(models.Lead).options(*_LEAD_LOAD)
    # O'zining referral funnel'ini ko'rayotgan sales — bu attribution ko'rinishi,
    # hozirgi egalik/claim holatidan qat'i nazar hammasi ko'rsatiladi.
    own_referral_view = referred_by_id and actor.role == UserRole.sales.value and referred_by_id == actor.id
    if pool:
        # Umumiy havza: ulashilgan va hali band qilinmagan lidlar
        q = q.filter(models.Lead.is_shared == True, models.Lead.claimed_by_id.is_(None))  # noqa: E712
    elif actor.role == UserRole.sales.value and not own_referral_view:
        # Sales: o'zi yaratgan yoki band qilgan + havzadagi bo'sh lidlar
        q = q.filter(
            (models.Lead.created_by_id == actor.id) |
            (models.Lead.claimed_by_id == actor.id) |
            ((models.Lead.is_shared == True) & (models.Lead.claimed_by_id.is_(None)))  # noqa: E712
        )
    if stage:
        q = q.join(models.LeadStage, models.Lead.stage_id == models.LeadStage.id).filter(models.LeadStage.slug == stage)
    elif status:
        q = q.filter(models.Lead.status == status)
    if source_id:
        q = q.filter(models.Lead.source_id == source_id)
    if referred_by_id:
        q = q.filter(models.Lead.referred_by_id == referred_by_id)
    if bucket and bucket in _FUNNEL_BUCKET_STATUSES:
        q = q.filter(models.Lead.status.in_(_FUNNEL_BUCKET_STATUSES[bucket]))
    if today:
        day_start_utc, day_end_utc = tz.day_bounds(tz.today())
        q = q.filter(models.Lead.callback_at >= day_start_utc, models.Lead.callback_at < day_end_utc)
    if overdue:
        # Vaqti belgilangan, o'tib ketgan va hali yakunlanmagan (won/lost emas) lidlar.
        # Bularni "Bugun" filtri ko'rsatmaydi — shuning uchun alohida ko'rinish.
        open_stage_ids = [
            sid for (sid,) in db.query(models.LeadStage.id)
            .filter(models.LeadStage.kind == "lead").all()
        ]
        q = q.filter(models.Lead.callback_at < datetime.utcnow())
        if open_stage_ids:
            q = q.filter(models.Lead.stage_id.in_(open_stage_ids))
    if search:
        q = q.filter(
            models.Lead.full_name.ilike(f"%{search}%") |
            models.Lead.phone.ilike(f"%{search}%")
        )
    order = models.Lead.callback_at.asc() if overdue else models.Lead.created_at.desc()
    q = q.order_by(order)
    if limit is not None:
        q = q.offset(offset).limit(limit)
    elif offset:
        q = q.offset(offset)
    leads = q.all()
    rmap = _next_reminder_map(db, [l.id for l in leads])
    return [_lead_read(l, rmap.get(l.id)) for l in leads]


@app.get("/leads/stats", response_model=schemas.LeadStatsRead)
def lead_stats(
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    lead_q = db.query(models.Lead)
    if actor.role == UserRole.sales.value:
        lead_q = lead_q.filter(models.Lead.created_by_id == actor.id)
    total = lead_q.count()

    counts = dict(
        lead_q.with_entities(models.Lead.stage_id, func.count(models.Lead.id))
        .group_by(models.Lead.stage_id).all()
    )
    stages = (
        db.query(models.LeadStage)
        .filter(models.LeadStage.is_archived == False)  # noqa: E712
        .order_by(models.LeadStage.order.asc()).all()
    )
    return schemas.LeadStatsRead(
        total=total,
        stages=[
            schemas.LeadStageStat(
                slug=s.slug, name=s.name, color=s.color, icon=s.icon,
                kind=s.kind, order=s.order, count=counts.get(s.id, 0),
            ) for s in stages
        ],
    )


@app.get("/leads/check-phone")
def check_lead_phone(
    phone: str = Query(..., min_length=3),
    exclude_id: Optional[int] = Query(None),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Bu raqam bazada bormi? — formani yuborishdan OLDIN ogohlantirish uchun.

    POST /leads baribir 409 qaytaradi, lekin u xodim butun formani to'ldirib
    bo'lgandan keyin ishlaydi. Bu endpoint raqam yozilayotgan paytda mavjud
    lidni (qaysi bosqichda va kimda ekanini) ko'rsatadi.
    """
    dup = _find_duplicate_lead(db, phone, exclude_id=exclude_id)
    if not dup:
        return {"duplicate": False}
    return {
        "duplicate": True,
        "lead": {
            "id": dup.id,
            "full_name": dup.full_name,
            "phone": dup.phone,
            "status": dup.status,
            "stage_name": dup.stage.name if dup.stage else None,
            "claimed_by_name": dup.claimed_by.full_name if dup.claimed_by else None,
            "created_at": dup.created_at,
        },
    }


@app.post("/leads", response_model=schemas.LeadRead, status_code=201)
def create_lead(
    payload: schemas.LeadCreate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    dup = _find_duplicate_lead(db, payload.phone)
    if dup:
        raise HTTPException(
            409,
            f"Bu raqam bilan lid allaqachon mavjud: {dup.full_name} (#{dup.id})",
        )
    stage = _default_stage(db)
    lead_data = payload.dict()
    # Manba — xodim formada nimani tanlagan bo'lsa o'sha. Tanlanmagan bo'lsa
    # sozlamalardagi "default" manba (bo'lmasa — manbasiz).
    source = None
    if lead_data.get("source_id"):
        source = db.query(models.LeadSource).filter(models.LeadSource.id == lead_data["source_id"]).first()
        if not source:
            raise HTTPException(400, "Bunday manba topilmadi")
    else:
        source = _default_source(db)
        if source:
            lead_data["source_id"] = source.id
    lead = models.Lead(
        **lead_data,
        phone_key=dedup_key(payload.phone),
        status=stage.slug if stage else models.LeadStatus.new.value,
        stage_id=stage.id if stage else None,
        created_by_id=actor.id,
        referred_by_id=source.referrer_id if source else None,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.flush()
    _bump_referral_stat(db, lead.referred_by_id, leads_delta=1)
    _log_lead_activity(
        db, lead_id=lead.id, action="created",
        description=f"Lid qo'shildi: {lead.full_name}", author_id=actor.id,
    )
    _notify(
        db, user_ids=_crm_recipient_ids(db, exclude_id=actor.id),
        title="Yangi lid qo'shildi",
        body=f"{lead.full_name} · {lead.source.name if lead.source else 'manba yo‘q'}",
        link=f"/leads?lead={lead.id}", ntype="new_lead",
    )
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "stage", "source"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


@app.patch("/leads/{lead_id}/status", response_model=schemas.LeadRead)
def update_lead_status(
    lead_id: int,
    payload: schemas.LeadStatusUpdate,
    actor: models.User = Depends(require_call_center),
    db: Session = Depends(get_db),
):
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    old_name = lead.stage.name if lead.stage else lead.status
    old_kind = lead.stage.kind if lead.stage else None
    new_slug = payload.status
    stage = db.query(models.LeadStage).filter(models.LeadStage.slug == new_slug).first()
    if not stage:
        raise HTTPException(404, f"'{new_slug}' bosqichi topilmadi")
    lead.status = new_slug
    lead.stage_id = stage.id
    lead.callback_at = payload.callback_at
    if payload.notes is not None:
        lead.notes = payload.notes
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    new_name = stage.name
    if new_name != old_name:
        _log_lead_activity(
            db, lead_id=lead.id, action="stage_changed",
            description=f"Holat: {old_name} → {new_name}", author_id=actor.id,
            meta={"old": old_name, "new": new_name},
        )
    if stage.kind == "won" and old_kind != "won" and lead.referral_credited_at is None:
        lead.referral_credited_at = datetime.utcnow()
        _bump_referral_stat(db, lead.referred_by_id, paid_delta=1)
    elif old_kind == "won" and stage.kind != "won":
        _revoke_referral_credit(db, lead)
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "stage", "source"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


@app.patch("/leads/{lead_id}/stage", response_model=schemas.LeadRead)
def move_lead_stage(
    lead_id: int,
    payload: schemas.LeadStageMove,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    if actor.role == UserRole.sales.value and lead.created_by_id != actor.id:
        raise HTTPException(403, "Faqat o'z lidingizni o'zgartira olasiz")
    stage = db.query(models.LeadStage).filter(models.LeadStage.id == payload.stage_id).first()
    if not stage:
        raise HTTPException(404, "Bosqich topilmadi")
    old_name = lead.stage.name if lead.stage else lead.status
    old_kind = lead.stage.kind if lead.stage else None
    lead.stage_id = stage.id
    lead.status = stage.slug
    if payload.callback_at is not None:
        lead.callback_at = payload.callback_at
    if payload.notes is not None:
        lead.notes = payload.notes
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    if stage.name != old_name:
        _log_lead_activity(
            db, lead_id=lead.id, action="stage_changed",
            description=f"Holat: {old_name} → {stage.name}", author_id=actor.id,
            meta={"old": old_name, "new": stage.name},
        )
    if stage.kind == "won" and old_kind != "won" and lead.referral_credited_at is None:
        lead.referral_credited_at = datetime.utcnow()
        _bump_referral_stat(db, lead.referred_by_id, paid_delta=1)
    elif old_kind == "won" and stage.kind != "won":
        _revoke_referral_credit(db, lead)
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "stage", "source"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


def _lead_write_guard(lead: models.Lead, actor: models.User) -> None:
    """Sales faqat o'zi yaratgan yoki band qilgan lidni o'zgartira oladi."""
    if actor.role != UserRole.sales.value:
        return
    if lead.created_by_id != actor.id and lead.claimed_by_id != actor.id:
        raise HTTPException(403, "Faqat o'z lidingizni o'zgartira olasiz")


# Tarixda ko'rsatiladigan maydon nomlari
_LEAD_FIELD_LABELS = {
    "full_name": "Ism", "phone": "Telefon", "course_interest": "Kurs",
    "source_id": "Manba", "notes": "Izoh", "callback_at": "Kelish vaqti",
    "date_of_birth": "Tug'ilgan sana", "parent_phone": "Ota-ona telefoni",
    "parent2_phone": "Qo'shimcha telefon", "interested_group_id": "Guruh",
}


@app.patch("/leads/{lead_id}", response_model=schemas.LeadRead)
def update_lead(
    lead_id: int,
    payload: schemas.LeadUpdate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Lid ma'lumotlarini tahrirlash (ism, telefon, manba, izoh va h.k.).

    Shu paytgacha bunday endpoint yo'q edi — telefon xato yozilsa lidni
    o'chirib qaytadan qo'shishdan boshqa yo'l qolmasdi.
    """
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    _lead_write_guard(lead, actor)

    changes = payload.dict(exclude_unset=True)
    if "phone" in changes and changes["phone"]:
        dup = _find_duplicate_lead(db, changes["phone"], exclude_id=lead.id)
        if dup:
            raise HTTPException(409, f"Bu raqam boshqa lidda bor: {dup.full_name} (#{dup.id})")
    if changes.get("source_id"):
        if not db.query(models.LeadSource).filter(models.LeadSource.id == changes["source_id"]).first():
            raise HTTPException(400, "Bunday manba topilmadi")
    if changes.get("interested_group_id"):
        if not db.query(models.Group).filter(models.Group.id == changes["interested_group_id"]).first():
            raise HTTPException(400, "Bunday guruh topilmadi")

    touched = []
    for field, val in changes.items():
        if getattr(lead, field) == val:
            continue
        setattr(lead, field, val)
        touched.append(_LEAD_FIELD_LABELS.get(field, field))
    if "phone" in changes and changes["phone"]:
        lead.phone_key = dedup_key(changes["phone"])
    if not touched:
        return _lead_read(lead, _next_reminder_for(db, lead.id))

    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    _log_lead_activity(
        db, lead_id=lead.id, action="edited",
        description="Tahrirlandi: " + ", ".join(touched), author_id=actor.id,
    )
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "claimed_by", "referred_by", "stage", "source", "interested_group"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


@app.post("/leads/{lead_id}/notes", response_model=schemas.LeadActivityRead, status_code=201)
def add_lead_note(
    lead_id: int,
    payload: schemas.LeadNoteCreate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Lidga sanasiz izoh qoldirish — tarixga yoziladi.

    Ilgari izoh qoldirishning yagona yo'li eslatma yaratish edi, unda esa
    sana majburiy — shuning uchun xodimlar deyarli hech narsa yozmagan.
    """
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    _lead_write_guard(lead, actor)
    body = payload.body.strip()
    if not body:
        raise HTTPException(400, "Izoh bo'sh")
    act = models.LeadActivity(
        lead_id=lead.id, action="note", description=body,
        author_id=actor.id, created_at=datetime.utcnow(),
    )
    db.add(act)
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(act)
    return schemas.LeadActivityRead(
        id=act.id, action=act.action, description=act.description,
        author_name=actor.full_name or actor.username, created_at=act.created_at,
    )


@app.post("/leads/{lead_id}/convert", response_model=schemas.StudentRead, status_code=201)
def convert_lead_to_student(
    lead_id: int,
    payload: schemas.LeadConvert,
    actor: models.User = Depends(require_call_center),
    db: Session = Depends(get_db),
):
    """Lidni talabaga aylantirish va (ixtiyoriy) guruhga qo'shish.

    Shu paytgacha "To'landi" bosqichi hech narsa qilmasdi — xodim Talabalar
    bo'limiga o'tib hamma narsani qo'lda qaytadan kiritishi kerak edi.
    """
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    if is_placeholder_phone(lead.phone):
        raise HTTPException(400, "Lidda haqiqiy telefon raqami yo'q — avval raqamni kiriting")

    key = dedup_key(lead.phone)
    if key:
        existing = next(
            (st for st in db.query(models.Student).filter(models.Student.is_archived == False).all()  # noqa: E712
             if dedup_key(st.phone1) == key),
            None,
        )
        if existing:
            raise HTTPException(409, f"Bu raqam bilan talaba allaqachon bor: {existing.full_name} (#{existing.id})")

    group = None
    if payload.group_id:
        group = db.query(models.Group).filter(models.Group.id == payload.group_id).first()
        if not group:
            raise HTTPException(404, "Guruh topilmadi")

    student = models.Student(
        full_name=lead.full_name,
        phone1=lead.phone,
        father_name=payload.father_name,
        father_phone=lead.parent_phone,
        mother_name=payload.mother_name,
        mother_phone=lead.parent2_phone,
        notes=lead.notes,
        is_active=True,
        is_demo=payload.is_demo,
        created_at=datetime.utcnow(),
    )
    db.add(student)
    db.flush()

    if group:
        db.add(models.GroupStudent(
            group_id=group.id, student_id=student.id,
            tariff_id=payload.tariff_id, joined_at=datetime.utcnow(),
        ))

    write_audit(db, entity_type="student", entity_id=student.id, action="create",
                changed_by_id=actor.id,
                new_value={"full_name": student.full_name, "phone1": student.phone1,
                           "from_lead_id": lead.id})

    # Lidni "won" bosqichiga o'tkazamiz (bo'lsa) va tarixga yozamiz
    won_stage = (
        db.query(models.LeadStage)
        .filter(models.LeadStage.kind == "won", models.LeadStage.is_archived == False)  # noqa: E712
        .order_by(models.LeadStage.order.asc()).first()
    )
    old_kind = lead.stage.kind if lead.stage else None
    if won_stage:
        lead.stage_id = won_stage.id
        lead.status = won_stage.slug
        if old_kind != "won" and lead.referral_credited_at is None:
            lead.referral_credited_at = datetime.utcnow()
            _bump_referral_stat(db, lead.referred_by_id, paid_delta=1)
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    _log_lead_activity(
        db, lead_id=lead.id, action="converted",
        description=(f"Talabaga aylantirildi (#{student.id})"
                     + (f", guruh: {group.name}" if group else "")),
        author_id=actor.id, meta={"student_id": student.id, "group_id": group.id if group else None},
    )
    db.commit()
    db.refresh(student)
    return _student_read(student)


@app.get("/leads/{lead_id}/activities", response_model=List[schemas.LeadActivityRead])
def lead_activities(
    lead_id: int,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    if actor.role == UserRole.sales.value and lead.created_by_id != actor.id:
        raise HTTPException(403, "Ruxsat yo'q")
    acts = (
        db.query(models.LeadActivity)
        .options(joinedload(models.LeadActivity.author))
        .filter(models.LeadActivity.lead_id == lead_id)
        .order_by(models.LeadActivity.created_at.desc()).all()
    )
    return [
        schemas.LeadActivityRead(
            id=a.id, action=a.action, description=a.description,
            author_name=(a.author.full_name or a.author.username) if a.author else None,
            created_at=a.created_at,
        ) for a in acts
    ]


@app.post("/leads/{lead_id}/claim", response_model=schemas.LeadRead)
def claim_lead(
    lead_id: int,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Umumiy havzadagi lidni o'ziga biriktirish."""
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    if lead.claimed_by_id and lead.claimed_by_id != actor.id:
        raise HTTPException(409, "Bu lid allaqachon band qilingan")
    lead.claimed_by_id = actor.id
    lead.claimed_at = datetime.utcnow()
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    actor_name = actor.full_name or actor.username
    _log_lead_activity(
        db, lead_id=lead.id, action="claimed",
        description=f"Lid band qilindi: {actor_name}", author_id=actor.id,
    )
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "claimed_by", "stage", "source", "interested_group"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


@app.post("/leads/{lead_id}/release", response_model=schemas.LeadRead)
def release_lead(
    lead_id: int,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Lidni umumiy havzaga qaytarish (band qilishni bekor qilish)."""
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    is_owner = lead.claimed_by_id == actor.id
    if not is_owner and actor.role not in (UserRole.admin.value, UserRole.hunter.value):
        raise HTTPException(403, "Faqat egasi yoki admin havzaga qaytara oladi")
    lead.claimed_by_id = None
    lead.claimed_at = None
    lead.is_shared = True
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    _log_lead_activity(
        db, lead_id=lead.id, action="released",
        description="Lid umumiy havzaga qaytarildi", author_id=actor.id,
    )
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "claimed_by", "stage", "source", "interested_group"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


@app.post("/leads/{lead_id}/share", response_model=schemas.LeadRead)
def share_lead(
    lead_id: int,
    actor: models.User = Depends(require_call_center),
    db: Session = Depends(get_db),
):
    """Lidni umumiy havzaga chiqarish (admin/call_center)."""
    lead = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    lead.is_shared = True
    lead.claimed_by_id = None
    lead.claimed_at = None
    lead.updated_by_id = actor.id
    lead.updated_at = datetime.utcnow()
    _log_lead_activity(
        db, lead_id=lead.id, action="shared",
        description="Lid umumiy havzaga chiqarildi", author_id=actor.id,
    )
    _notify(
        db, user_ids=[u[0] for u in db.query(models.User.id).filter(
            models.User.is_active == True,  # noqa: E712
            models.User.role.in_([UserRole.hunter.value, UserRole.sales.value]),
        ).all()],
        title="Umumiy havzada yangi lid",
        body=f"{lead.full_name} — band qilish uchun ochiq",
        link=f"/leads?lead={lead.id}", ntype="shared_lead",
    )
    db.commit()
    db.refresh(lead)
    db.refresh(lead, attribute_names=["created_by", "updated_by", "claimed_by", "stage", "source", "interested_group"])
    return _lead_read(lead, _next_reminder_for(db, lead.id))


@app.delete("/leads/{lead_id}", status_code=204)
def delete_lead(
    lead_id: int,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    if actor.role == UserRole.sales.value and lead.created_by_id != actor.id:
        raise HTTPException(403, "Faqat o'z lidingizni o'chira olasiz")
    # SQLite'da FK majburlanmagani uchun ondelete=CASCADE ishlamaydi —
    # bog'liq yozuvlarni o'zimiz tozalaymiz, aks holda yetim qatorlar qoladi.
    db.query(models.Reminder).filter(models.Reminder.lead_id == lead.id).delete(synchronize_session=False)
    db.query(models.FacebookLead).filter(models.FacebookLead.lead_id == lead.id).update(
        {"lead_id": None}, synchronize_session=False
    )
    # Statistika lid bilan birga qaytarilsin (aks holda "to'lagan"lar soni oshib qolaveradi)
    _revoke_referral_credit(db, lead)
    _bump_referral_stat(
        db, lead.referred_by_id, leads_delta=-1,
        period=lead.created_at.strftime("%Y-%m") if lead.created_at else None,
    )
    db.delete(lead)
    db.commit()


# ── Lead stages (pipeline) ────────────────────────────────────────────────────

@app.get("/lead-stages", response_model=List[schemas.LeadStageRead])
def list_lead_stages(
    include_archived: bool = Query(False),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    q = db.query(models.LeadStage)
    if not include_archived:
        q = q.filter(models.LeadStage.is_archived == False)  # noqa: E712
    stages = q.order_by(models.LeadStage.order.asc()).all()
    counts = dict(
        db.query(models.Lead.stage_id, func.count(models.Lead.id))
        .group_by(models.Lead.stage_id).all()
    )
    out = []
    for s in stages:
        r = schemas.LeadStageRead.from_orm(s)
        r.lead_count = counts.get(s.id, 0)
        out.append(r)
    return out


@app.post("/lead-stages", response_model=schemas.LeadStageRead, status_code=201)
def create_lead_stage(
    payload: schemas.LeadStageCreate,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slug = _slugify(payload.name)
    if db.query(models.LeadStage).filter(models.LeadStage.slug == slug).first():
        slug = f"{slug}-{int(datetime.utcnow().timestamp())}"
    max_order = db.query(func.max(models.LeadStage.order)).scalar() or 0
    stage = models.LeadStage(
        name=payload.name, slug=slug, order=max_order + 10,
        color=payload.color, icon=payload.icon, kind=payload.kind,
        created_at=datetime.utcnow(),
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    r = schemas.LeadStageRead.from_orm(stage)
    r.lead_count = 0
    return r


@app.put("/lead-stages/reorder", response_model=List[schemas.LeadStageRead])
def reorder_lead_stages(
    payload: schemas.StageReorder,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    for idx, sid in enumerate(payload.ordered_ids):
        db.query(models.LeadStage).filter(models.LeadStage.id == sid).update({"order": (idx + 1) * 10})
    db.commit()
    return list_lead_stages(include_archived=False, actor=actor, db=db)


@app.put("/lead-stages/{stage_id}", response_model=schemas.LeadStageRead)
def update_lead_stage(
    stage_id: int,
    payload: schemas.LeadStageUpdate,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stage = db.query(models.LeadStage).filter(models.LeadStage.id == stage_id).first()
    if not stage:
        raise HTTPException(404, "Bosqich topilmadi")
    for field, val in payload.dict(exclude_unset=True).items():
        setattr(stage, field, val)
    db.commit()
    db.refresh(stage)
    count = db.query(func.count(models.Lead.id)).filter(models.Lead.stage_id == stage.id).scalar()
    r = schemas.LeadStageRead.from_orm(stage)
    r.lead_count = count
    return r


@app.delete("/lead-stages/{stage_id}", status_code=204)
def delete_lead_stage(
    stage_id: int,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stage = db.query(models.LeadStage).filter(models.LeadStage.id == stage_id).first()
    if not stage:
        raise HTTPException(404, "Bosqich topilmadi")
    in_use = db.query(func.count(models.Lead.id)).filter(models.Lead.stage_id == stage_id).scalar()
    if in_use:
        # Ichida lid bo'lsa o'chirmaymiz — arxivlaymiz
        stage.is_archived = True
        db.commit()
        return
    db.delete(stage)
    db.commit()


# ── Lead sources ──────────────────────────────────────────────────────────────

@app.get("/lead-sources", response_model=List[schemas.LeadSourceRead])
def list_lead_sources(
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.LeadSource)
        .filter(models.LeadSource.is_active == True)  # noqa: E712
        .order_by(models.LeadSource.name.asc()).all()
    )


@app.post("/lead-sources", response_model=schemas.LeadSourceRead, status_code=201)
def create_lead_source(
    payload: schemas.LeadSourceCreate,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    src = models.LeadSource(
        name=payload.name, is_campaign=payload.is_campaign,
        is_active=True, created_at=datetime.utcnow(),
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@app.put("/lead-sources/{source_id}", response_model=schemas.LeadSourceRead)
def update_lead_source(
    source_id: int,
    payload: schemas.LeadSourceUpdate,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    src = db.query(models.LeadSource).filter(models.LeadSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Manba topilmadi")
    for field, val in payload.dict(exclude_unset=True).items():
        setattr(src, field, val)
    db.commit()
    db.refresh(src)
    return src


@app.delete("/lead-sources/{source_id}", status_code=204)
def delete_lead_source(
    source_id: int,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    src = db.query(models.LeadSource).filter(models.LeadSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Manba topilmadi")
    src.is_active = False
    db.commit()


# ── Reminders / tasks ─────────────────────────────────────────────────────────

def _reminder_read(r: models.Reminder) -> schemas.ReminderRead:
    now = datetime.utcnow()
    effective_due = r.snoozed_until or r.due_at
    return schemas.ReminderRead(
        id=r.id,
        lead_id=r.lead_id,
        lead_name=r.lead.full_name if r.lead else None,
        lead_phone=r.lead.phone if r.lead else None,
        assigned_to_id=r.assigned_to_id,
        assigned_to_name=(r.assigned_to.full_name or r.assigned_to.username) if r.assigned_to else None,
        due_at=r.due_at,
        body=r.body,
        kind=r.kind,
        status=r.status,
        snoozed_until=r.snoozed_until,
        is_overdue=r.status == "pending" and effective_due < now,
        created_at=r.created_at,
    )


@app.get("/reminders", response_model=List[schemas.ReminderRead])
def list_reminders(
    status: Optional[str] = Query(None),          # pending | done | dismissed
    lead_id: Optional[int] = Query(None),
    mine: bool = Query(True),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    q = db.query(models.Reminder).options(
        joinedload(models.Reminder.lead),
        joinedload(models.Reminder.assigned_to),
    )
    if lead_id:
        q = q.filter(models.Reminder.lead_id == lead_id)
    if status:
        q = q.filter(models.Reminder.status == status)
    # Har kim o'ziga tegishli / o'zi yaratganini ko'radi; admin — hammasini.
    # Ma'lum bir lid uchun (drawer/tarix) filtr qo'llanmaydi — o'sha lidga
    # kirish huquqi bo'lgan har kim boshqalar yozgan izoh/eslatmalarni ham ko'rishi kerak.
    if mine and not lead_id and actor.role != UserRole.admin.value:
        q = q.filter(
            (models.Reminder.assigned_to_id == actor.id) |
            (models.Reminder.created_by_id == actor.id)
        )
    reminders = q.order_by(models.Reminder.due_at.asc()).all()
    return [_reminder_read(r) for r in reminders]


@app.post("/reminders", response_model=schemas.ReminderRead, status_code=201)
def create_reminder(
    payload: schemas.ReminderCreate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    lead = db.query(models.Lead).filter(models.Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(404, "Lid topilmadi")
    r = models.Reminder(
        lead_id=payload.lead_id,
        assigned_to_id=payload.assigned_to_id or actor.id,
        created_by_id=actor.id,
        due_at=payload.due_at,
        body=payload.body,
        kind=payload.kind,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(r)
    _log_lead_activity(
        db, lead_id=lead.id, action="reminder",
        description=f"Eslatma: {payload.body or payload.kind} ({payload.due_at:%d.%m %H:%M})",
        author_id=actor.id,
    )
    db.commit()
    db.refresh(r)
    db.refresh(r, attribute_names=["lead", "assigned_to"])
    return _reminder_read(r)


@app.patch("/reminders/{reminder_id}", response_model=schemas.ReminderRead)
def update_reminder(
    reminder_id: int,
    payload: schemas.ReminderUpdate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    r = db.query(models.Reminder).options(
        joinedload(models.Reminder.lead),
        joinedload(models.Reminder.assigned_to),
    ).filter(models.Reminder.id == reminder_id).first()
    if not r:
        raise HTTPException(404, "Eslatma topilmadi")
    data = payload.dict(exclude_unset=True)
    for field, val in data.items():
        setattr(r, field, val)
    if data.get("status") == "done" and not r.done_at:
        r.done_at = datetime.utcnow()
    # Muddat surilgan bo'lsa — bildirishnoma yangi vaqtda qaytadan yuborilsin
    if "due_at" in data or "snoozed_until" in data:
        r.notified_at = None
    r.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(r)
    db.refresh(r, attribute_names=["lead", "assigned_to"])
    return _reminder_read(r)


@app.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(
    reminder_id: int,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    r = db.query(models.Reminder).filter(models.Reminder.id == reminder_id).first()
    if not r:
        raise HTTPException(404, "Eslatma topilmadi")
    db.delete(r)
    db.commit()


# ── Eslatma bildirishnomalari ────────────────────────────────────────────────
# Shu paytgacha eslatmalar hech qachon "otmasdi": muddati kelganda hech kimga
# xabar bormasdi, shuning uchun bazadagi eslatmalar muddati o'tgan holda
# osilib qolgan edi. Quyidagi fon jarayoni har daqiqada tekshiradi.

def _reminders_due_tick() -> None:
    from .database import SessionLocal
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = (
            db.query(models.Reminder)
            .options(joinedload(models.Reminder.lead))
            .filter(
                models.Reminder.status == "pending",
                models.Reminder.notified_at.is_(None),
                func.coalesce(models.Reminder.snoozed_until, models.Reminder.due_at) <= now,
            )
            .limit(100)
            .all()
        )
        for r in due:
            target = r.assigned_to_id or r.created_by_id
            lead_name = r.lead.full_name if r.lead else "lid"
            if target:
                db.add(models.Notification(
                    user_id=target,
                    notification_type="reminder_due",
                    title="Eslatma vaqti keldi",
                    body=f"{lead_name} · {r.body or r.kind}",
                    link=f"/leads?lead={r.lead_id}",
                    is_read=False, created_at=now,
                ))
            r.notified_at = now
        if due:
            db.commit()
    except Exception:
        log.exception("Eslatmalar rejalashtiruvchisi xatosi")
        db.rollback()
    finally:
        db.close()


_notif_prune_last: Optional[datetime] = None


def _prune_notifications() -> None:
    """Eski bildirishnomalarni tozalash — jadval cheksiz o'smasin.

    O'qilganlari 14 kundan, o'qilmaganlari 90 kundan keyin o'chadi; egasi
    o'chirilgan foydalanuvchiga tegishli yetim qatorlar ham tozalanadi.
    """
    from .database import SessionLocal
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        db.query(models.Notification).filter(
            models.Notification.is_read == True,  # noqa: E712
            models.Notification.created_at < now - timedelta(days=14),
        ).delete(synchronize_session=False)
        db.query(models.Notification).filter(
            models.Notification.created_at < now - timedelta(days=90),
        ).delete(synchronize_session=False)
        alive_ids = [u[0] for u in db.query(models.User.id).all()]
        if alive_ids:
            db.query(models.Notification).filter(
                ~models.Notification.user_id.in_(alive_ids)
            ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        log.exception("Eski bildirishnomalarni tozalashda xato")
        db.rollback()
    finally:
        db.close()


def _reminder_scheduler_loop() -> None:
    import time
    global _notif_prune_last
    while True:
        _reminders_due_tick()
        if _notif_prune_last is None or (datetime.utcnow() - _notif_prune_last) > timedelta(hours=24):
            _prune_notifications()
            _notif_prune_last = datetime.utcnow()
        time.sleep(60)


@_on_startup
def start_reminder_scheduler(force: bool = False) -> "threading.Thread | None":
    import threading
    if not (SCHEDULERS_ENABLED or force):
        return None
    t = threading.Thread(target=_reminder_scheduler_loop, name="reminder_scheduler", daemon=True)
    t.start()
    return t


@app.get("/leads/comment-stats", response_model=schemas.CommentStatsRead)
def lead_comment_stats(
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Lidlarga yozilgan izohlar statistikasi — nechta, qachondan qachongacha,
    qaysi oyda ko'proq yozilgan.

    Manba — lid tarixidagi `note` yozuvlari (izohlar aynan shu yerda saqlanadi).
    Ilgari bu yerda `Reminder.body` sanalardi, ya'ni butunlay boshqa jadval:
    bazada 2 ta eslatma bo'lgani uchun panel doim deyarli bo'sh chiqardi.
    """
    is_note = models.LeadActivity.action == "note"
    base = db.query(models.LeadActivity).filter(is_note)
    total = base.count()
    first_at = base.order_by(models.LeadActivity.created_at.asc()).with_entities(models.LeadActivity.created_at).first()
    last_at = base.order_by(models.LeadActivity.created_at.desc()).with_entities(models.LeadActivity.created_at).first()

    # extract() — SQLite'da ham, PostgreSQL'da ham ishlaydi (strftime faqat SQLite'da bor)
    y_expr = extract('year', models.LeadActivity.created_at)
    m_expr = extract('month', models.LeadActivity.created_at)
    month_rows = (
        db.query(y_expr, m_expr, func.count(models.LeadActivity.id))
        .filter(is_note)
        .group_by(y_expr, m_expr)
        .order_by(y_expr, m_expr)
        .all()
    )
    months = [schemas.CommentMonthStat(period=f"{int(y):04d}-{int(m):02d}", count=c)
              for y, m, c in month_rows if y and m]
    busiest = max(months, key=lambda m: m.count) if months else None

    author_rows = (
        db.query(models.User.id, models.User.full_name, models.User.username, func.count(models.LeadActivity.id))
        .join(models.LeadActivity, models.LeadActivity.author_id == models.User.id)
        .filter(is_note)
        .group_by(models.User.id)
        .order_by(func.count(models.LeadActivity.id).desc())
        .limit(10)
        .all()
    )
    by_author = [
        schemas.CommentAuthorStat(author_name=(fn or un), count=c)
        for _, fn, un, c in author_rows
    ]

    return schemas.CommentStatsRead(
        total=total,
        first_at=first_at[0] if first_at else None,
        last_at=last_at[0] if last_at else None,
        months=months,
        busiest_month=busiest,
        by_author=by_author,
    )


# ── Notifications ─────────────────────────────────────────────────────────────

@app.get("/notifications", response_model=List[schemas.NotificationRead])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(30, le=100),
    actor: models.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    q = db.query(models.Notification).filter(models.Notification.user_id == actor.id)
    if unread_only:
        q = q.filter(models.Notification.is_read == False)  # noqa: E712
    return q.order_by(models.Notification.created_at.desc()).limit(limit).all()


@app.get("/notifications/unread-count")
def notifications_unread_count(
    actor: models.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    n = (
        db.query(func.count(models.Notification.id))
        .filter(models.Notification.user_id == actor.id, models.Notification.is_read == False)  # noqa: E712
        .scalar()
    )
    return {"count": n or 0}


@app.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: int,
    actor: models.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    n = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == actor.id,
    ).first()
    if not n:
        raise HTTPException(404, "Topilmadi")
    n.is_read = True
    db.commit()


@app.post("/notifications/read-all", status_code=204)
def mark_all_notifications_read(
    actor: models.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == actor.id,
        models.Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()


# ── Lead analytics ────────────────────────────────────────────────────────────

@app.get("/leads/analytics", response_model=schemas.LeadAnalyticsRead)
def lead_analytics(
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    lead_q = db.query(models.Lead)
    if actor.role == UserRole.sales.value:
        lead_q = lead_q.filter(models.Lead.created_by_id == actor.id)
    total = lead_q.count()

    stage_counts = dict(
        lead_q.with_entities(models.Lead.stage_id, func.count(models.Lead.id))
        .group_by(models.Lead.stage_id).all()
    )
    stages = (
        db.query(models.LeadStage)
        .filter(models.LeadStage.is_archived == False)  # noqa: E712
        .order_by(models.LeadStage.order.asc()).all()
    )
    distribution = [
        schemas.FunnelStep(
            slug=s.slug, name=s.name, color=s.color,
            count=stage_counts.get(s.id, 0),
            percentage=round(stage_counts.get(s.id, 0) / total * 100, 1) if total else 0.0,
        ) for s in stages
    ]
    won = sum(stage_counts.get(s.id, 0) for s in stages if s.kind == "won")
    lost = sum(stage_counts.get(s.id, 0) for s in stages if s.kind == "lost")
    won_stage_ids = [s.id for s in stages if s.kind == "won"]

    # Manba bo'yicha konversiya
    src_total = dict(
        lead_q.with_entities(models.Lead.source_id, func.count(models.Lead.id))
        .group_by(models.Lead.source_id).all()
    )
    src_won = {}
    if won_stage_ids:
        src_won = dict(
            lead_q.filter(models.Lead.stage_id.in_(won_stage_ids))
            .with_entities(models.Lead.source_id, func.count(models.Lead.id))
            .group_by(models.Lead.source_id).all()
        )
    source_names = {s.id: s.name for s in db.query(models.LeadSource).all()}
    sources = []
    for sid, tot in sorted(src_total.items(), key=lambda kv: kv[1], reverse=True):
        enr = src_won.get(sid, 0)
        sources.append(schemas.SourceStat(
            source=source_names.get(sid, "Noma'lum"),
            total=tot, enrolled=enr,
            conversion_rate=round(enr / tot * 100, 1) if tot else 0.0,
        ))

    # Referral (taklif qilingan bolalar) — oylik tarix, manba egasi (masalan
    # Facebook/Instagram'ni yurituvchi sales) bo'yicha. Sales o'z sonini,
    # boshqalar hammasini ko'radi.
    stat_q = (
        db.query(models.LeadReferralStat, models.User.full_name)
        .join(models.User, models.LeadReferralStat.referrer_id == models.User.id)
    )
    if actor.role == UserRole.sales.value:
        stat_q = stat_q.filter(models.LeadReferralStat.referrer_id == actor.id)
    stat_rows = stat_q.order_by(
        models.LeadReferralStat.referrer_id, models.LeadReferralStat.period
    ).all()
    referrer_map: dict[int, schemas.ReferrerStat] = {}
    for stat, referrer_name in stat_rows:
        r = referrer_map.get(stat.referrer_id)
        if not r:
            status_counts = dict(
                db.query(models.Lead.status, func.count(models.Lead.id))
                .filter(models.Lead.referred_by_id == stat.referrer_id)
                .group_by(models.Lead.status).all()
            )
            funnel = schemas.ReferralFunnel(
                target=sum(status_counts.values()),
                **{
                    key: sum(status_counts.get(s, 0) for s in statuses)
                    for key, statuses in _FUNNEL_BUCKET_STATUSES.items()
                },
            )
            r = schemas.ReferrerStat(
                referrer_id=stat.referrer_id, referrer_name=referrer_name,
                total_leads=0, total_paid=0, months=[], funnel=funnel,
            )
            referrer_map[stat.referrer_id] = r
        r.months.append(schemas.ReferralMonth(
            period=stat.period, leads_count=stat.leads_count, paid_count=stat.paid_count,
        ))
        r.total_leads += stat.leads_count
        r.total_paid += stat.paid_count
    referrals = list(referrer_map.values())

    return schemas.LeadAnalyticsRead(
        total=total, won=won, lost=lost,
        conversion=round(won / total * 100, 1) if total else 0.0,
        distribution=distribution, sources=sources, referrals=referrals,
    )


# ── Intake forms (public lead capture) ────────────────────────────────────────

def _intake_read(f: models.IntakeForm) -> schemas.IntakeFormRead:
    return schemas.IntakeFormRead(
        id=f.id, slug=f.slug, name=f.name, title=f.title, description=f.description,
        source_id=f.source_id, source_name=f.source.name if f.source else None,
        is_active=f.is_active, submissions=f.submissions, created_at=f.created_at,
    )


@app.get("/leads/conversion-tree", response_model=schemas.ConversionTreeRead)
def lead_conversion_tree(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Lid oqimi daraxti — bosqichlar, o'tishlar va konversiya ko'rsatkichlari.

    ── Sanalar semantikasi (MUHIM) ────────────────────────────────────────
    Bu yerda uch xil sana aralashib ketishi mumkin edi, shuning uchun har biri
    aniq belgilangan:

      * KOGORTA — tanlangan OYDA YARATILGAN lidlar (`leads.created_at`).
        Daraxtdagi barcha foizlar shu to'plamga nisbatan hisoblanadi.
      * O'TISHLAR — shu kogorta lidlarining bosqich o'zgarishlari
        (`lead_activities.action='stage_changed'`), VAQTIDAN QAT'I NAZAR.
        Sababi: 30-avgustda kelgan lid 2-sentyabrda to'lashi mumkin —
        o'tishni oy chegarasi bilan kesib tashlasak, konversiya kam ko'rinardi.
      * TUSHUM — kogortadagi "won" lidlarga mos keluvchi talabalarning
        HAQIQIY to'lovlari (`payments.amount`), to'lov sanasidan qat'i nazar.

    Oy chegarasi Toshkent vaqtida olinadi (bazada vaqt naive UTC).

    ── Lid → Talaba bog'lanishi ──────────────────────────────────────────
    Bazada `leads.student_id` maydoni yo'q. Bog'lanish ikki manbadan tiklanadi:
      1. `converted` faoliyat yozuvidagi `meta_json.student_id` (aniq manba);
      2. u bo'lmasa — telefon raqami bo'yicha (`dedup_key`), ya'ni tizimning
         o'zi dublikat izlashda ishlatadigan usul.
    Ikkalasi ham topilmasa, lid "studentga o'tkazilmagan" deb belgilanadi —
    bu menejment uchun haqiqiy signal, taxmin emas.
    """
    # ── Davr chegarasi (Toshkent oyi → naive UTC) ──
    period_start, period_end = tz.month_bounds(year, month)

    # ── Ruxsat ────────────────────────────────────────────────────────────
    # Voronka BUTUNLIGICHA ko'rsatiladi — sales uchun ham.
    #
    # Ilgari sales faqat `created_by_id == o'zi` lidlarni ko'rardi. Amalda bu
    # sahifani sales uchun BO'SH qoldirardi: lidlar Facebook formasi orqali
    # keladi va admin/hunter nomidan yoziladi, sales esa ularga referral
    # (`referred_by_id`) sifatida biriktiriladi — ya'ni `created_by_id` hech
    # qachon unga tegishli bo'lmaydi. Konversiya xaritasi shaxsiy natija emas,
    # jamoaning umumiy oqimi haqida, shuning uchun kogorta hamma uchun bir xil.
    #
    # Yashirin qoladigan yagona narsa — OPERATORLAR kesimi (kim nechta
    # qo'ng'iroq qildi, kimning konversiyasi qanday): u xodimlarni bir-biri
    # bilan taqqoslaydi va faqat admin/hunter uchun qoladi.
    can_see_operators = actor.role in (UserRole.admin.value, UserRole.hunter.value)

    leads = db.query(models.Lead).filter(
        models.Lead.created_at >= period_start,
        models.Lead.created_at < period_end,
    ).order_by(models.Lead.id).all()
    lead_ids = [l.id for l in leads]
    total = len(leads)

    # ── Bosqichlar: arxivlangani ham kerak (tarixda uchraydi) ──
    stages = db.query(models.LeadStage).order_by(models.LeadStage.order.asc()).all()
    by_name = {s.name: s for s in stages}
    by_id = {s.id: s for s in stages}

    def stage_key(stage) -> str:
        return f"s{stage.id}"

    # Tarixda uchraydigan, lekin endi mavjud bo'lmagan bosqich nomlari uchun
    # sun'iy tugun — ma'lumot yo'qolmasin.
    ghost_order_base = (stages[-1].order + 10) if stages else 100
    ghosts: dict = {}

    def key_for_name(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        st = by_name.get(name)
        if st:
            return stage_key(st)
        if name not in ghosts:
            ghosts[name] = {
                "key": f"h:{name}", "id": None, "name": name, "slug": None,
                "color": None, "kind": "unknown",
                "order": ghost_order_base + len(ghosts),
            }
        return ghosts[name]["key"]

    node_meta = {stage_key(s): {
        "key": stage_key(s), "id": s.id, "name": s.name, "slug": s.slug,
        "color": s.color, "kind": s.kind, "order": s.order,
        "is_archived": bool(s.is_archived),
    } for s in stages}

    if total == 0:
        return schemas.ConversionTreeRead(
            month=month, year=year, total_leads=0, won_leads=0, lost_leads=0,
            open_leads=0, conversion_rate=0.0, revenue=0.0,
            can_see_operators=can_see_operators,
            scope="all",
        )

    # ── Kogorta faoliyati ──
    acts = (
        db.query(models.LeadActivity)
        .filter(
            models.LeadActivity.lead_id.in_(lead_ids),
            models.LeadActivity.action.in_(["stage_changed", "converted"]),
        )
        .order_by(models.LeadActivity.created_at.asc(), models.LeadActivity.id.asc())
        .all()
    )
    moves_by_lead: dict = {}
    converted_student: dict = {}
    for a in acts:
        if a.action == "converted":
            try:
                meta = json.loads(a.meta_json) if a.meta_json else {}
            except (ValueError, TypeError):
                meta = {}
            if meta.get("student_id"):
                converted_student[a.lead_id] = meta["student_id"]
            continue
        try:
            meta = json.loads(a.meta_json) if a.meta_json else {}
        except (ValueError, TypeError):
            meta = {}
        old, new = meta.get("old"), meta.get("new")
        if not old or not new or old == new:
            continue
        moves_by_lead.setdefault(a.lead_id, []).append((old, new, a.created_at))

    # ── Har bir lid yo'lini tiklaymiz ──
    # Boshlang'ich bosqich alohida yozilmaydi, shuning uchun uni birinchi
    # o'tishning "old" qiymatidan olamiz; o'tish bo'lmasa — joriy bosqichdan.
    visited: dict = {}          # node_key -> set(lead_id)
    trans: dict = {}            # (from_key,to_key) -> set(lead_id)
    won_stage_ids = {s.id for s in stages if s.kind == "won"}
    lost_stage_ids = {s.id for s in stages if s.kind == "lost"}
    first_stage = next((s for s in stages if s.kind == "lead" and not s.is_archived), None)
    first_key = stage_key(first_stage) if first_stage else None

    won_keys = {stage_key(by_id[i]) for i in won_stage_ids if i in by_id}
    won_ids, lost_ids, direct_ids = [], [], []
    conv_days = []

    for lead in leads:
        moves = moves_by_lead.get(lead.id, [])
        cur_stage = by_id.get(lead.stage_id)
        if moves:
            start_key = key_for_name(moves[0][0])
        else:
            start_key = stage_key(cur_stage) if cur_stage else first_key
        touched = set()
        if start_key:
            visited.setdefault(start_key, set()).add(lead.id)
            touched.add(start_key)
        prev_key = start_key
        for old, new, when in moves:
            fk, tk = key_for_name(old), key_for_name(new)
            if not fk or not tk:
                continue
            visited.setdefault(tk, set()).add(lead.id)
            touched.add(fk); touched.add(tk)
            trans.setdefault((fk, tk), set()).add(lead.id)
            prev_key = tk
        # Joriy bosqich tarixda umuman uchramagan bo'lsa ham hisobga olamiz.
        if cur_stage:
            visited.setdefault(stage_key(cur_stage), set()).add(lead.id)
            touched.add(stage_key(cur_stage))

        # "Won" — bosqichga YETIB BORGAN lidlar, joriy bosqichi bo'yicha emas.
        # Aks holda daraxtda "To'landi: 2" turib, konversiya 0% ko'rinardi
        # (lid to'lagandan keyin boshqa bosqichga ko'chirilgan bo'lsa).
        if touched & won_keys:
            won_ids.append(lead.id)
            # Konversiya vaqti: yaratilgandan "won"ga birinchi o'tishgacha.
            won_at = next(
                (w for o, n, w in moves if (by_name.get(n).id if by_name.get(n) else None) in won_stage_ids),
                None,
            )
            if won_at and lead.created_at:
                days = (won_at - lead.created_at).total_seconds() / 86400.0
                if days >= 0:
                    conv_days.append(days)
            # To'g'ridan-to'g'ri konversiya: bitta o'tishda birinchi bosqichdan "won"ga.
            if len(moves) == 1 and start_key == first_key:
                direct_ids.append(lead.id)
        elif lead.stage_id in lost_stage_ids:
            lost_ids.append(lead.id)

    # ── Tushum: kogorta "won" lidlarini talabalarga bog'laymiz ──
    student_of_lead: dict = dict(converted_student)
    unresolved = [l for l in leads if l.id in set(won_ids) and l.id not in student_of_lead]
    if unresolved:
        students = db.query(models.Student.id, models.Student.phone1).all()
        by_phone = {}
        for sid, phone in students:
            k = dedup_key(phone or "")
            if k:
                by_phone.setdefault(k, sid)
        for l in unresolved:
            k = dedup_key(l.phone or "")
            if k and k in by_phone:
                student_of_lead[l.id] = by_phone[k]

    revenue_by_lead: dict = {}
    if student_of_lead:
        sids = list(set(student_of_lead.values()))
        pay_rows = dict(
            db.query(models.Payment.student_id, func.coalesce(func.sum(models.Payment.amount), 0))
            .filter(models.Payment.student_id.in_(sids))
            .group_by(models.Payment.student_id).all()
        )
        for lid, sid in student_of_lead.items():
            revenue_by_lead[lid] = float(pay_rows.get(sid, 0) or 0)
    revenue = float(sum(revenue_by_lead.values()))

    won_set = set(won_ids)
    students_created = len([lid for lid in won_ids if lid in student_of_lead])
    missing_student_ids = [lid for lid in won_ids if lid not in student_of_lead]

    # ── Tugunlar ──
    all_meta = dict(node_meta)
    all_meta.update({g["key"]: g for g in ghosts.values()})
    # Voronka TO'LIQ ko'rsatiladi: tirik bosqich, bu oyda hech bir lid unga
    # kirmagan bo'lsa ham, 0 bilan chiziladi ("Javob bermadi" kabi yangi
    # bosqichlar aks holda umuman ko'rinmasdi va menejer qaysi qadam
    # ishlatilmayotganini bilmasdi). Arxivlangan va "ghost" (endi mavjud
    # bo'lmagan) bosqichlar esa faqat tarixda uchragan bo'lsa qo'shiladi.
    nodes = []
    for key, m in all_meta.items():
        ids = visited.get(key, set())
        if not ids and (m.get("id") is None or m.get("is_archived")):
            continue
        nodes.append(schemas.TreeStageNode(
            key=key, id=m["id"], name=m["name"], slug=m["slug"], color=m["color"],
            kind=m["kind"], order=m["order"], count=len(ids),
            percent=round(len(ids) / total * 100, 1) if total else 0.0,
            lead_ids=sorted(ids),
        ))
    nodes.sort(key=lambda n: (n.order, n.name))
    node_count = {n.key: n.count for n in nodes}

    # ── O'tishlar ──
    def transition_kind(fk: str, tk: str) -> str:
        fm, tm = all_meta.get(fk, {}), all_meta.get(tk, {})
        if tm.get("kind") == "lost":
            return "lost"
        if tm.get("kind") == "won":
            return "won"
        fo, to = fm.get("order", 0), tm.get("order", 0)
        if to < fo:
            return "back"
        # Oraliqda tirik bosqich qolib ketgan bo'lsa — sakrash.
        skipped = [s for s in stages
                   if not s.is_archived and s.kind == "lead" and fo < s.order < to]
        return "skip" if skipped else "normal"

    transitions = []
    for (fk, tk), ids in trans.items():
        base = node_count.get(fk, 0)
        transitions.append(schemas.TreeTransition(
            from_key=fk, to_key=tk,
            from_name=all_meta.get(fk, {}).get("name", "?"),
            to_name=all_meta.get(tk, {}).get("name", "?"),
            count=len(ids),
            percent=round(len(ids) / base * 100, 1) if base else 0.0,
            kind=transition_kind(fk, tk),
            lead_ids=sorted(ids),
        ))
    transitions.sort(key=lambda t: t.count, reverse=True)

    # ── Manba kesimi ──
    src_names = {s.id: s.name for s in db.query(models.LeadSource).all()}
    src_map: dict = {}
    for l in leads:
        e = src_map.setdefault(l.source_id, {"leads": [], "won": 0, "revenue": 0.0})
        e["leads"].append(l.id)
        if l.id in won_set:
            e["won"] += 1
            e["revenue"] += revenue_by_lead.get(l.id, 0.0)
    sources = [
        schemas.TreeSourceStat(
            id=sid, name=src_names.get(sid, "Ko'rsatilmagan"),
            leads=len(e["leads"]), won=e["won"],
            conversion=round(e["won"] / len(e["leads"]) * 100, 1) if e["leads"] else 0.0,
            revenue=e["revenue"], lead_ids=e["leads"],
        )
        for sid, e in src_map.items()
    ]
    sources.sort(key=lambda s: s.leads, reverse=True)

    # ── Operator kesimi (faqat ruxsat bo'lsa) ──
    operators = []
    if can_see_operators:
        user_names = {u.id: (u.full_name or u.username)
                      for u in db.query(models.User).all()}
        op_map: dict = {}
        for l in leads:
            owner = l.claimed_by_id or l.created_by_id
            e = op_map.setdefault(owner, {"leads": 0, "won": 0, "revenue": 0.0})
            e["leads"] += 1
            if l.id in won_set:
                e["won"] += 1
                e["revenue"] += revenue_by_lead.get(l.id, 0.0)
        operators = [
            schemas.TreeOperatorStat(
                id=uid, name=user_names.get(uid, "Noma'lum"),
                leads=e["leads"], won=e["won"],
                conversion=round(e["won"] / e["leads"] * 100, 1) if e["leads"] else 0.0,
                revenue=e["revenue"],
            )
            for uid, e in op_map.items()
        ]
        operators.sort(key=lambda o: (o.won, o.leads), reverse=True)

    # ── Xulosalar (qoidaga asoslangan, matn to'qilmaydi) ──
    insights = []
    lost_trans = [t for t in transitions if t.kind == "lost"]
    if lost_trans:
        worst = max(lost_trans, key=lambda t: t.count)
        insights.append(schemas.TreeInsight(
            kind="bottleneck", title="Eng katta yo'qotish",
            detail=f"{worst.from_name} → {worst.to_name}",
            value=f"{worst.count} ta lid · {worst.percent}%",
            from_key=worst.from_key, to_key=worst.to_key,
        ))
    # Eng katta to'xtash: bosqichga yetgan, lekin undan chiqmagan lidlar.
    stuck = []
    for n in nodes:
        if n.kind != "lead":
            continue
        out = sum(t.count for t in transitions if t.from_key == n.key)
        if n.count and out < n.count:
            stuck.append((n, n.count - out))
    if stuck:
        node, cnt = max(stuck, key=lambda x: x[1])
        insights.append(schemas.TreeInsight(
            kind="warning", title="Eng ko'p to'xtab qolgan bosqich",
            detail=node.name, value=f"{cnt} ta lid shu bosqichda qolgan",
            stage_key=node.key,
        ))
    if direct_ids:
        insights.append(schemas.TreeInsight(
            kind="success", title="To'g'ridan-to'g'ri konversiya",
            detail="Oraliq bosqichlarsiz to'lovga o'tgan lidlar",
            value=f"{len(direct_ids)} ta · {round(len(direct_ids) / total * 100, 1)}%",
        ))
    if missing_student_ids:
        insights.append(schemas.TreeInsight(
            kind="warning", title="Studentga o'tkazilmagan",
            detail="To'landi bosqichida, lekin talaba kartasi yaratilmagan",
            value=f"{len(missing_student_ids)} ta lid",
        ))
    best_src = max((s for s in sources if s.leads >= 5), key=lambda s: s.conversion, default=None)
    if best_src and best_src.won:
        insights.append(schemas.TreeInsight(
            kind="info", title="Eng yaxshi manba",
            detail=best_src.name,
            value=f"{best_src.conversion}% konversiya · {best_src.leads} ta lid",
        ))
    overdue = sum(1 for l in leads
                  if l.callback_at and l.callback_at < datetime.utcnow()
                  and l.stage_id not in won_stage_ids and l.stage_id not in lost_stage_ids)
    if overdue:
        insights.append(schemas.TreeInsight(
            kind="warning", title="Muddati o'tgan qayta aloqa",
            detail="Kelish/qo'ng'iroq vaqti o'tib ketgan, hali yopilmagan lidlar",
            value=f"{overdue} ta lid",
        ))

    conv_days.sort()
    median = None
    if conv_days:
        mid = len(conv_days) // 2
        median = conv_days[mid] if len(conv_days) % 2 else (conv_days[mid - 1] + conv_days[mid]) / 2

    return schemas.ConversionTreeRead(
        month=month, year=year,
        total_leads=total, won_leads=len(won_ids), lost_leads=len(lost_ids),
        open_leads=total - len(won_ids) - len(lost_ids),
        conversion_rate=round(len(won_ids) / total * 100, 1) if total else 0.0,
        revenue=revenue,
        avg_conversion_days=round(sum(conv_days) / len(conv_days), 1) if conv_days else None,
        median_conversion_days=round(median, 1) if median is not None else None,
        avg_revenue_per_won=round(revenue / len(won_ids), 2) if won_ids else None,
        direct_conversions=len(direct_ids), direct_conversion_ids=sorted(direct_ids),
        students_created=students_created,
        won_without_student=len(missing_student_ids),
        won_without_student_ids=sorted(missing_student_ids),
        stages=nodes, transitions=transitions, insights=insights,
        sources=sources, operators=operators,
        can_see_operators=can_see_operators,
        scope="all",
    )


@app.get("/leads/by-ids", response_model=List[schemas.LeadRead])
def leads_by_ids(
    ids: str = Query(..., description="Vergul bilan ajratilgan lid ID'lari"),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Daraxtdagi tugun/o'tish bosilganda — aynan o'sha lidlarni qaytaradi.

    Tugunda mingta lid bo'lishi mumkin, shuning uchun daraxt javobida faqat
    ID'lar keladi; to'liq kartalar esa foydalanuvchi bosgandan keyin,
    sahifalab olinadi.
    """
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()][:200]
    except ValueError:
        raise HTTPException(400, "ID ro'yxati noto'g'ri")
    if not wanted:
        return []
    q = db.query(models.Lead).options(*_LEAD_LOAD).filter(models.Lead.id.in_(wanted))
    if actor.role == UserRole.sales.value:
        q = q.filter(models.Lead.created_by_id == actor.id)
    rows = q.all()
    order = {lid: i for i, lid in enumerate(wanted)}
    rows.sort(key=lambda l: order.get(l.id, 10**6))
    return [_lead_read(l, _next_reminder_for(db, l.id)) for l in rows]


# ── Ish markazi (Work Center) ───────────────────────────────────────────────

OUTCOME_LABELS = {
    "connected":     "Bog'landim",
    "no_answer":     "Javob bermadi",
    "phone_off":     "Telefon o'chiq",
    "callback":      "Qayta qo'ng'iroq kerak",
    "resolved":      "Muammo hal qilindi",
    "will_pay":      "To'lov qiladi",
    "wont_pay":      "To'lov qilmaydi",
    "returns":       "Darsga qaytadi",
    "not_returns":   "Darsga qaytmaydi",
    "interested":    "Qiziqdi",
    "rejected":      "Rad etdi",
    "wrong_number":  "Noto'g'ri raqam",
}
# "Bog'landim" deb sanaladigan natijalar — connect rate shu asosda.
CONNECTED_OUTCOMES = {"connected", "resolved", "will_pay", "wont_pay",
                      "returns", "not_returns", "interested", "rejected"}
NO_ANSWER_OUTCOMES = {"no_answer", "phone_off"}


def _wc_local_now() -> datetime:
    return tz.now()


def _wc_day_bounds(d: date):
    """Toshkent kunining naive UTC chegaralari."""
    return tz.day_bounds(d)


def _task_read(t, state, actor_names) -> schemas.WorkTaskRead:
    """Nomzod vazifa + saqlangan holat → javob modeli."""
    now_utc = datetime.utcnow()
    status = state.status if state else "new"
    due = t.due_at
    if state and state.postponed_to:
        due = state.postponed_to
    return schemas.WorkTaskRead(
        source_key=t.source_key,
        task_type=t.task_type,
        task_label=work_center.TASK_LABELS.get(t.task_type, t.task_type),
        title=t.title, reason=t.reason, priority=t.priority,
        status=status,
        due_at=due,
        overdue=bool(due and due < now_utc and status in ("new", "in_progress", "postponed")),
        entity_type=t.entity_type, entity_id=t.entity_id,
        phone=t.phone, phone2=t.phone2,
        assigned_to_id=t.assigned_to_id,
        assigned_to_name=actor_names.get(t.assigned_to_id),
        meta=t.meta,
        last_outcome=state.outcome if state else None,
        last_note=state.note if state else None,
        completed_at=state.completed_at if state else None,
        postponed_to=state.postponed_to if state else None,
        is_manual=bool(state.is_manual) if state else False,
    )


@app.get("/work-center", response_model=schemas.WorkCenterRead)
def work_center_queue(
    user_id: Optional[int] = Query(None, description="Admin boshqa xodim navbatini ko'rishi uchun"),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Kunlik ish navbati — CRM ma'lumotidan avtomatik yig'iladi.

    Vazifalar bazada saqlanmaydi: ular har so'rovda qayta hisoblanadi va
    `work_tasks` jadvalidagi holat bilan birlashtiriladi (`source_key` orqali).
    Shuning uchun "bir xil eslatma qayta-qayta chiqdi" holati bo'lishi mumkin
    emas — kalit deterministik.
    """
    is_admin = actor.role == UserRole.admin.value
    target = actor
    if user_id and user_id != actor.id:
        if not is_admin:
            raise HTTPException(403, "Boshqa xodim navbatini ko'rish faqat admin uchun")
        target = db.query(models.User).filter(models.User.id == user_id).first()
        if not target:
            raise HTTPException(404, "Xodim topilmadi")

    now_local = _wc_local_now()
    candidates = work_center.generate(db, now_local, _students_payment_map)

    # Ko'rinish filtri — vazifa kimga tegishli.
    visible = [t for t in candidates
               if work_center.visible_to(t.assigned_to_id, target, t.entity_type)]

    keys = [t.source_key for t in visible]
    states = {}
    if keys:
        for row in db.query(models.WorkTask).filter(models.WorkTask.source_key.in_(keys)).all():
            states[row.source_key] = row

    # Qo'lda yaratilgan vazifalar (generator bilmaydi) — ular faqat jadvalda.
    manual_q = db.query(models.WorkTask).filter(
        models.WorkTask.is_manual == True,                       # noqa: E712
        models.WorkTask.status.notin_(["cancelled"]),
    )
    if not is_admin or target.id != actor.id:
        manual_q = manual_q.filter(models.WorkTask.assigned_to_id == target.id)
    manual_rows = manual_q.all()

    names = {u.id: (u.full_name or u.username) for u in db.query(models.User).all()}

    items = [_task_read(t, states.get(t.source_key), names) for t in visible]
    for row in manual_rows:
        if row.source_key in states:
            continue
        now_utc = datetime.utcnow()
        due = row.postponed_to or row.due_at
        items.append(schemas.WorkTaskRead(
            source_key=row.source_key, task_type=row.task_type,
            task_label=work_center.TASK_LABELS.get(row.task_type, row.task_type),
            title=row.title, reason=row.reason, priority=row.priority,
            status=row.status, due_at=due,
            overdue=bool(due and due < now_utc and row.status in ("new", "in_progress", "postponed")),
            entity_type=row.entity_type, entity_id=row.entity_id,
            assigned_to_id=row.assigned_to_id,
            assigned_to_name=names.get(row.assigned_to_id),
            last_outcome=row.outcome, last_note=row.note,
            completed_at=row.completed_at, postponed_to=row.postponed_to,
            is_manual=True,
        ))

    # Keyinga surilgan vazifa yangi vaqti kelgunicha navbatda ko'rinmaydi.
    now_utc = datetime.utcnow()
    open_items, done_items = [], []
    for it in items:
        if it.status == "completed":
            done_items.append(it)
        elif it.status == "cancelled":
            continue
        elif it.status == "skipped":
            continue
        elif it.status == "postponed" and it.postponed_to and it.postponed_to > now_utc:
            continue
        else:
            open_items.append(it)

    open_items.sort(key=lambda t: (
        work_center.PRIORITY_ORDER.get(t.priority, 9),
        not t.overdue,
        t.due_at or datetime.max,
    ))
    done_items.sort(key=lambda t: t.completed_at or datetime.min, reverse=True)

    # Bugungi qo'ng'iroq statistikasi
    day_start, day_end = _wc_day_bounds(now_local.date())
    calls = (
        db.query(models.CallActivity)
        .filter(models.CallActivity.user_id == target.id,
                models.CallActivity.created_at >= day_start,
                models.CallActivity.created_at < day_end).all()
    )
    daily = schemas.DailyCallStats(
        calls=len(calls),
        connected=sum(1 for c in calls if c.outcome in CONNECTED_OUTCOMES),
        no_answer=sum(1 for c in calls if c.outcome in NO_ANSWER_OUTCOMES),
        callbacks=sum(1 for c in calls if c.next_action == "callback"),
        payment_calls=sum(1 for c in calls if c.task_type == work_center.PAYMENT_REMINDER),
        absence_calls=sum(1 for c in calls if c.task_type == work_center.ABSENCE_FOLLOWUP),
        completed_tasks=len([t for t in done_items
                             if t.completed_at and day_start <= t.completed_at < day_end]),
    )

    return schemas.WorkCenterRead(
        date=now_local.date().isoformat(),
        kpi=schemas.WorkCenterKpi(
            total=len(open_items) + len(done_items),
            completed=len(done_items),
            remaining=len(open_items),
            critical=sum(1 for t in open_items if t.priority == "critical"),
            overdue=sum(1 for t in open_items if t.overdue),
        ),
        tasks=open_items,
        completed=done_items[:50],
        daily=daily,
        scope_user_id=target.id,
        can_pick_user=is_admin,
    )


@app.post("/work-center/tasks", response_model=schemas.WorkTaskRead, status_code=201)
def create_work_task(
    payload: schemas.WorkTaskCreate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Qo'lda vazifa yaratish (generator qamramaydigan ishlar uchun)."""
    if payload.priority not in work_center.PRIORITY_ORDER:
        raise HTTPException(400, "Noto'g'ri muhimlik darajasi")
    assigned = payload.assigned_to_id or actor.id
    if assigned != actor.id and actor.role != UserRole.admin.value:
        raise HTTPException(403, "Boshqa xodimga vazifa biriktirish faqat admin uchun")

    key = f"manual:{actor.id}:{int(datetime.utcnow().timestamp() * 1000)}"
    row = models.WorkTask(
        source_key=key, task_type=work_center.GENERAL_TASK,
        assigned_to_id=assigned, created_by_id=actor.id,
        entity_type=payload.entity_type, entity_id=payload.entity_id,
        title=payload.title.strip(), reason=payload.reason,
        priority=payload.priority, status="new",
        due_at=payload.due_at, is_manual=True,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    names = {u.id: (u.full_name or u.username) for u in db.query(models.User).all()}
    return schemas.WorkTaskRead(
        source_key=row.source_key, task_type=row.task_type,
        task_label=work_center.TASK_LABELS[row.task_type],
        title=row.title, reason=row.reason, priority=row.priority,
        status=row.status, due_at=row.due_at,
        entity_type=row.entity_type, entity_id=row.entity_id,
        assigned_to_id=row.assigned_to_id, assigned_to_name=names.get(row.assigned_to_id),
        is_manual=True,
    )


def _upsert_task_state(db, *, source_key, actor, status, note=None, outcome=None,
                       postponed_to=None, task_type=None, title=None,
                       entity_type=None, entity_id=None, priority=None):
    """Vazifa holatini yozadi (yo'q bo'lsa yaratadi).

    `source_key` unikal bo'lgani uchun bitta vazifa uchun bitta qator —
    generator uni necha marta chiqarishidan qat'i nazar.
    """
    row = db.query(models.WorkTask).filter(models.WorkTask.source_key == source_key).first()
    if not row:
        row = models.WorkTask(
            source_key=source_key,
            task_type=task_type or work_center.GENERAL_TASK,
            title=(title or source_key)[:200],
            entity_type=entity_type, entity_id=entity_id,
            priority=priority or "normal",
            assigned_to_id=actor.id, created_by_id=actor.id,
            status="new", created_at=datetime.utcnow(), is_manual=False,
        )
        db.add(row)
    row.status = status
    row.updated_at = datetime.utcnow()
    if note is not None:
        row.note = note
    if outcome is not None:
        row.outcome = outcome
    if status == "completed":
        row.completed_at = datetime.utcnow()
        row.completed_by_id = actor.id
        row.postponed_to = None
    if status == "postponed":
        row.postponed_to = postponed_to
        row.completed_at = None
    return row


@app.patch("/work-center/tasks", response_model=schemas.WorkTaskRead)
def update_work_task(
    source_key: str = Query(..., max_length=160),
    payload: schemas.WorkTaskUpdate = None,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Vazifa holatini o'zgartirish: bajarildi / o'tkazib yuborildi / surildi."""
    allowed = {"new", "in_progress", "completed", "skipped", "postponed", "cancelled"}
    if payload.status not in allowed:
        raise HTTPException(400, "Noto'g'ri holat")
    if payload.status == "postponed" and not payload.postponed_to:
        raise HTTPException(400, "Keyinga surish uchun yangi vaqt kerak")

    existing = db.query(models.WorkTask).filter(models.WorkTask.source_key == source_key).first()
    if existing and existing.assigned_to_id and existing.assigned_to_id != actor.id \
            and actor.role != UserRole.admin.value:
        raise HTTPException(403, "Bu vazifa boshqa xodimga biriktirilgan")

    row = _upsert_task_state(
        db, source_key=source_key, actor=actor, status=payload.status,
        note=payload.note, postponed_to=payload.postponed_to,
        task_type=payload.task_type, title=payload.title,
        entity_type=payload.entity_type, entity_id=payload.entity_id,
        priority=payload.priority,
    )
    db.commit()
    db.refresh(row)
    names = {u.id: (u.full_name or u.username) for u in db.query(models.User).all()}
    return schemas.WorkTaskRead(
        source_key=row.source_key, task_type=row.task_type,
        task_label=work_center.TASK_LABELS.get(row.task_type, row.task_type),
        title=row.title, reason=row.reason, priority=row.priority,
        status=row.status, due_at=row.postponed_to or row.due_at,
        entity_type=row.entity_type, entity_id=row.entity_id,
        assigned_to_id=row.assigned_to_id, assigned_to_name=names.get(row.assigned_to_id),
        last_outcome=row.outcome, last_note=row.note,
        completed_at=row.completed_at, postponed_to=row.postponed_to,
        is_manual=bool(row.is_manual),
    )


# ── Qo'ng'iroq faoliyati ────────────────────────────────────────────────────

def _call_read(c: models.CallActivity, names: dict) -> schemas.CallActivityRead:
    return schemas.CallActivityRead(
        id=c.id, user_id=c.user_id, user_name=names.get(c.user_id),
        entity_type=c.entity_type, entity_id=c.entity_id, entity_name=c.entity_name,
        phone=c.phone, task_type=c.task_type,
        outcome=c.outcome, outcome_label=OUTCOME_LABELS.get(c.outcome, c.outcome),
        note=c.note, next_action=c.next_action, next_action_at=c.next_action_at,
        duration_sec=c.duration_sec, state_before=c.state_before, state_after=c.state_after,
        payment_promise=c.payment_promise, promised_at=c.promised_at,
        created_at=c.created_at, edited_at=c.edited_at,
        edited_by_name=names.get(c.edited_by_id), original_note=c.original_note,
    )


@app.post("/activities/call", response_model=schemas.CallActivityRead, status_code=201)
def log_call(
    payload: schemas.CallActivityCreate,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Qo'ng'iroq natijasini yozish.

    MUHIM: bu yerda lid bosqichi AVTOMATIK o'zgartirilmaydi. Natija "Qiziqdi"
    bo'lsa ham bosqichni tizim o'zi ko'chirmaydi — xodim buni ongli ravishda
    lid kartasida qiladi. Sabab: qo'ng'iroq natijasi taxmin, bosqich esa
    hisobot va maosh hisob-kitobiga ta'sir qiladigan rasmiy holat.

    "Keyingi qadam: qayta qo'ng'iroq" tanlansa, mavjud ESLATMA tizimida
    (`reminders`) yozuv yaratiladi — bu qo'shimcha ma'lumot, mavjud holatni
    buzmaydi.
    """
    if payload.outcome not in OUTCOME_LABELS:
        raise HTTPException(400, "Noma'lum qo'ng'iroq natijasi")
    if payload.entity_type not in ("lead", "student"):
        raise HTTPException(400, "entity_type 'lead' yoki 'student' bo'lishi kerak")

    name = phone = state_before = None
    lead = None
    if payload.entity_type == "lead":
        lead = db.query(models.Lead).options(joinedload(models.Lead.stage)) \
                 .filter(models.Lead.id == payload.entity_id).first()
        if not lead:
            raise HTTPException(404, "Lid topilmadi")
        if actor.role == UserRole.sales.value and lead.created_by_id != actor.id:
            raise HTTPException(403, "Faqat o'z lidingiz bilan ishlay olasiz")
        name, phone = lead.full_name, lead.phone
        state_before = lead.stage.name if lead.stage else lead.status
    else:
        # Talabalar bo'yicha qo'ng'iroq — sales rolida bunday ish yo'q.
        if actor.role == UserRole.sales.value:
            raise HTTPException(403, "Ruxsat yo'q")
        st = db.query(models.Student).filter(models.Student.id == payload.entity_id).first()
        if not st:
            raise HTTPException(404, "Talaba topilmadi")
        name = st.full_name
        phone = st.father_phone or st.mother_phone or st.phone1

    call = models.CallActivity(
        user_id=actor.id,
        entity_type=payload.entity_type, entity_id=payload.entity_id,
        entity_name=name, phone=phone,
        source_key=payload.source_key, task_type=payload.task_type,
        outcome=payload.outcome, note=(payload.note or "").strip() or None,
        next_action=payload.next_action, next_action_at=payload.next_action_at,
        duration_sec=payload.duration_sec,
        state_before=state_before, state_after=state_before,
        payment_promise=payload.payment_promise, promised_at=payload.promised_at,
        created_at=datetime.utcnow(),
    )
    db.add(call)
    db.flush()

    # Lid tarixi ikkiga bo'linib ketmasin — mavjud timeline'ga ham yozamiz.
    if lead is not None:
        desc = f"Qo'ng'iroq: {OUTCOME_LABELS[payload.outcome]}"
        if call.note:
            desc += f" — {call.note}"
        _log_lead_activity(
            db, lead_id=lead.id, action="call", description=desc, author_id=actor.id,
            meta={"outcome": payload.outcome, "call_id": call.id,
                  "next_action": payload.next_action},
        )
        lead.updated_by_id = actor.id
        lead.updated_at = datetime.utcnow()

    # Keyingi qadam "qayta qo'ng'iroq" bo'lsa — eslatma yaratamiz (lid uchun).
    if payload.next_action == "callback" and payload.next_action_at and lead is not None:
        db.add(models.Reminder(
            lead_id=lead.id, assigned_to_id=actor.id, created_by_id=actor.id,
            due_at=payload.next_action_at, body=call.note, kind="call",
            status="pending", created_at=datetime.utcnow(),
        ))

    if payload.complete_task and payload.source_key:
        _upsert_task_state(
            db, source_key=payload.source_key, actor=actor, status="completed",
            note=call.note, outcome=payload.outcome,
            task_type=payload.task_type, title=name,
            entity_type=payload.entity_type, entity_id=payload.entity_id,
        )

    db.commit()
    db.refresh(call)
    names = {u.id: (u.full_name or u.username) for u in db.query(models.User).all()}
    return _call_read(call, names)


@app.get("/activities", response_model=schemas.CallActivityPage)
def list_call_activities(
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    task_type: Optional[str] = None,
    outcome: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    """Qo'ng'iroqlar jurnali — serverda filtrlanadi va sahifalanadi.

    Admin hammasini ko'radi; qolgan rollar faqat O'Z yozuvlarini
    (`user_id` so'ralsa ham bekor qilinadi).
    """
    query = db.query(models.CallActivity)
    if actor.role != UserRole.admin.value:
        query = query.filter(models.CallActivity.user_id == actor.id)
    elif user_id:
        query = query.filter(models.CallActivity.user_id == user_id)

    if entity_type:
        query = query.filter(models.CallActivity.entity_type == entity_type)
    if entity_id:
        query = query.filter(models.CallActivity.entity_id == entity_id)
    if task_type:
        query = query.filter(models.CallActivity.task_type == task_type)
    if outcome:
        query = query.filter(models.CallActivity.outcome == outcome)
    if date_from:
        query = query.filter(models.CallActivity.created_at >= _wc_day_bounds(date_from)[0])
    if date_to:
        query = query.filter(models.CallActivity.created_at < _wc_day_bounds(date_to)[1])
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (models.CallActivity.entity_name.ilike(like)) |
            (models.CallActivity.phone.ilike(like)) |
            (models.CallActivity.note.ilike(like))
        )

    total = query.count()
    rows = (query.order_by(models.CallActivity.created_at.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    names = {u.id: (u.full_name or u.username) for u in db.query(models.User).all()}
    return schemas.CallActivityPage(
        items=[_call_read(c, names) for c in rows],
        total=total, page=page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


def _operator_stats(db, day_from, day_to, user_ids=None):
    """Operatorlar kesimi — bitta so'rovdan yig'iladi."""
    q = db.query(models.CallActivity).filter(
        models.CallActivity.created_at >= day_from,
        models.CallActivity.created_at < day_to,
    )
    if user_ids is not None:
        q = q.filter(models.CallActivity.user_id.in_(user_ids))
    calls = q.all()

    agg = {}
    for c in calls:
        e = agg.setdefault(c.user_id, {
            "calls": 0, "connected": 0, "no_answer": 0, "callbacks": 0,
            "payment": 0, "absence": 0, "leads": set(),
        })
        e["calls"] += 1
        if c.outcome in CONNECTED_OUTCOMES:
            e["connected"] += 1
        if c.outcome in NO_ANSWER_OUTCOMES:
            e["no_answer"] += 1
        if c.next_action == "callback":
            e["callbacks"] += 1
        if c.task_type == work_center.PAYMENT_REMINDER:
            e["payment"] += 1
        if c.task_type == work_center.ABSENCE_FOLLOWUP:
            e["absence"] += 1
        if c.entity_type == "lead":
            e["leads"].add(c.entity_id)

    done = dict(
        db.query(models.WorkTask.completed_by_id, func.count(models.WorkTask.id))
        .filter(models.WorkTask.status == "completed",
                models.WorkTask.completed_at >= day_from,
                models.WorkTask.completed_at < day_to)
        .group_by(models.WorkTask.completed_by_id).all()
    )
    for uid, n in done.items():
        if uid is None:
            continue
        agg.setdefault(uid, {"calls": 0, "connected": 0, "no_answer": 0,
                             "callbacks": 0, "payment": 0, "absence": 0, "leads": set()})

    users = {u.id: u for u in db.query(models.User).filter(
        models.User.id.in_(list(agg) or [0])).all()}
    out = []
    for uid, e in agg.items():
        u = users.get(uid)
        out.append(schemas.OperatorStat(
            id=uid, name=(u.full_name or u.username) if u else "Noma'lum",
            role=u.role if u else None,
            calls=e["calls"], connected=e["connected"], no_answer=e["no_answer"],
            completed_tasks=done.get(uid, 0),
            callbacks=e["callbacks"], payment_calls=e["payment"],
            absence_calls=e["absence"], leads_handled=len(e["leads"]),
            connect_rate=round(e["connected"] / e["calls"] * 100, 1) if e["calls"] else 0.0,
        ))
    out.sort(key=lambda o: (o.calls, o.completed_tasks), reverse=True)
    return out


@app.get("/activities/stats", response_model=schemas.TeamActivityRead)
def team_activity_stats(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Jamoa faoliyati — faqat admin uchun."""
    today = _wc_local_now().date()
    d_from = date_from or today
    d_to = date_to or today
    if d_to < d_from:
        d_from, d_to = d_to, d_from
    day_from = _wc_day_bounds(d_from)[0]
    day_to = _wc_day_bounds(d_to)[1]

    ops = _operator_stats(db, day_from, day_to)
    total_calls = sum(o.calls for o in ops)
    connected = sum(o.connected for o in ops)

    insights = []
    if ops:
        best = max(ops, key=lambda o: (o.connect_rate, o.calls))
        if best.calls >= 5:
            insights.append(schemas.TreeInsight(
                kind="success", title="Eng yuqori bog'lanish darajasi",
                detail=best.name, value=f"{best.connect_rate}% ({best.calls} qo'ng'iroq)",
            ))
        busiest = max(ops, key=lambda o: o.calls)
        if busiest.calls:
            insights.append(schemas.TreeInsight(
                kind="info", title="Eng ko'p qo'ng'iroq",
                detail=busiest.name, value=f"{busiest.calls} ta",
            ))
    # Oldingi teng uzunlikdagi davr bilan taqqoslash
    span = (d_to - d_from).days + 1
    prev_from = _wc_day_bounds(d_from - timedelta(days=span))[0]
    prev_calls = (
        db.query(func.count(models.CallActivity.id))
        .filter(models.CallActivity.created_at >= prev_from,
                models.CallActivity.created_at < day_from).scalar() or 0
    )
    if prev_calls:
        delta = round((total_calls - prev_calls) / prev_calls * 100, 1)
        insights.append(schemas.TreeInsight(
            kind="info" if delta >= 0 else "warning",
            title="Oldingi davrga nisbatan",
            detail=f"{prev_calls} → {total_calls} qo'ng'iroq",
            value=f"{'+' if delta >= 0 else ''}{delta}%",
        ))

    overdue_tasks = (
        db.query(func.count(models.Reminder.id))
        .filter(models.Reminder.status == "pending",
                func.coalesce(models.Reminder.snoozed_until, models.Reminder.due_at) < datetime.utcnow())
        .scalar() or 0
    )
    if overdue_tasks:
        insights.append(schemas.TreeInsight(
            kind="warning", title="Kechikkan eslatmalar",
            detail="Muddati o'tgan, hali bajarilmagan",
            value=f"{overdue_tasks} ta",
        ))

    return schemas.TeamActivityRead(
        date_from=d_from, date_to=d_to,
        total_calls=total_calls, connected=connected,
        no_answer=sum(o.no_answer for o in ops),
        completed_tasks=sum(o.completed_tasks for o in ops),
        callbacks=sum(o.callbacks for o in ops),
        payment_calls=sum(o.payment_calls for o in ops),
        absence_calls=sum(o.absence_calls for o in ops),
        connect_rate=round(connected / total_calls * 100, 1) if total_calls else 0.0,
        avg_calls_per_operator=round(total_calls / len(ops), 1) if ops else 0.0,
        operators=ops, insights=insights,
    )


@app.get("/activities/operators/{operator_id}", response_model=schemas.OperatorDetailRead)
def operator_activity_detail(
    operator_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Bitta operatorning batafsil faoliyati — qo'ng'iroqlar va vazifalar."""
    today = _wc_local_now().date()
    d_from = date_from or today
    d_to = date_to or today
    if d_to < d_from:
        d_from, d_to = d_to, d_from
    day_from = _wc_day_bounds(d_from)[0]
    day_to = _wc_day_bounds(d_to)[1]

    u = db.query(models.User).filter(models.User.id == operator_id).first()
    if not u:
        raise HTTPException(404, "Xodim topilmadi")

    stats = _operator_stats(db, day_from, day_to, user_ids=[operator_id])
    stat = stats[0] if stats else schemas.OperatorStat(
        id=operator_id, name=u.full_name or u.username, role=u.role)

    names = {x.id: (x.full_name or x.username) for x in db.query(models.User).all()}
    calls = (
        db.query(models.CallActivity)
        .filter(models.CallActivity.user_id == operator_id,
                models.CallActivity.created_at >= day_from,
                models.CallActivity.created_at < day_to)
        .order_by(models.CallActivity.created_at.desc()).limit(500).all()
    )
    tasks = (
        db.query(models.WorkTask)
        .filter(models.WorkTask.completed_by_id == operator_id,
                models.WorkTask.completed_at >= day_from,
                models.WorkTask.completed_at < day_to)
        .order_by(models.WorkTask.completed_at.desc()).limit(200).all()
    )
    return schemas.OperatorDetailRead(
        operator=stat, date_from=d_from, date_to=d_to,
        calls=[_call_read(c, names) for c in calls],
        tasks=[schemas.WorkTaskRead(
            source_key=t.source_key, task_type=t.task_type,
            task_label=work_center.TASK_LABELS.get(t.task_type, t.task_type),
            title=t.title, reason=t.reason, priority=t.priority, status=t.status,
            due_at=t.due_at, entity_type=t.entity_type, entity_id=t.entity_id,
            assigned_to_id=t.assigned_to_id, assigned_to_name=names.get(t.assigned_to_id),
            last_outcome=t.outcome, last_note=t.note,
            completed_at=t.completed_at, is_manual=bool(t.is_manual),
        ) for t in tasks],
    )


@app.get("/intake-forms", response_model=List[schemas.IntakeFormRead])
def list_intake_forms(
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    forms = (
        db.query(models.IntakeForm).options(joinedload(models.IntakeForm.source))
        .order_by(models.IntakeForm.created_at.desc()).all()
    )
    return [_intake_read(f) for f in forms]


@app.post("/intake-forms", response_model=schemas.IntakeFormRead, status_code=201)
def create_intake_form(
    payload: schemas.IntakeFormCreate,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slug = _slugify(payload.name)[:50]
    if db.query(models.IntakeForm).filter(models.IntakeForm.slug == slug).first():
        slug = f"{slug}-{int(datetime.utcnow().timestamp())}"
    form = models.IntakeForm(
        slug=slug, name=payload.name, title=payload.title or payload.name,
        description=payload.description, source_id=payload.source_id,
        is_active=True, submissions=0, created_at=datetime.utcnow(),
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    db.refresh(form, attribute_names=["source"])
    return _intake_read(form)


@app.put("/intake-forms/{form_id}", response_model=schemas.IntakeFormRead)
def update_intake_form(
    form_id: int,
    payload: schemas.IntakeFormUpdate,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    form = db.query(models.IntakeForm).filter(models.IntakeForm.id == form_id).first()
    if not form:
        raise HTTPException(404, "Forma topilmadi")
    for field, val in payload.dict(exclude_unset=True).items():
        setattr(form, field, val)
    db.commit()
    db.refresh(form)
    db.refresh(form, attribute_names=["source"])
    return _intake_read(form)


@app.delete("/intake-forms/{form_id}", status_code=204)
def delete_intake_form(
    form_id: int,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    form = db.query(models.IntakeForm).filter(models.IntakeForm.id == form_id).first()
    if not form:
        raise HTTPException(404, "Forma topilmadi")
    db.delete(form)
    db.commit()


# ── Public (auth talab qilmaydigan) intake endpoint'lar ───────────────────────

@app.get("/public/intake/{slug}", response_model=schemas.PublicIntakeConfig)
def public_intake_config(slug: str, db: Session = Depends(get_db)):
    form = db.query(models.IntakeForm).filter(models.IntakeForm.slug == slug).first()
    if not form or not form.is_active:
        raise HTTPException(404, "Forma topilmadi yoki faol emas")
    return schemas.PublicIntakeConfig(
        slug=form.slug, name=form.name, title=form.title or form.name,
        description=form.description, is_active=form.is_active,
    )


@app.post("/public/intake/{slug}", status_code=201)
def public_intake_submit(
    slug: str,
    payload: schemas.PublicLeadSubmit,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = _client_ip(request)
    # Spam himoyasi: bir IP daqiqasiga 5 ta, soatiga 30 ta ariza
    rate_limit(f"intake-min:{ip}", limit=5, window=60)
    rate_limit(f"intake-hour:{ip}", limit=30, window=3600)

    form = db.query(models.IntakeForm).filter(models.IntakeForm.slug == slug).first()
    if not form or not form.is_active:
        raise HTTPException(404, "Forma topilmadi yoki faol emas")
    if _find_duplicate_lead(db, payload.phone):
        raise HTTPException(409, "Bu raqam bilan ariza allaqachon qabul qilingan")
    stage = _default_stage(db)
    lead = models.Lead(
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        # Dedup kaliti — busiz keyingi tekshiruvlar bu lidni "ko'rmay" qolardi
        # va shu raqam ikkinchi marta ro'yxatga tushib ketardi.
        phone_key=dedup_key(payload.phone),
        course_interest=payload.course_interest,
        parent_phone=payload.parent_phone,
        notes=payload.notes,
        source_id=form.source_id,
        status=stage.slug if stage else models.LeadStatus.new.value,
        stage_id=stage.id if stage else None,
        is_shared=True,                       # ommaviy formadan kelgan lid — umumiy havzaga
        created_by_id=_system_user_id(db),
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.flush()
    _log_lead_activity(
        db, lead_id=lead.id, action="created",
        description=f"Ommaviy forma orqali: {form.name}", author_id=None,
    )
    form.submissions = (form.submissions or 0) + 1
    recipients = [u[0] for u in db.query(models.User.id).filter(
        models.User.is_active == True,  # noqa: E712
        models.User.role.in_([UserRole.admin.value, UserRole.call_center.value,
                              UserRole.hunter.value, UserRole.sales.value]),
    ).all()]
    _notify(
        db, user_ids=recipients,
        title="Ommaviy formadan yangi lid",
        body=f"{lead.full_name} · {form.name}",
        link=f"/leads?lead={lead.id}", ntype="new_lead",
    )
    db.commit()
    return {"ok": True, "message": "Arizangiz qabul qilindi"}


def _system_user_id(db) -> int:
    """Ommaviy formadan kelgan lidlar uchun 'egasi' — birinchi admin."""
    u = (
        db.query(models.User.id)
        .filter(models.User.role == UserRole.admin.value)
        .order_by(models.User.id.asc()).first()
    )
    if not u:
        u = db.query(models.User.id).order_by(models.User.id.asc()).first()
    return u[0]


# ═══════════════════════════════════════════════════════════════════════════
#  OTA-ONA AKKAUNTLARI — hunter/admin boshqaruvi (+ dars jadvali slotlari)
# ═══════════════════════════════════════════════════════════════════════════
import secrets as _secrets
import string as _string


def _gen_password(n: int = 8) -> str:
    alphabet = _string.ascii_letters + _string.digits
    return "".join(_secrets.choice(alphabet) for _ in range(n))


def _parent_account_read(p: models.Parent) -> schemas.ParentAccountRead:
    return schemas.ParentAccountRead(
        id=p.id, full_name=p.full_name, display_name=p.display_name,
        phone=p.phone, username=p.username, is_active=p.is_active, created_at=p.created_at,
        children=[
            schemas.ParentChildInfo(student_id=c.student_id, student_name=c.student.full_name)
            for c in p.children if c.student
        ],
    )


@app.post("/parents", response_model=schemas.ParentAccountCreated, status_code=201)
def create_parent_account(
    payload: schemas.ParentAccountCreate,
    actor: models.User = Depends(require_hunter),
    db: Session = Depends(get_db),
):
    """Ota-ona akkaunti yaratish (hunter/admin). Parol bir marta qaytariladi."""
    phone = payload.phone.strip()
    username = (payload.username or phone).strip()
    if db.query(models.Parent).filter(models.Parent.phone == phone).first():
        raise HTTPException(409, "Bu telefon bilan ota-ona allaqachon mavjud")
    if db.query(models.Parent).filter(models.Parent.username == username).first():
        raise HTTPException(409, "Bu login band")

    raw_password = payload.password or _gen_password()
    parent = models.Parent(
        full_name=payload.full_name.strip(), display_name=payload.display_name,
        phone=phone, username=username, hashed_password=hash_password(raw_password),
        is_active=True, created_by_id=actor.id, created_at=datetime.utcnow(),
    )
    db.add(parent)
    db.flush()
    for sid in dict.fromkeys(payload.student_ids):   # dublikatlarsiz
        if db.query(models.Student).filter(models.Student.id == sid).first():
            db.add(models.ParentChild(parent_id=parent.id, student_id=sid, created_at=datetime.utcnow()))
    db.commit()
    db.refresh(parent)
    out = schemas.ParentAccountCreated(**_parent_account_read(parent).dict())
    out.generated_password = raw_password
    return out


@app.get("/parents", response_model=List[schemas.ParentAccountRead])
def list_parent_accounts(
    search: Optional[str] = Query(None),
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    q = db.query(models.Parent).options(
        joinedload(models.Parent.children).joinedload(models.ParentChild.student),
    )
    if search:
        q = q.filter(
            models.Parent.full_name.ilike(f"%{search}%") |
            models.Parent.phone.ilike(f"%{search}%") |
            models.Parent.username.ilike(f"%{search}%")
        )
    return [_parent_account_read(p) for p in q.order_by(models.Parent.full_name).all()]


@app.get("/parents/{parent_id}", response_model=schemas.ParentAccountRead)
def get_parent_account(
    parent_id: int,
    actor: models.User = Depends(require_crm_access),
    db: Session = Depends(get_db),
):
    p = db.query(models.Parent).filter(models.Parent.id == parent_id).first()
    if not p:
        raise HTTPException(404, "Ota-ona topilmadi")
    return _parent_account_read(p)


@app.patch("/parents/{parent_id}", response_model=schemas.ParentAccountRead)
def update_parent_account(
    parent_id: int,
    payload: schemas.ParentAccountUpdate,
    actor: models.User = Depends(require_hunter),
    db: Session = Depends(get_db),
):
    p = db.query(models.Parent).filter(models.Parent.id == parent_id).first()
    if not p:
        raise HTTPException(404, "Ota-ona topilmadi")
    data = payload.dict(exclude_unset=True)
    if "phone" in data and data["phone"] != p.phone:
        if db.query(models.Parent).filter(models.Parent.phone == data["phone"]).first():
            raise HTTPException(409, "Bu telefon band")
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _parent_account_read(p)


@app.post("/parents/{parent_id}/reset-password")
def reset_parent_password(
    parent_id: int,
    payload: schemas.ResetParentPassword,
    actor: models.User = Depends(require_hunter),
    db: Session = Depends(get_db),
):
    p = db.query(models.Parent).filter(models.Parent.id == parent_id).first()
    if not p:
        raise HTTPException(404, "Ota-ona topilmadi")
    raw = payload.password or _gen_password()
    p.hashed_password = hash_password(raw)
    # Barcha refresh tokenlarni bekor qilamiz (xavfsizlik)
    db.query(models.ParentRefreshToken).filter(
        models.ParentRefreshToken.parent_id == p.id,
        models.ParentRefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.utcnow()})
    db.commit()
    return {"generated_password": raw}


@app.post("/parents/{parent_id}/children", response_model=schemas.ParentAccountRead)
def link_parent_child(
    parent_id: int,
    payload: schemas.LinkChildRequest,
    actor: models.User = Depends(require_hunter),
    db: Session = Depends(get_db),
):
    p = db.query(models.Parent).filter(models.Parent.id == parent_id).first()
    if not p:
        raise HTTPException(404, "Ota-ona topilmadi")
    if not db.query(models.Student).filter(models.Student.id == payload.student_id).first():
        raise HTTPException(404, "Talaba topilmadi")
    exists = db.query(models.ParentChild).filter(
        models.ParentChild.parent_id == parent_id,
        models.ParentChild.student_id == payload.student_id,
    ).first()
    if not exists:
        db.add(models.ParentChild(parent_id=parent_id, student_id=payload.student_id, created_at=datetime.utcnow()))
        db.commit()
    db.refresh(p)
    return _parent_account_read(p)


@app.delete("/parents/{parent_id}/children/{student_id}", status_code=204)
def unlink_parent_child(
    parent_id: int,
    student_id: int,
    actor: models.User = Depends(require_hunter),
    db: Session = Depends(get_db),
):
    link = db.query(models.ParentChild).filter(
        models.ParentChild.parent_id == parent_id,
        models.ParentChild.student_id == student_id,
    ).first()
    if link:
        db.delete(link)
        db.commit()


@app.post("/parents/broadcast", response_model=schemas.ParentBroadcastResult)
def broadcast_to_parents(
    payload: schemas.ParentBroadcastRequest,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Talabalarga bog'langan Telegram ID'lari (Student.telegram_user_id) orqali
    barcha ota-onalarga bir xil matnli xabar yuboradi — bitta ID bir nechta
    talabaga tegishli bo'lsa ham, unga faqat bitta xabar boradi."""
    ids = [
        row[0] for row in
        db.query(models.Student.telegram_user_id)
        .filter(models.Student.telegram_user_id.isnot(None), models.Student.telegram_user_id != "")
        .distinct()
        .all()
    ]
    safe_text = html.escape(payload.text)
    sent = 0
    errors: list[str] = []
    for tid in ids:
        try:
            ok, err = send_telegram_message(tid, safe_text)
        except Exception as e:
            ok, err = False, str(e)[:400]
        if ok:
            sent += 1
        elif err and err not in errors:
            errors.append(err)
    write_audit(db, entity_type="parent_broadcast", entity_id=0, action="send",
                changed_by_id=actor.id,
                new_value={"text": payload.text, "total": len(ids), "sent": sent, "errors": errors[:5]})
    db.commit()
    return schemas.ParentBroadcastResult(
        total=len(ids), sent=sent, failed=len(ids) - sent, sample_errors=errors[:5]
    )


@app.post("/users/broadcast", response_model=schemas.StaffBroadcastResult)
def broadcast_to_staff(
    payload: schemas.StaffBroadcastRequest,
    actor: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Telegram ID'si (User.telegram_chat_id) biriktirilgan barcha faol xodimlarga
    bir xil matnli xabar yuboradi."""
    ids = [
        row[0] for row in
        db.query(models.User.telegram_chat_id)
        .filter(
            models.User.telegram_chat_id.isnot(None),
            models.User.telegram_chat_id != "",
            models.User.is_active.is_(True),
        )
        .distinct()
        .all()
    ]
    safe_text = html.escape(payload.text)
    sent = 0
    errors: list[str] = []
    for tid in ids:
        try:
            ok, err = send_telegram_message(tid, safe_text)
        except Exception as e:
            ok, err = False, str(e)[:400]
        if ok:
            sent += 1
        elif err and err not in errors:
            errors.append(err)
    write_audit(db, entity_type="staff_broadcast", entity_id=0, action="send",
                changed_by_id=actor.id,
                new_value={"text": payload.text, "total": len(ids), "sent": sent, "errors": errors[:5]})
    db.commit()
    return schemas.StaffBroadcastResult(
        total=len(ids), sent=sent, failed=len(ids) - sent, sample_errors=errors[:5]
    )


# ── Dars jadvali slotlari (strukturaviy jadval) ──────────────────────────────

@app.get("/groups/{group_id}/schedule-slots", response_model=List[schemas.ScheduleSlotRead])
def list_schedule_slots(
    group_id: int,
    actor: models.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.ScheduleSlot)
        .filter(models.ScheduleSlot.group_id == group_id)
        .order_by(models.ScheduleSlot.day_of_week, models.ScheduleSlot.start_time)
        .all()
    )


@app.post("/groups/{group_id}/schedule-slots", response_model=schemas.ScheduleSlotRead, status_code=201)
def create_schedule_slot(
    group_id: int,
    payload: schemas.ScheduleSlotCreate,
    actor: models.User = Depends(require_lms_write),
    db: Session = Depends(get_db),
):
    if not db.query(models.Group).filter(models.Group.id == group_id).first():
        raise HTTPException(404, "Guruh topilmadi")
    slot = models.ScheduleSlot(
        group_id=group_id, day_of_week=payload.day_of_week,
        start_time=payload.start_time, end_time=payload.end_time,
        room=payload.room, created_at=datetime.utcnow(),
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@app.delete("/schedule-slots/{slot_id}", status_code=204)
def delete_schedule_slot(
    slot_id: int,
    actor: models.User = Depends(require_lms_write),
    db: Session = Depends(get_db),
):
    slot = db.query(models.ScheduleSlot).filter(models.ScheduleSlot.id == slot_id).first()
    if slot:
        db.delete(slot)
        db.commit()
# ── Camera API ────────────────────────────────────────────────────────────────

@app.post("/students/{student_id}/face-photo")
async def upload_student_face_photo(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_lms_write),
):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    contents, ext = await _read_image_upload(file, allow_gif=False)
    s.photo_path = _store_upload("student_photos", ext, contents, s.photo_path)
    db.commit()
    return {"photo_url": f"/uploads/{uploads_sign.sign(s.photo_path)}"}

def _require_camera_key(x_camera_key: Optional[str] = Header(None, alias="x-camera-key")) -> None:
    if not CAMERA_API_KEY or not x_camera_key or not _sec.compare_digest(
            x_camera_key.encode(), CAMERA_API_KEY.encode()):
        raise HTTPException(status_code=403, detail="Camera API key noto'g'ri")


@app.post("/users/{user_id}/face-photo")
async def upload_user_face_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    contents, ext = await _read_image_upload(file, allow_gif=False)
    u.face_photo_path = _store_upload("staff_photos", ext, contents, u.face_photo_path)
    db.commit()
    return {"face_photo_url": f"/uploads/{uploads_sign.sign(u.face_photo_path)}"}


@app.get("/camera/students")
def camera_students(
    db: Session = Depends(get_db),
    _: None = Depends(_require_camera_key),
):
    """Kamera servisi uchun — faol o'quvchilar ro'yxati (foto, guruh, jadval, to'lov holati)."""
    now_   = tz.today()
    month_ = now_.month
    year_  = now_.year

    students = (
        db.query(models.Student)
        .options(
            selectinload(models.Student.group_memberships).selectinload(models.GroupStudent.group),
            selectinload(models.Student.payments),
        )
        .filter(models.Student.is_active == True, models.Student.is_archived == False)
        .all()
    )
    result = []
    for s in students:
        groups = [
            {"id": gs.group_id, "name": gs.group.name, "schedule": gs.group.schedule}
            for gs in s.group_memberships
            if gs.group and gs.group.is_active and gs.left_at is None
        ]
        paid_this_month = sum(
            float(p.amount) for p in s.payments
            if p.month == month_ and p.year == year_
        )
        is_debtor = (paid_this_month == 0) and len(groups) > 0
        result.append({
            "id":         s.id,
            "full_name":  s.full_name,
            "telegram_id": s.telegram_id,
            # /uploads imzosiz ochilmaydi — kamera rasmni o'z kaliti bilan oladi
            "photo_url":  f"/camera/photo/student/{s.id}" if s.photo_path else None,
            "groups":     groups,
            "is_debtor":  is_debtor,
        })
    return result


@app.get("/camera/staff")
def camera_staff(
    db: Session = Depends(get_db),
    _: None = Depends(_require_camera_key),
):
    """Kamera servisi uchun — yuz rasmi bor xodimlar ro'yxati."""
    staff = (
        db.query(models.User)
        .filter(
            models.User.is_active == True,
            models.User.face_photo_path.isnot(None),
        )
        .all()
    )
    return [
        {
            "id": u.id,
            "full_name": u.full_name or u.username,
            "role": u.role,
            "face_photo_url": f"/camera/photo/staff/{u.id}" if u.face_photo_path else None,
        }
        for u in staff
    ]


@app.get("/camera/photo/student/{student_id}")
def camera_student_photo(
    student_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(_require_camera_key),
):
    """Kamera servisi uchun — o'quvchi yuz rasmi (bytes)."""
    from fastapi.responses import FileResponse as FR
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s or not s.photo_path:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    path = os.path.join(UPLOAD_DIR, s.photo_path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fayl topilmadi")
    return FR(path)


@app.get("/camera/photo/staff/{user_id}")
def camera_staff_photo(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(_require_camera_key),
):
    """Kamera servisi uchun — xodim yuz rasmi (bytes)."""
    from fastapi.responses import FileResponse as FR
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u or not u.face_photo_path:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    path = os.path.join(UPLOAD_DIR, u.face_photo_path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fayl topilmadi")
    return FR(path)


@app.post("/camera/checkin", status_code=201)
def camera_checkin(
    payload: schemas.CameraCheckin,
    db: Session = Depends(get_db),
    _: None = Depends(_require_camera_key),
):
    """Kamera tomonidan aniqlangan keldi/ketdi hodisasini DB ga saqlaydi."""
    detected_at = payload.detected_at or datetime.utcnow()
    event_type  = "keldi" if payload.event in ("arrival", "keldi") else "ketdi"

    rec = models.CameraAttendance(
        student_id  = payload.student_id if payload.person_type == "student" else None,
        staff_id    = payload.student_id if payload.person_type == "staff"   else None,
        person_type = payload.person_type or "student",
        event_type  = event_type,
        detected_at = detected_at,
    )
    db.add(rec)
    db.commit()
    return {"status": "ok", "id": rec.id}


@app.get("/students/{student_id}/camera-attendance")
def student_camera_attendance(
    student_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    """O'quvchining kamera orqali keldi/ketdi tarixi (so'nggi N kun)."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(models.CameraAttendance)
        .filter(
            models.CameraAttendance.student_id == student_id,
            models.CameraAttendance.detected_at >= since,
        )
        .order_by(models.CameraAttendance.detected_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id":          r.id,
            "event_type":  r.event_type,
            "detected_at": r.detected_at.isoformat(),
        }
        for r in rows
    ]


# ── Staff warnings (audit) ─────────────────────────────────────────────────────
# Audit xodimga ogohlantirish shu yerdan beradi; bot faqat xabarni Telegram orqali
# yetkazib beruvchi vositachi — botga hech qanday so'rov yozilmaydi, aksincha shu
# yerning o'zi mavjud send_telegram_message() yordamida to'g'ridan-to'g'ri yuboradi.

SEVERITY_EMOJI = {"gray": "⚪️", "yellow": "\U0001f7e1", "red": "\U0001f534"}


def _staff_name(u: Optional[models.User]) -> Optional[str]:
    if not u:
        return None
    return u.full_name or u.username


def _staff_warning_read(w: models.StaffWarning) -> schemas.StaffWarningRead:
    return schemas.StaffWarningRead(
        id=w.id, staff_id=w.staff_id, staff_name=_staff_name(w.staff),
        issued_by_id=w.issued_by_id, issued_by_name=_staff_name(w.issued_by),
        discipline_code_id=w.discipline_code_id, code=w.code, severity=w.severity,
        reason=w.reason, photo_path=w.photo_path,
        created_at=w.created_at, notified_at=w.notified_at, notify_error=w.notify_error,
        cancelled_at=w.cancelled_at, cancelled_by_name=_staff_name(w.cancelled_by),
    )


def _send_staff_warning_notification(w: models.StaffWarning, staff: models.User) -> None:
    """`w`ning notified_at/notify_error maydonlarini joyida yangilaydi — db.commit() chaqiruvchida."""
    if not staff.telegram_chat_id:
        w.notify_error = "Xodimga Telegram ID biriktirilmagan (bot orqali /start bosishi kerak)"
        return
    emoji = SEVERITY_EMOJI.get(w.severity, "⚠️")
    local_time = tz.to_local(w.created_at).strftime("%d.%m.%Y %H:%M")
    lines = [f"{emoji} <b>Sizga ogohlantirish berildi</b>", ""]
    if w.code:
        lines.append(f"Kod: {html.escape(w.code)}")
    lines.append(f"Sabab: {html.escape(w.reason)}")
    lines.append(f"Sana: {local_time}")
    ok, err = send_telegram_message(staff.telegram_chat_id, "\n".join(lines))
    if ok:
        w.notified_at = datetime.utcnow()
        w.notify_error = None
    else:
        w.notify_error = err


@app.get("/staff-options", response_model=List[schemas.StaffOption])
def list_staff_options(db: Session = Depends(get_db), _: models.User = Depends(require_audit)):
    """Ogohlantirish beriladigan xodim tanlagichi uchun — /users kabi metodist-only emas."""
    return (
        db.query(models.User)
        .filter(models.User.is_active.is_(True))
        .order_by(models.User.full_name, models.User.username)
        .all()
    )


@app.patch("/staff-options/{user_id}/telegram", response_model=schemas.StaffOption)
def set_staff_telegram_chat_id(
    user_id: int,
    payload: schemas.StaffTelegramUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_audit),
):
    """Audit (yoki admin) xodimga Telegram chat ID biriktiradi — faqat shu
    maydon o'zgaradi, role/parol/is_active kabi maydonlarga tegilmaydi."""
    staff = db.query(models.User).filter(models.User.id == user_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    old_val = staff.telegram_chat_id
    new_val = (payload.telegram_chat_id or "").strip() or None
    staff.telegram_chat_id = new_val
    write_audit(db, entity_type="user", entity_id=staff.id, action="set_telegram_chat_id",
                changed_by_id=actor.id,
                old_value={"telegram_chat_id": old_val}, new_value={"telegram_chat_id": new_val})
    db.commit()
    db.refresh(staff)
    return staff


@app.get("/discipline-codes", response_model=List[schemas.DisciplineCodeRead])
def list_discipline_codes(db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    codes = (
        db.query(models.DisciplineCode)
        .filter(models.DisciplineCode.is_active.is_(True))
        .order_by(models.DisciplineCode.code)
        .all()
    )
    return codes


@app.get("/staff-warnings/mine", response_model=List[schemas.StaffWarningRead])
def list_my_staff_warnings(db: Session = Depends(get_db), actor: models.User = Depends(require_auth)):
    """Har qanday login qilgan xodim — faqat o'ziga berilgan ogohlantirishlarni ko'radi."""
    q = (
        db.query(models.StaffWarning)
        .options(
            joinedload(models.StaffWarning.staff),
            joinedload(models.StaffWarning.issued_by),
            joinedload(models.StaffWarning.cancelled_by),
        )
        .filter(models.StaffWarning.staff_id == actor.id)
    )
    return [_staff_warning_read(w) for w in q.order_by(models.StaffWarning.created_at.desc()).all()]


@app.get("/staff-warnings", response_model=List[schemas.StaffWarningRead])
def list_staff_warnings(
    staff_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_audit),
):
    q = db.query(models.StaffWarning).options(
        joinedload(models.StaffWarning.staff),
        joinedload(models.StaffWarning.issued_by),
        joinedload(models.StaffWarning.cancelled_by),
    )
    if staff_id:
        q = q.filter(models.StaffWarning.staff_id == staff_id)
    return [_staff_warning_read(w) for w in q.order_by(models.StaffWarning.created_at.desc()).all()]


@app.post("/staff-warnings", response_model=schemas.StaffWarningRead, status_code=201)
def create_staff_warning(
    payload: schemas.StaffWarningCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_audit),
):
    staff = db.query(models.User).filter(models.User.id == payload.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    code = None
    severity = payload.severity
    reason = payload.reason
    if payload.discipline_code_id:
        dc = db.query(models.DisciplineCode).filter(
            models.DisciplineCode.id == payload.discipline_code_id,
            models.DisciplineCode.is_active.is_(True),
        ).first()
        if not dc:
            raise HTTPException(status_code=404, detail="Kodeks moddasi topilmadi")
        code, severity, reason = dc.code, dc.severity, dc.text
    elif not severity or not reason:
        raise HTTPException(status_code=400, detail="Kodeks tanlang yoki daraja va sabab kiriting")

    w = models.StaffWarning(
        staff_id=staff.id, issued_by_id=actor.id,
        discipline_code_id=payload.discipline_code_id, code=code,
        severity=severity, reason=reason,
    )
    db.add(w)
    db.flush()
    _send_staff_warning_notification(w, staff)
    write_audit(db, entity_type="staff_warning", entity_id=w.id, action="create",
                changed_by_id=actor.id,
                new_value={"staff_id": staff.id, "code": code, "severity": severity, "reason": reason})
    db.commit()
    db.refresh(w)
    return _staff_warning_read(w)


@app.post("/staff-warnings/{warning_id}/resend", response_model=schemas.StaffWarningRead)
def resend_staff_warning(warning_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_audit)):
    w = db.query(models.StaffWarning).filter(models.StaffWarning.id == warning_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Ogohlantirish topilmadi")
    if w.cancelled_at:
        raise HTTPException(status_code=400, detail="Bekor qilingan ogohlantirish qayta yuborilmaydi")
    staff = db.query(models.User).filter(models.User.id == w.staff_id).first()
    _send_staff_warning_notification(w, staff)
    db.commit()
    db.refresh(w)
    return _staff_warning_read(w)


@app.post("/staff-warnings/{warning_id}/cancel", response_model=schemas.StaffWarningRead)
def cancel_staff_warning(warning_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    w = db.query(models.StaffWarning).filter(models.StaffWarning.id == warning_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Ogohlantirish topilmadi")
    if w.cancelled_at:
        raise HTTPException(status_code=400, detail="Ogohlantirish allaqachon bekor qilingan")
    w.cancelled_at = datetime.utcnow()
    w.cancelled_by_id = actor.id
    write_audit(db, entity_type="staff_warning", entity_id=w.id, action="cancel", changed_by_id=actor.id)
    db.commit()
    db.refresh(w)
    return _staff_warning_read(w)


# ── Bot boshqaruvi (Employee/Role/Sozlama/Taklif havolalari) ────────────────────
# Bot'ning o'z SQLite bazasiga to'g'ridan-to'g'ri o'qish/yozish (backend/bot_client.py) —
# bot buni o'z ichida qanday saqlagan bo'lsa, aynan shu ma'lumotlar ustida ishlaydi.
# Bot bu bazani ham o'qib/yozib turgani uchun (WAL rejimida) bir vaqtda ikkala
# jarayon ham xavfsiz ishlay oladi.

def _bot_employee_read(e: bot_client.BotEmployee) -> schemas.BotEmployeeRead:
    return schemas.BotEmployeeRead(
        id=e.id, telegram_id=e.telegram_id, full_name=e.full_name, username=e.username,
        role_id=e.role_id, role_name=e.role.name if e.role else None,
        is_admin=e.is_admin, is_superadmin=e.is_superadmin,
    )


@app.get("/bot/employees", response_model=List[schemas.BotEmployeeRead])
def list_bot_employees(actor: models.User = Depends(require_admin)):
    db = bot_client.BotSessionLocal()
    try:
        employees = (
            db.query(bot_client.BotEmployee)
            .options(joinedload(bot_client.BotEmployee.role))
            .order_by(bot_client.BotEmployee.full_name)
            .all()
        )
        return [_bot_employee_read(e) for e in employees]
    finally:
        db.close()


@app.get("/bot/chats", response_model=List[schemas.BotChatRead])
def list_bot_chats(search: Optional[str] = Query(None), db: Session = Depends(get_db),
                    actor: models.User = Depends(require_hunter)):
    """Bot orqali xabar almashilgan barcha suhbatlar — oxirgi xabar bilan, Chatbot inbox uchun."""
    bdb = bot_client.BotSessionLocal()
    try:
        sub = (
            bdb.query(
                bot_client.BotMessage.chat_id,
                func.max(bot_client.BotMessage.id).label("last_id"),
                func.count(bot_client.BotMessage.id).label("cnt"),
            )
            .group_by(bot_client.BotMessage.chat_id)
            .subquery()
        )
        rows = (
            bdb.query(bot_client.BotMessage, sub.c.cnt)
            .join(sub, bot_client.BotMessage.id == sub.c.last_id)
            .order_by(bot_client.BotMessage.created_at.desc())
            .all()
        )
        chat_ids = [m.chat_id for m, _ in rows]

        students_by_tid = {}
        if chat_ids:
            for s in db.query(models.Student).filter(
                models.Student.telegram_user_id.in_([str(c) for c in chat_ids])
            ).all():
                students_by_tid[str(s.telegram_user_id)] = s

        employees_by_tid = {}
        if chat_ids:
            for e in bdb.query(bot_client.BotEmployee).filter(
                bot_client.BotEmployee.telegram_id.in_(chat_ids)
            ).all():
                employees_by_tid[e.telegram_id] = e

        out = []
        for m, cnt in rows:
            student = students_by_tid.get(str(m.chat_id))
            employee = employees_by_tid.get(m.chat_id)
            if student:
                kind, display_name = "student", student.full_name
            elif employee:
                kind, display_name = "staff", employee.full_name
            else:
                kind = "unknown"
                display_name = m.full_name or (f"@{m.username}" if m.username else str(m.chat_id))
            if search:
                s_low = search.lower()
                if s_low not in display_name.lower() and search not in str(m.chat_id):
                    continue
            out.append(schemas.BotChatRead(
                chat_id=m.chat_id, display_name=display_name, kind=kind,
                last_text=m.text, last_direction=m.direction, last_sent_ok=m.sent_ok,
                last_at=m.created_at, message_count=cnt,
            ))
        return out
    finally:
        bdb.close()


@app.get("/bot/chats/{chat_id}/messages", response_model=List[schemas.BotMessageRead])
def list_bot_chat_messages(chat_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                            actor: models.User = Depends(require_hunter)):
    """Bitta suhbatning xabarlar tarixi (eskidan yangiga qarab)."""
    bdb = bot_client.BotSessionLocal()
    try:
        q = (
            bdb.query(bot_client.BotMessage)
            .filter(bot_client.BotMessage.chat_id == chat_id)
            .order_by(bot_client.BotMessage.created_at.desc())
        )
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
        rows.reverse()
        return rows
    finally:
        bdb.close()


@app.get("/bot/roles", response_model=List[schemas.BotRoleRead])
def list_bot_roles(actor: models.User = Depends(require_admin)):
    db = bot_client.BotSessionLocal()
    try:
        return db.query(bot_client.BotRole).order_by(bot_client.BotRole.name).all()
    finally:
        db.close()


@app.post("/bot/roles", response_model=schemas.BotRoleRead, status_code=201)
def create_bot_role(payload: schemas.BotRoleCreate, actor: models.User = Depends(require_admin)):
    db = bot_client.BotSessionLocal()
    try:
        existing = db.query(bot_client.BotRole).filter(bot_client.BotRole.name == payload.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu nomdagi rol allaqachon mavjud")
        role = bot_client.BotRole(name=payload.name, is_parent=payload.is_parent, is_active=True)
        db.add(role)
        db.commit()
        db.refresh(role)
        return role
    finally:
        db.close()


@app.patch("/bot/roles/{role_id}/toggle", response_model=schemas.BotRoleRead)
def toggle_bot_role(role_id: int, actor: models.User = Depends(require_admin)):
    db = bot_client.BotSessionLocal()
    try:
        role = db.get(bot_client.BotRole, role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol topilmadi")
        role.is_active = not role.is_active
        db.commit()
        db.refresh(role)
        return role
    finally:
        db.close()


@app.post("/bot/employees/{employee_id}/role", response_model=schemas.BotEmployeeRead)
def set_bot_employee_role(
    employee_id: int, payload: schemas.BotEmployeeRoleSet, actor: models.User = Depends(require_admin),
):
    db = bot_client.BotSessionLocal()
    try:
        employee = db.get(bot_client.BotEmployee, employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Xodim topilmadi")
        if payload.role_id is None:
            employee.role_id = None
            db.commit()
            db.refresh(employee)
            send_telegram_message(str(employee.telegram_id), "Sizning rolingiz olib tashlandi.")
            return _bot_employee_read(employee)
        role = db.get(bot_client.BotRole, payload.role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol topilmadi")
        employee.role_id = role.id
        db.commit()
        db.refresh(employee)
        if role.is_parent:
            dm_text = (
                f"\U0001f389 Minar Academyga xush kelibsiz, {html.escape(employee.full_name)}!\n\n"
                "Endi farzandingizning davomati, dars jadvali va boshqa muhim yangiliklardan shu bot "
                "orqali xabardor bo'lib turasiz. Boshlash uchun botga /start bosing."
            )
        else:
            dm_text = (
                f"Sizga '{html.escape(role.name)}' roli berildi. Yangilangan imkoniyatlar uchun "
                "botga /start bosing."
            )
        send_telegram_message(str(employee.telegram_id), dm_text)
        return _bot_employee_read(employee)
    finally:
        db.close()


@app.post("/bot/employees/{employee_id}/admin", response_model=schemas.BotEmployeeRead)
def set_bot_employee_admin(
    employee_id: int, payload: schemas.BotEmployeeAdminSet, actor: models.User = Depends(require_admin),
):
    db = bot_client.BotSessionLocal()
    try:
        employee = db.get(bot_client.BotEmployee, employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Xodim topilmadi")
        if payload.tier is None:
            admins = db.query(bot_client.BotEmployee).filter(bot_client.BotEmployee.is_admin.is_(True)).all()
            if not employee.is_admin:
                raise HTTPException(status_code=400, detail="Bu xodim admin emas")
            if len(admins) <= 1:
                raise HTTPException(status_code=400, detail="Bu yagona admin, uni adminlikdan olib bo'lmaydi")
            if employee.is_superadmin and sum(1 for a in admins if a.is_superadmin) <= 1:
                raise HTTPException(status_code=400, detail="Bu yagona superadmin, uni olib bo'lmaydi")
            employee.is_admin = False
            employee.is_superadmin = False
            db.commit()
            db.refresh(employee)
            send_telegram_message(str(employee.telegram_id), "Sizning admin huquqingiz olib tashlandi.")
            return _bot_employee_read(employee)
        employee.is_admin = True
        employee.is_superadmin = payload.tier == "superadmin"
        db.commit()
        db.refresh(employee)
        tier_label = "Superadmin (CEO)" if employee.is_superadmin else "Admin"
        send_telegram_message(
            str(employee.telegram_id),
            f"\U0001f451 Sizga {tier_label} huquqi berildi. Botga /start bosib davom eting.",
        )
        return _bot_employee_read(employee)
    finally:
        db.close()


@app.get("/bot/settings/{key}", response_model=schemas.BotSettingValue)
def get_bot_setting(key: str, actor: models.User = Depends(require_admin)):
    db = bot_client.BotSessionLocal()
    try:
        setting = db.query(bot_client.BotSetting).filter(bot_client.BotSetting.key == key).first()
        return schemas.BotSettingValue(value=setting.value if setting else "")
    finally:
        db.close()


@app.put("/bot/settings/{key}", response_model=schemas.BotSettingValue)
def set_bot_setting(key: str, payload: schemas.BotSettingValue, actor: models.User = Depends(require_admin)):
    db = bot_client.BotSessionLocal()
    try:
        setting = db.query(bot_client.BotSetting).filter(bot_client.BotSetting.key == key).first()
        if setting is None:
            setting = bot_client.BotSetting(key=key, value=payload.value)
            db.add(setting)
        else:
            setting.value = payload.value
        db.commit()
        return schemas.BotSettingValue(value=payload.value)
    finally:
        db.close()


@app.post("/bot/investor/send-now")
def investor_send_daily_stats_now(actor: models.User = Depends(require_admin)):
    """Kunlik statistikani darhol investorlar guruhiga yuboradi (sinov/qo'lda yuborish uchun)."""
    chat_id = _investor_setting("investor_chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Investorlar guruhi Telegram chat ID kiritilmagan")
    ok, err = send_telegram_message(chat_id, build_investor_daily_stats_message())
    if ok:
        today_str = tz.today().isoformat()
        _investor_setting_set("investor_daily_stats_last_sent", today_str)
    return {"ok": ok, "detail": err}


@app.post("/bot/invite-links", response_model=schemas.BotInviteLinkRead, status_code=201)
def create_bot_invite_link(payload: schemas.BotInviteLinkCreate, actor: models.User = Depends(require_admin)):
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN sozlanmagan")
    db = bot_client.BotSessionLocal()
    try:
        # Havola yozuvining "kim yaratdi" (created_by_id) maydoni bot'ning o'z xodim ID'siga
        # bog'langan (NOT NULL FK) — CRM orqali chaqirilganda mavjud bot superadminlaridan
        # birini nominal yaratuvchi sifatida ishlatamiz (faqat bot ichidagi bookkeeping uchun).
        creator = (
            db.query(bot_client.BotEmployee)
            .filter(bot_client.BotEmployee.is_superadmin.is_(True))
            .first()
        )
        if creator is None:
            raise HTTPException(status_code=400, detail="Botda hech qanday superadmin topilmadi")
        token = _secrets.token_urlsafe(16)
        link_row = bot_client.BotAdminInviteLink(token=token, tier=payload.tier, created_by_id=creator.id)
        db.add(link_row)
        db.commit()

        import httpx
        r = httpx.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=10)
        bot_username = r.json().get("result", {}).get("username", "")
        link = f"https://t.me/{bot_username}?start=invite_{token}"
        return schemas.BotInviteLinkRead(token=token, tier=payload.tier, link=link, used=False)
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Kompyuter berish (bron) — hunter/admin
# ══════════════════════════════════════════════════════════════════════════════
# Talabaga markaz kompyuteri vaqtincha beriladi: qaysi raqamli kompyuter, kimga,
# soat nechida berildi, soat nechida qaytarib olindi va buni kim qildi — hammasi
# `computer_rentals` jurnalida. Vaqtlar server tomonida qo'yiladi (tugma
# bosilgan payt) — qo'lda yozilgan vaqt jurnalning ishonchliligini buzardi.

def _rental_dict(r: models.ComputerRental) -> dict:
    end = r.returned_at or tz.utcnow()
    return {
        "id": r.id,
        "computer_id": r.computer_id,
        "computer_number": r.computer.number if r.computer else None,
        "computer_name": r.computer.name if r.computer else None,
        "student_id": r.student_id,
        "student_name": r.student.full_name if r.student else None,
        "student_phone": r.student.phone1 if r.student else None,
        "given_at": r.given_at,
        "returned_at": r.returned_at,
        "duration_minutes": max(0, int((end - r.given_at).total_seconds() // 60)),
        "given_by": (r.given_by.full_name or r.given_by.username) if r.given_by else None,
        "returned_by": (r.returned_by.full_name or r.returned_by.username) if r.returned_by else None,
        "note": r.note,
        "return_note": r.return_note,
    }


def _rental_query(db: Session):
    return db.query(models.ComputerRental).options(
        joinedload(models.ComputerRental.computer),
        joinedload(models.ComputerRental.student),
        joinedload(models.ComputerRental.given_by),
        joinedload(models.ComputerRental.returned_by),
    )


@app.get("/computers")
def list_computers(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    q = db.query(models.Computer)
    if not include_inactive:
        q = q.filter(models.Computer.is_active.is_(True))
    computers = q.order_by(models.Computer.number).all()
    open_rentals = {
        r.computer_id: r
        for r in _rental_query(db).filter(models.ComputerRental.returned_at.is_(None)).all()
    }
    return [
        {
            "id": c.id, "number": c.number, "name": c.name, "note": c.note,
            "is_active": c.is_active,
            "current": _rental_dict(open_rentals[c.id]) if c.id in open_rentals else None,
        }
        for c in computers
    ]


@app.post("/computers", status_code=201)
def create_computer(
    payload: schemas.ComputerCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    existing = db.query(models.Computer).filter(models.Computer.number == payload.number).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail=f"{payload.number}-kompyuter allaqachon mavjud")
        # O'chirilgan raqam qayta qo'shilsa — eski yozuv tiklanadi (tarix bitta raqamda qoladi)
        existing.is_active = True
        existing.name = payload.name
        existing.note = payload.note
        db.commit()
        return {"id": existing.id}
    c = models.Computer(number=payload.number, name=payload.name, note=payload.note, created_at=tz.utcnow())
    db.add(c)
    db.commit()
    return {"id": c.id}


@app.post("/computers/bulk", status_code=201)
def create_computers_bulk(
    payload: schemas.ComputerBulkCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    """Oraliq bo'yicha qo'shish (masalan 51–60). Mavjud raqamlar o'tkazib yuboriladi."""
    lo, hi = sorted((payload.number_from, payload.number_to))
    if hi - lo >= 500:
        raise HTTPException(status_code=400, detail="Bir martada ko'pi bilan 500 ta kompyuter")
    existing = {
        c.number: c for c in
        db.query(models.Computer).filter(models.Computer.number.between(lo, hi)).all()
    }
    added = skipped = 0
    for n in range(lo, hi + 1):
        c = existing.get(n)
        if c is None:
            db.add(models.Computer(number=n, is_active=True, created_at=tz.utcnow()))
            added += 1
        elif not c.is_active:
            c.is_active = True
            added += 1
        else:
            skipped += 1
    db.commit()
    return {"added": added, "skipped": skipped}


@app.patch("/computers/{computer_id}")
def update_computer(
    computer_id: int,
    payload: schemas.ComputerUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    c = db.query(models.Computer).get(computer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Kompyuter topilmadi")
    data = payload.dict(exclude_unset=True)
    if "number" in data and data["number"] != c.number:
        clash = db.query(models.Computer).filter(models.Computer.number == data["number"]).first()
        if clash:
            raise HTTPException(status_code=400, detail=f"{data['number']}-raqam band")
    for k, v in data.items():
        if k == "number" and v is None:
            continue
        setattr(c, k, v)
    db.commit()
    return {"ok": True}


@app.delete("/computers/{computer_id}")
def delete_computer(
    computer_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    c = db.query(models.Computer).get(computer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Kompyuter topilmadi")
    busy = db.query(models.ComputerRental).filter(
        models.ComputerRental.computer_id == c.id, models.ComputerRental.returned_at.is_(None)
    ).first()
    if busy:
        raise HTTPException(status_code=400, detail="Kompyuter hozir talabada — avval qaytarib oling")
    c.is_active = False
    db.commit()
    return {"ok": True}


@app.get("/computers/students")
def computer_student_search(
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    """Berish oynasidagi talaba qidiruvi (ism yoki telefon bo'yicha)."""
    query = db.query(models.Student).filter(models.Student.is_archived.is_(False))
    term = q.strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(models.Student.full_name.ilike(like), models.Student.phone1.ilike(like)))
    rows = query.order_by(models.Student.full_name).limit(15).all()
    holding = dict(
        db.query(models.ComputerRental.student_id, models.Computer.number)
        .join(models.Computer, models.Computer.id == models.ComputerRental.computer_id)
        .filter(models.ComputerRental.returned_at.is_(None),
                models.ComputerRental.student_id.in_([s.id for s in rows] or [0]))
        .all()
    )
    return [
        {"id": s.id, "full_name": s.full_name, "phone": s.phone1, "has_computer": holding.get(s.id)}
        for s in rows
    ]


@app.post("/computers/{computer_id}/give", status_code=201)
def give_computer(
    computer_id: int,
    payload: schemas.ComputerGive,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_hunter),
):
    c = db.query(models.Computer).get(computer_id)
    if not c or not c.is_active:
        raise HTTPException(status_code=404, detail="Kompyuter topilmadi")
    student = db.query(models.Student).get(payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    busy = db.query(models.ComputerRental).filter(
        models.ComputerRental.computer_id == c.id, models.ComputerRental.returned_at.is_(None)
    ).first()
    if busy:
        raise HTTPException(status_code=400, detail=f"{c.number}-kompyuter hozir band")
    r = models.ComputerRental(
        computer_id=c.id, student_id=student.id, given_at=tz.utcnow(),
        given_by_id=actor.id, note=(payload.note or None),
    )
    db.add(r)
    db.commit()
    return _rental_dict(_rental_query(db).filter(models.ComputerRental.id == r.id).one())


@app.post("/computer-rentals/{rental_id}/return")
def return_computer(
    rental_id: int,
    payload: schemas.ComputerReturn,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_hunter),
):
    r = db.query(models.ComputerRental).get(rental_id)
    if not r:
        raise HTTPException(status_code=404, detail="Yozuv topilmadi")
    if r.returned_at is not None:
        raise HTTPException(status_code=400, detail="Kompyuter allaqachon qaytarilgan")
    r.returned_at = tz.utcnow()
    r.returned_by_id = actor.id
    r.return_note = payload.note or None
    db.commit()
    return _rental_dict(_rental_query(db).filter(models.ComputerRental.id == r.id).one())


@app.get("/computer-rentals")
def list_computer_rentals(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    computer_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    status_: Optional[str] = Query(None, alias="status", description="active | returned"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_hunter),
):
    """Berish jurnali. Sana filtri — berilgan kun (Toshkent) bo'yicha."""
    q = _rental_query(db)
    if date_from or date_to:
        start, end = tz.range_bounds(date_from or date_to, date_to or date_from)
        q = q.filter(models.ComputerRental.given_at >= start, models.ComputerRental.given_at < end)
    if computer_id:
        q = q.filter(models.ComputerRental.computer_id == computer_id)
    if student_id:
        q = q.filter(models.ComputerRental.student_id == student_id)
    if status_ == "active":
        q = q.filter(models.ComputerRental.returned_at.is_(None))
    elif status_ == "returned":
        q = q.filter(models.ComputerRental.returned_at.isnot(None))
    rows = q.order_by(models.ComputerRental.given_at.desc()).limit(1000).all()
    return [_rental_dict(r) for r in rows]


# ── Minar Space (space.minaracademy.uz) — o'quvchi kabineti API'si ────────────
# /space/... (o'quvchi ilovasi), /space/admin/... (xodimlar). Batafsil: backend/minar/__init__.py
from .minar import setup as _minar_setup
_minar_setup(app)
