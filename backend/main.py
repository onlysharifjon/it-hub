import json
import os
from datetime import datetime, timedelta
from typing import List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .models import UserRole

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

auth_scheme = HTTPBearer(auto_error=False)

app = FastAPI(title="IT Hub — Metodika API", version="2.0.0")


# ── Default users (auto-created on startup) ───────────────────────────────────

DEFAULT_USERS = [
    {"username": "admin",    "password": "Admin@2026",     "role": UserRole.admin.value},
    {"username": "metodist", "password": "Metodist@2026",  "role": UserRole.metodist.value},
    {"username": "teacher",  "password": "Teacher@2026",   "role": UserRole.teacher.value},
]


@app.on_event("startup")
def ensure_default_users() -> None:
    """Dastur ishga tushganda 3 ta default user yo'q bo'lsa yaratadi."""
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
    return user


def require_metodist(user: models.User = Depends(require_auth)) -> models.User:
    """Metodist va Admin o'ta oladi."""
    if user.role not in (UserRole.metodist.value, UserRole.admin.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu amal faqat metodist/admin uchun ruxsat etilgan",
        )
    return user


def require_admin(user: models.User = Depends(require_auth)) -> models.User:
    """Faqat Admin o'ta oladi."""
    if user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu amal faqat admin uchun ruxsat etilgan",
        )
    return user


# ── Audit log helper ──────────────────────────────────────────────────────────

def write_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: int | None,
    action: str,
    changed_by_id: int,
    old_value=None,
    new_value=None,
) -> None:
    log = models.AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_by_id=changed_by_id,
        changed_at=datetime.utcnow(),
        old_value=json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
        new_value=json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
    )
    db.add(log)


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol xato",
        )
    token = create_access_token({"sub": user.username, "role": user.role})
    return schemas.TokenResponse(access_token=token)


@app.get("/auth/me", response_model=schemas.UserRead)
def me(user: models.User = Depends(require_auth)):
    return user


# ── Users endpoints (metodist only) ──────────────────────────────────────────

@app.get("/users", response_model=List[schemas.UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    return db.query(models.User).order_by(models.User.id).all()


@app.post("/users", response_model=schemas.UserRead, status_code=201)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_metodist),
):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Bu username allaqachon mavjud")
    user = models.User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    write_audit(db, entity_type="user", entity_id=user.id, action="create",
                changed_by_id=actor.id, new_value={"username": user.username, "role": user.role.value})
    db.commit()
    db.refresh(user)
    return user


@app.put("/users/{user_id}", response_model=schemas.UserRead)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_metodist),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    old = {"role": user.role.value, "is_active": user.is_active}
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    new = {"role": user.role.value, "is_active": user.is_active}
    write_audit(db, entity_type="user", entity_id=user.id, action="update",
                changed_by_id=actor.id, old_value=old, new_value=new)
    db.commit()
    db.refresh(user)
    return user


# ── Lessons endpoints ─────────────────────────────────────────────────────────

@app.get("/lessons", response_model=List[schemas.LessonRead])
def list_lessons(db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    return db.query(models.Lesson).order_by(models.Lesson.lesson_number).all()


@app.get("/lessons/month/{month}", response_model=List[schemas.LessonRead])
def lessons_by_month(
    month: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_auth),
):
    return (
        db.query(models.Lesson)
        .filter(models.Lesson.month == month)
        .order_by(models.Lesson.lesson_number)
        .all()
    )


@app.get("/lessons/{lesson_id}", response_model=schemas.LessonRead)
def get_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_auth),
):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    return lesson


@app.post("/lessons", response_model=schemas.LessonRead, status_code=201)
def create_lesson(
    payload: schemas.LessonCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_metodist),
):
    if db.query(models.Lesson).filter(models.Lesson.lesson_number == payload.lesson_number).first():
        raise HTTPException(status_code=400, detail="Bu dars raqami allaqachon mavjud")
    lesson = models.Lesson(**payload.dict(), updated_at=datetime.utcnow(), updated_by_id=actor.id)
    db.add(lesson)
    db.flush()
    write_audit(db, entity_type="lesson", entity_id=lesson.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(lesson)
    return lesson


@app.put("/lessons/reorder", response_model=List[schemas.LessonRead])
def reorder_lessons(
    payload: schemas.ReorderRequest,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_metodist),
):
    old_order = {}
    lessons_map = {}
    for item in payload.items:
        lesson = db.query(models.Lesson).filter(models.Lesson.id == item.id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail=f"Dars {item.id} topilmadi")
        old_order[item.id] = lesson.lesson_number
        lessons_map[item.id] = (lesson, item.lesson_number)

    # Use large temporary offsets to avoid unique constraint during batch update
    OFFSET = 100_000
    now = datetime.utcnow()
    for lesson, _ in lessons_map.values():
        lesson.lesson_number = lesson.lesson_number + OFFSET
    db.flush()

    for lesson, new_num in lessons_map.values():
        lesson.lesson_number = new_num
        lesson.updated_at = now
        lesson.updated_by_id = actor.id

    write_audit(
        db, entity_type="lesson", entity_id=None, action="reorder",
        changed_by_id=actor.id,
        old_value={str(k): v for k, v in old_order.items()},
        new_value={str(i.id): i.lesson_number for i in payload.items},
    )
    db.commit()
    updated = [lessons_map[item.id][0] for item in payload.items]
    for lesson in updated:
        db.refresh(lesson)
    return updated


@app.put("/lessons/{lesson_id}", response_model=schemas.LessonRead)
def update_lesson(
    lesson_id: int,
    payload: schemas.LessonUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_metodist),
):
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
def delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_metodist),
):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    old_value = {"title": lesson.title, "lesson_number": lesson.lesson_number}
    write_audit(db, entity_type="lesson", entity_id=lesson_id, action="delete",
                changed_by_id=actor.id, old_value=old_value)
    db.delete(lesson)
    db.commit()


# ── Audit log endpoints ───────────────────────────────────────────────────────

@app.get("/audit-logs", response_model=List[schemas.AuditLogRead])
def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.changed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@app.get("/audit-logs/lesson/{lesson_id}", response_model=List[schemas.AuditLogRead])
def lesson_audit_logs(
    lesson_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    return (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.entity_type == "lesson",
            models.AuditLog.entity_id == lesson_id,
        )
        .order_by(models.AuditLog.changed_at.desc())
        .all()
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}