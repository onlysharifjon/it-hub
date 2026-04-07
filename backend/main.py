import json
import os
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional
import io

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .models import UserRole

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")

auth_scheme = HTTPBearer(auto_error=False)

app = FastAPI(title="IT Hub — LMS API", version="3.0.0")

# ── Default users ──────────────────────────────────────────────────────────────

DEFAULT_USERS = [
    {"username": "admin",     "password": "Admin@2026",     "role": UserRole.admin.value,    "full_name": "Administrator"},
    {"username": "dev",       "password": "Dev@2026",       "role": UserRole.admin.value,    "full_name": "Developer"},
    {"username": "metodist",  "password": "Metodist@2026",  "role": UserRole.metodist.value, "full_name": "Metodist"},
    {"username": "teacher1",  "password": "Teacher@2026",   "role": UserRole.teacher.value,  "full_name": "Sarvar Toshmatov"},
    {"username": "teacher2",  "password": "Teacher@2026",   "role": UserRole.teacher.value,  "full_name": "Malika Yusupova"},
    {"username": "teacher3",  "password": "Teacher@2026",   "role": UserRole.teacher.value,  "full_name": "Jasur Rahimov"},
]


@app.on_event("startup")
def ensure_default_users() -> None:
    from .database import SessionLocal
    db = SessionLocal()
    try:
        for u in DEFAULT_USERS:
            exists = db.query(models.User).filter(models.User.username == u["username"]).first()
            if not exists:
                user = models.User(
                    username=u["username"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                    full_name=u.get("full_name"),
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                db.add(user)
        db.commit()
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


# ── Auth helpers ──────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


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
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise exc
    # Check expiry on each request
    if user.expires_at and datetime.utcnow() > user.expires_at:
        user.is_active = False
        user.blocked_reason = user.blocked_reason or "Akkount muddati tugadi"
        user.blocked_at = datetime.utcnow()
        db.commit()
        raise exc
    return user


def require_metodist(user: models.User = Depends(require_auth)) -> models.User:
    if user.role not in (UserRole.metodist.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="Bu amal faqat metodist/admin uchun")
    return user


def require_admin(user: models.User = Depends(require_auth)) -> models.User:
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Bu amal faqat admin uchun")
    return user


def _resolve_token(raw_token: str, db: Session) -> models.User:
    """Decode a raw JWT string and return the authenticated admin user."""
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
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise exc
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Bu amal faqat admin uchun")
    return user


def require_admin_download(
    _token: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Auth for file-download endpoints: accepts Bearer header OR ?_token= query param."""
    if _token:
        return _resolve_token(_token, db)
    if credentials and credentials.scheme.lower() == "bearer":
        return _resolve_token(credentials.credentials, db)
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
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
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

    token = create_access_token({"sub": user.username, "role": user.role})
    return schemas.TokenResponse(access_token=token)


@app.get("/auth/me", response_model=schemas.UserRead)
def me(user: models.User = Depends(require_auth)):
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
        q = q.filter(models.AuditLog.changed_at >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to:
        q = q.filter(models.AuditLog.changed_at < datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1))
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
def list_tariffs(db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    return db.query(models.Tariff).order_by(models.Tariff.name).all()


@app.post("/tariffs", response_model=schemas.TariffRead, status_code=201)
def create_tariff(payload: schemas.TariffCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    t = models.Tariff(**payload.dict())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@app.put("/tariffs/{tariff_id}", response_model=schemas.TariffRead)
def update_tariff(tariff_id: int, payload: schemas.TariffUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    t = db.query(models.Tariff).filter(models.Tariff.id == tariff_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarif topilmadi")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@app.delete("/tariffs/{tariff_id}", status_code=204)
def delete_tariff(tariff_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    t = db.query(models.Tariff).filter(models.Tariff.id == tariff_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarif topilmadi")
    db.delete(t)
    db.commit()


# ── Students endpoints ────────────────────────────────────────────────────────

def _student_read(s: models.Student) -> schemas.StudentRead:
    return schemas.StudentRead(
        id=s.id, full_name=s.full_name, phone1=s.phone1,
        father_name=s.father_name, father_phone=s.father_phone,
        mother_name=s.mother_name, mother_phone=s.mother_phone,
        telegram_id=s.telegram_id, notes=s.notes, is_active=s.is_active,
        is_archived=s.is_archived,
        created_at=s.created_at, group_count=len(s.group_memberships)
    )


@app.get("/students")
def list_students(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_archived: Optional[bool] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    q = db.query(models.Student)
    # by default exclude archived unless explicitly requested
    if is_archived is None:
        q = q.filter(models.Student.is_archived == False)
    else:
        q = q.filter(models.Student.is_archived == is_archived)
    if is_active is not None:
        q = q.filter(models.Student.is_active == is_active)
    if search:
        q = q.filter(
            models.Student.full_name.ilike(f"%{search}%") |
            models.Student.phone1.ilike(f"%{search}%") |
            models.Student.father_phone.ilike(f"%{search}%") |
            models.Student.mother_phone.ilike(f"%{search}%")
        )
    if date_from:
        q = q.filter(models.Student.created_at >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to:
        q = q.filter(models.Student.created_at < datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1))
    total = q.count()
    students = q.order_by(models.Student.full_name).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_student_read(s) for s in students],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    }


@app.get("/students/{student_id}", response_model=schemas.StudentRead)
def get_student(student_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    return _student_read(s)


@app.post("/students", response_model=schemas.StudentRead, status_code=201)
def create_student(payload: schemas.StudentCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    s = models.Student(**payload.dict())
    db.add(s)
    db.flush()
    write_audit(db, entity_type="student", entity_id=s.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(s)
    return _student_read(s)


@app.put("/students/{student_id}", response_model=schemas.StudentRead)
def update_student(student_id: int, payload: schemas.StudentUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    changes = payload.dict(exclude_unset=True)
    for k, v in changes.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return _student_read(s)


@app.post("/students/{student_id}/archive", response_model=schemas.StudentRead)
def archive_student(student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
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
def unarchive_student(student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
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
    total = schemas.STAGE_TOTAL_LESSONS.get(stage, 24)
    completed = 0
    if db is not None:
        completed = db.query(func.count(func.distinct(models.Attendance.lesson_date))).filter(
            models.Attendance.group_id == g.id
        ).scalar() or 0
    remaining = max(0, total - completed)
    pct = round(completed / total * 100, 1) if total > 0 else 0.0
    return schemas.GroupRead(
        id=g.id, name=g.name, stage=stage, teacher_id=g.teacher_id,
        teacher_name=g.teacher.full_name or g.teacher.username if g.teacher else None,
        course_price=g.course_price, schedule=g.schedule,
        start_date=g.start_date, is_active=g.is_active,
        created_at=g.created_at, student_count=len(g.members),
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
        ) for m in g.members
    ]
    base = _group_read(g, db=db)
    return schemas.GroupDetail(**base.dict(), members=members)


@app.get("/groups")
def list_groups(
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    q = db.query(models.Group)
    if is_active is not None:
        q = q.filter(models.Group.is_active == is_active)
    if search:
        q = q.filter(models.Group.name.ilike(f"%{search}%"))
    if date_from:
        q = q.filter(models.Group.start_date >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to:
        q = q.filter(models.Group.start_date < datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1))
    total = q.count()
    groups = q.order_by(models.Group.name).offset((page - 1) * page_size).limit(page_size).all()
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
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    # Teacher faqat o'z guruhini ko'ra oladi
    if actor.role == UserRole.teacher.value and g.teacher_id != actor.id:
        raise HTTPException(status_code=403, detail="Bu guruh sizga tegishli emas")
    return _group_detail(g, db=db)


@app.post("/groups", response_model=schemas.GroupRead, status_code=201)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
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
def update_group(group_id: int, payload: schemas.GroupUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(g, k, v)
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
def add_student_to_group(group_id: int, payload: schemas.AddStudentToGroup, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    s = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    exists = db.query(models.GroupStudent).filter(
        models.GroupStudent.group_id == group_id,
        models.GroupStudent.student_id == payload.student_id
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Talaba bu guruhda allaqachon mavjud")
    tariff_id = payload.tariff_id
    if tariff_id:
        tariff = db.query(models.Tariff).filter(models.Tariff.id == tariff_id).first()
        if not tariff:
            raise HTTPException(status_code=404, detail="Tarif topilmadi")
    elif g.course_price and g.course_price > 0:
        # Auto-assign a tariff matching the group's course_price
        matched = db.query(models.Tariff).filter(
            models.Tariff.price == g.course_price,
            models.Tariff.is_active == True,
        ).first()
        tariff_id = matched.id if matched else None
    gs = models.GroupStudent(group_id=group_id, student_id=payload.student_id, tariff_id=tariff_id)
    db.add(gs)
    db.commit()
    return {"message": "Talaba guruhga qo'shildi"}


@app.delete("/groups/{group_id}/students/{student_id}", status_code=204)
def remove_student_from_group(group_id: int, student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    gs = db.query(models.GroupStudent).filter(
        models.GroupStudent.group_id == group_id,
        models.GroupStudent.student_id == student_id
    ).first()
    if not gs:
        raise HTTPException(status_code=404, detail="Topilmadi")
    db.delete(gs)
    db.commit()


# ── Payments endpoints ────────────────────────────────────────────────────────

def _payment_read(p: models.Payment) -> schemas.PaymentRead:
    return schemas.PaymentRead(
        id=p.id, student_id=p.student_id,
        student_name=p.student.full_name if p.student else None,
        group_id=p.group_id,
        group_name=p.group.name if p.group else None,
        amount=p.amount, month=p.month, year=p.year,
        paid_at=p.paid_at, notes=p.notes
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
    _: models.User = Depends(require_admin),
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
        q = q.filter(models.Payment.paid_at >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to:
        q = q.filter(models.Payment.paid_at < datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1))
    total = q.count()
    payments = q.order_by(models.Payment.paid_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_payment_read(p) for p in payments],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    }


@app.post("/payments", response_model=schemas.PaymentRead, status_code=201)
def create_payment(payload: schemas.PaymentCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    p = models.Payment(**payload.dict(), paid_at=datetime.utcnow())
    db.add(p)
    db.flush()
    write_audit(db, entity_type="payment", entity_id=p.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(p)
    return _payment_read(p)


@app.put("/payments/{payment_id}", response_model=schemas.PaymentRead)
def update_payment(payment_id: int, payload: schemas.PaymentUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    p = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _payment_read(p)


@app.delete("/payments/{payment_id}", status_code=204)
def delete_payment(payment_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_admin)):
    p = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    db.delete(p)
    db.commit()


# ── Salary helper ─────────────────────────────────────────────────────────────

def _group_salary(db: Session, group: models.Group, month: int, year: int):
    """
    O'qituvchi maoshini hisoblaydi.
    Formula: teacher_pay_per_student × talaba_kelgan_darslar_soni
    (teacher_pay_per_student = 1 dars uchun 1 talabadan olinadigan summa)
    """
    pay_per = Decimal(str(group.teacher_pay_per_student or 0))
    if pay_per == 0:
        return Decimal(0), []

    total = Decimal(0)
    students = []
    for mem in group.members:
        attended = db.query(func.count(models.Attendance.id)).filter(
            models.Attendance.group_id   == group.id,
            models.Attendance.student_id == mem.student_id,
            models.Attendance.is_present == True,
            extract('month', models.Attendance.lesson_date) == month,
            extract('year',  models.Attendance.lesson_date) == year,
        ).scalar() or 0
        share = (pay_per * Decimal(str(attended))).quantize(Decimal('1'))
        total += share
        students.append({
            "student_id":   mem.student_id,
            "student_name": mem.student.full_name,
            "attended":     attended,
            "salary_share": float(share),
        })
    return total, students


# ── Statistics endpoints ──────────────────────────────────────────────────────

@app.get("/stats/overview", response_model=schemas.StatsOverview)
def stats_overview(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    now = datetime.utcnow()
    cur_month, cur_year = now.month, now.year
    sel_year = year or cur_year

    prev_month = cur_month - 1 if cur_month > 1 else 12
    prev_year = cur_year if cur_month > 1 else cur_year - 1

    total_students = db.query(func.count(models.Student.id)).scalar()
    active_students = db.query(func.count(models.Student.id)).filter(models.Student.is_active == True).scalar()
    total_groups = db.query(func.count(models.Group.id)).scalar()
    active_groups_count = db.query(func.count(models.Group.id)).filter(models.Group.is_active == True).scalar()

    # Load active groups for salary calculation
    active_grps = db.query(models.Group).filter(models.Group.is_active == True).all()

    def month_income(m, y):
        r = db.query(func.sum(models.Payment.amount)).filter(
            models.Payment.month == m, models.Payment.year == y
        ).scalar()
        return r or Decimal(0)

    def month_external_expenses(m, y):
        r = db.query(func.sum(models.Expense.amount)).filter(
            models.Expense.month == m, models.Expense.year == y
        ).scalar()
        return r or Decimal(0)

    def teacher_salary_for_month(grps, m, y):
        return sum((_group_salary(db, g, m, y)[0] for g in grps), Decimal(0))

    this_income = month_income(cur_month, cur_year)
    last_income = month_income(prev_month, prev_year)
    change_pct = float((this_income - last_income) / last_income * 100) if last_income else 0.0

    cur_teacher_salary = teacher_salary_for_month(active_grps, cur_month, cur_year)
    cur_external = month_external_expenses(cur_month, cur_year)
    cur_total_exp = cur_teacher_salary + cur_external
    cur_net_profit = this_income - cur_total_exp

    # All 12 months of selected year (Jan → Dec)
    history = []
    for m in range(1, 13):
        income = month_income(m, sel_year)
        pcount = db.query(func.count(models.Payment.id)).filter(
            models.Payment.month == m, models.Payment.year == sel_year
        ).scalar()
        ext_exp = month_external_expenses(m, sel_year)
        t_salary = teacher_salary_for_month(active_grps, m, sel_year)
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
    Formula: teacher_pay_per_student × attended_lessons  (per-lesson rate per student)
    """
    groups = db.query(models.Group).filter(models.Group.is_active == True).all()
    teachers: dict = {}
    grand_total = Decimal(0)

    for g in groups:
        group_salary, student_details = _group_salary(db, g, month, year)
        if group_salary == 0 and not student_details:
            continue

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
            "teacher_pay_per_student": float(pay_per),
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
    sel_month = month or date.today().month
    sel_year  = year  or date.today().year

    groups = (
        db.query(models.Group)
        .filter(models.Group.teacher_id == actor.id, models.Group.is_active == True)
        .order_by(models.Group.name)
        .all()
    )

    total_salary  = Decimal(0)
    total_students = 0
    groups_out = []

    for g in groups:
        stage      = g.stage or 'foundation'
        total_less = schemas.STAGE_TOTAL_LESSONS.get(stage, 24)
        completed  = db.query(func.count(func.distinct(models.Attendance.lesson_date))).filter(
            models.Attendance.group_id == g.id
        ).scalar() or 0
        pct = round(completed / total_less * 100, 1) if total_less > 0 else 0.0

        group_salary, student_salaries = _group_salary(db, g, sel_month, sel_year)

        # lessons held this month
        month_lessons = db.query(func.count(func.distinct(models.Attendance.lesson_date))).filter(
            models.Attendance.group_id == g.id,
            extract('month', models.Attendance.lesson_date) == sel_month,
            extract('year',  models.Attendance.lesson_date) == sel_year,
        ).scalar() or 0

        total_salary   += group_salary
        total_students += len(g.members)

        groups_out.append({
            "id":                      g.id,
            "name":                    g.name,
            "stage":                   stage,
            "schedule":                g.schedule or "",
            "start_date":              str(g.start_date) if g.start_date else None,
            "student_count":           len(g.members),
            "total_lessons":           total_less,
            "completed_lessons":       completed,
            "progress_pct":            pct,
            "teacher_pay_per_student": float(pay_per),
            "month_salary":            float(group_salary),
            "month_lessons_held":      month_lessons,
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


# ── Expenses endpoints ────────────────────────────────────────────────────────

@app.get("/expenses", response_model=List[schemas.ExpenseRead])
def list_expenses(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    q = db.query(models.Expense)
    if month is not None:
        q = q.filter(models.Expense.month == month)
    if year is not None:
        q = q.filter(models.Expense.year == year)
    return q.order_by(models.Expense.year.desc(), models.Expense.month.desc(), models.Expense.id.desc()).all()


@app.post("/expenses", response_model=schemas.ExpenseRead, status_code=201)
def create_expense(payload: schemas.ExpenseCreate, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    exp = models.Expense(**payload.dict())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@app.put("/expenses/{expense_id}", response_model=schemas.ExpenseRead)
def update_expense(expense_id: int, payload: schemas.ExpenseUpdate, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Xarajat topilmadi")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(exp, k, v)
    db.commit()
    db.refresh(exp)
    return exp


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Xarajat topilmadi")
    db.delete(exp)
    db.commit()


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

    html = f"""<!DOCTYPE html>
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
    <span class="val">{student.full_name if student else '—'}</span>
  </div>
  <div class="row">
    <span class="label">Guruh</span>
    <span class="val">{group.name if group else '—'}</span>
  </div>
  <div class="row">
    <span class="label">Oy</span>
    <span class="val">{month_name} {p.year}</span>
  </div>
  <div class="row">
    <span class="label">Sana</span>
    <span class="val">{paid_date}</span>
  </div>
  {f'<div class="row"><span class="label">Izoh</span><span class="val">{p.notes}</span></div>' if p.notes else ''}

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
    return HTMLResponse(content=html)


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


def _schedule_has_today(schedule: str, today_wd: int) -> bool:
    if not schedule:
        return False
    import re
    tokens = re.split(r'[\s,\-/]+', schedule.lower())
    return any(_DAY_WORDS.get(t) == today_wd for t in tokens)


@app.get("/attendance/today")
def today_groups(
    target_date: Optional[date] = Query(None),  # admin can pick any date
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_auth),
):
    """
    Groups for quick attendance.
    - Admin/metodist: ALL active groups, any date (default today).
    - Teacher: only their groups scheduled for today.
    """
    ref_date = target_date or date.today()
    ref_wd = ref_date.weekday()
    is_admin_or_metodist = actor.role in (UserRole.admin.value, UserRole.metodist.value)

    q = db.query(models.Group).filter(models.Group.is_active == True)
    if not is_admin_or_metodist:
        # Teacher: only their groups
        q = q.filter(models.Group.teacher_id == actor.id)
    groups = q.order_by(models.Group.name).all()

    result = []
    for g in groups:
        # Teacher: filter by today's schedule; admin sees all
        if not is_admin_or_metodist and not _schedule_has_today(g.schedule, ref_wd):
            continue
        taken = db.query(func.count(models.Attendance.id)).filter(
            models.Attendance.group_id == g.id,
            models.Attendance.lesson_date == ref_date,
        ).scalar() or 0
        result.append({
            "id": g.id,
            "name": g.name,
            "stage": g.stage or 'foundation',
            "schedule": g.schedule,
            "teacher_name": g.teacher.full_name or g.teacher.username if g.teacher else None,
            "student_count": len(g.members),
            "attendance_taken": taken > 0,
            "attendance_count": taken,
            "date": str(ref_date),
        })

    return result


# ── Finance: monthly summary ───────────────────────────────────────────────────

@app.get("/finance/monthly")
def finance_monthly(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """
    Monthly finance summary.
    Income formula: owed = tariff_price (full monthly price, attendance-independent).
    Students pay for the month regardless of how many lessons they attended.
    Teacher salary is attendance-based (handled separately).
    """
    groups = db.query(models.Group).filter(models.Group.is_active == True).all()
    result = []
    total_expected = Decimal(0)
    total_actual = Decimal(0)

    for g in groups:
        # Actual payments for this group this month
        actual = db.query(func.sum(models.Payment.amount)).filter(
            models.Payment.group_id == g.id,
            models.Payment.month == month,
            models.Payment.year == year,
        ).scalar() or Decimal(0)

        # Total lessons held for this group this month (informational)
        total_lessons_held = db.query(
            func.count(func.distinct(models.Attendance.lesson_date))
        ).filter(
            models.Attendance.group_id == g.id,
            extract('month', models.Attendance.lesson_date) == month,
            extract('year', models.Attendance.lesson_date) == year,
        ).scalar() or 0

        expected = Decimal(0)
        student_details = []

        for m in g.members:
            # Count lessons student attended this month (informational only)
            attended = db.query(func.count(models.Attendance.id)).filter(
                models.Attendance.group_id == g.id,
                models.Attendance.student_id == m.student_id,
                models.Attendance.is_present == True,
                extract('month', models.Attendance.lesson_date) == month,
                extract('year', models.Attendance.lesson_date) == year,
            ).scalar() or 0

            if m.tariff:
                price = Decimal(str(m.tariff.price))
                tariff_name = m.tariff.name
            elif g.course_price and Decimal(str(g.course_price)) > 0:
                # Fallback: use group's course_price if student has no individual tariff
                price = Decimal(str(g.course_price))
                tariff_name = "Guruh narxi"
            else:
                price = Decimal(0)
                tariff_name = None

            if price > 0:
                owed = price.quantize(Decimal('1'))
                tariff_price = float(price)
                paid_amount = db.query(func.sum(models.Payment.amount)).filter(
                    models.Payment.group_id == g.id,
                    models.Payment.student_id == m.student_id,
                    models.Payment.month == month,
                    models.Payment.year == year,
                ).scalar() or Decimal(0)
                is_paid = paid_amount >= owed
                expected += owed
            else:
                owed = Decimal(0)
                tariff_price = 0.0
                is_paid = None  # no obligation

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

        # Unpaid = has tariff, hasn't fully paid
        unpaid_students = [s for s in student_details if s["is_paid"] is False]

        total_expected += expected
        total_actual += actual
        result.append({
            "group_id": g.id,
            "group_name": g.name,
            "student_count": len(g.members),
            "expected": float(expected),
            "actual": float(actual),
            "deficit": float(expected - actual),
            "unpaid_count": len(unpaid_students),
            "unpaid_students": unpaid_students,
            "all_students": student_details,
        })

    return {
        "month": month,
        "year": year,
        "total_expected": float(total_expected),
        "total_actual": float(total_actual),
        "total_deficit": float(total_expected - total_actual),
        "groups": result,
    }


# ── Attendance ─────────────────────────────────────────────────────────────────

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

    members = (
        db.query(models.GroupStudent)
        .filter(models.GroupStudent.group_id == group_id)
        .all()
    )
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
    _: models.User = Depends(require_metodist),
):
    """Save attendance for a specific date. payload: [{student_id, is_present}]"""
    try:
        d = date.fromisoformat(lesson_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Sana formati xato (YYYY-MM-DD)")

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    for item in payload:
        sid = item.get("student_id")
        present = item.get("is_present", True)
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
            existing.is_present = present
        else:
            db.add(models.Attendance(
                group_id=group_id,
                student_id=sid,
                lesson_date=d,
                is_present=present,
            ))
    db.commit()
    return {"saved": len(payload), "date": lesson_date}


@app.delete("/groups/{group_id}/attendance/{lesson_date}")
def delete_attendance_date(
    group_id: int,
    lesson_date: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    """Delete all attendance records for a specific date."""
    try:
        d = date.fromisoformat(lesson_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Sana formati xato")

    db.query(models.Attendance).filter(
        models.Attendance.group_id == group_id,
        models.Attendance.lesson_date == d,
    ).delete()
    db.commit()
    return {"deleted": True, "date": lesson_date}
