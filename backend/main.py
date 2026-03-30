import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
import io

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

auth_scheme = HTTPBearer(auto_error=False)

app = FastAPI(title="IT Hub — LMS API", version="3.0.0")

# ── Default users ──────────────────────────────────────────────────────────────

DEFAULT_USERS = [
    {"username": "admin",    "password": "Admin@2026",     "role": UserRole.admin.value,    "full_name": "Administrator"},
    {"username": "metodist", "password": "Metodist@2026",  "role": UserRole.metodist.value, "full_name": "Metodist"},
    {"username": "teacher",  "password": "Teacher@2026",   "role": UserRole.teacher.value,  "full_name": "O'qituvchi"},
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
    return user


def require_metodist(user: models.User = Depends(require_auth)) -> models.User:
    if user.role not in (UserRole.metodist.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="Bu amal faqat metodist/admin uchun")
    return user


def require_admin(user: models.User = Depends(require_auth)) -> models.User:
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Bu amal faqat admin uchun")
    return user


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
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Login yoki parol xato")
    token = create_access_token({"sub": user.username, "role": user.role})
    return schemas.TokenResponse(access_token=token)


@app.get("/auth/me", response_model=schemas.UserRead)
def me(user: models.User = Depends(require_auth)):
    return user


# ── Users endpoints ───────────────────────────────────────────────────────────

@app.get("/users", response_model=List[schemas.UserRead])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    return db.query(models.User).order_by(models.User.id).all()


@app.post("/users", response_model=schemas.UserRead, status_code=201)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Bu username allaqachon mavjud")
    user = models.User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()
    write_audit(db, entity_type="user", entity_id=user.id, action="create",
                changed_by_id=actor.id, new_value={"username": user.username, "role": user.role})
    db.commit()
    db.refresh(user)
    return user


@app.put("/users/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    old = {"role": user.role, "is_active": user.is_active}
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.full_name is not None:
        user.full_name = payload.full_name
    write_audit(db, entity_type="user", entity_id=user.id, action="update",
                changed_by_id=actor.id, old_value=old, new_value={"role": user.role, "is_active": user.is_active})
    db.commit()
    db.refresh(user)
    return user


# ── Lessons endpoints ─────────────────────────────────────────────────────────

@app.get("/lessons", response_model=List[schemas.LessonRead])
def list_lessons(db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    return db.query(models.Lesson).order_by(models.Lesson.lesson_number).all()


@app.get("/lessons/month/{month}", response_model=List[schemas.LessonRead])
def lessons_by_month(month: int, db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    return db.query(models.Lesson).filter(models.Lesson.month == month).order_by(models.Lesson.lesson_number).all()


@app.get("/lessons/{lesson_id}", response_model=schemas.LessonRead)
def get_lesson(lesson_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_auth)):
    lesson = db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    return lesson


@app.post("/lessons", response_model=schemas.LessonRead, status_code=201)
def create_lesson(payload: schemas.LessonCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
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

@app.get("/audit-logs", response_model=List[schemas.AuditLogRead])
def list_audit_logs(limit: int = 100, offset: int = 0, db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    return db.query(models.AuditLog).order_by(models.AuditLog.changed_at.desc()).offset(offset).limit(limit).all()


@app.get("/audit-logs/lesson/{lesson_id}", response_model=List[schemas.AuditLogRead])
def lesson_audit_logs(lesson_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    return (db.query(models.AuditLog)
            .filter(models.AuditLog.entity_type == "lesson", models.AuditLog.entity_id == lesson_id)
            .order_by(models.AuditLog.changed_at.desc()).all())


# ── Students endpoints ────────────────────────────────────────────────────────

def _student_read(s: models.Student) -> schemas.StudentRead:
    return schemas.StudentRead(
        id=s.id, full_name=s.full_name, phone1=s.phone1, phone2=s.phone2,
        telegram_id=s.telegram_id, notes=s.notes, is_active=s.is_active,
        created_at=s.created_at, group_count=len(s.group_memberships)
    )


@app.get("/students", response_model=List[schemas.StudentRead])
def list_students(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    q = db.query(models.Student)
    if is_active is not None:
        q = q.filter(models.Student.is_active == is_active)
    if search:
        q = q.filter(models.Student.full_name.ilike(f"%{search}%") | models.Student.phone1.ilike(f"%{search}%"))
    students = q.order_by(models.Student.full_name).all()
    return [_student_read(s) for s in students]


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


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Talaba topilmadi")
    db.delete(s)
    db.commit()


# ── Groups endpoints ──────────────────────────────────────────────────────────

def _group_read(g: models.Group) -> schemas.GroupRead:
    return schemas.GroupRead(
        id=g.id, name=g.name, teacher_id=g.teacher_id,
        teacher_name=g.teacher.full_name or g.teacher.username if g.teacher else None,
        course_price=g.course_price, schedule=g.schedule,
        start_date=g.start_date, is_active=g.is_active,
        created_at=g.created_at, student_count=len(g.members)
    )


def _group_detail(g: models.Group) -> schemas.GroupDetail:
    members = [
        schemas.GroupStudentRead(
            id=m.id, student_id=m.student_id,
            student_name=m.student.full_name,
            student_phone=m.student.phone1,
            joined_at=m.joined_at
        ) for m in g.members
    ]
    base = _group_read(g)
    return schemas.GroupDetail(**base.dict(), members=members)


@app.get("/groups", response_model=List[schemas.GroupRead])
def list_groups(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_metodist),
):
    q = db.query(models.Group)
    if is_active is not None:
        q = q.filter(models.Group.is_active == is_active)
    return [_group_read(g) for g in q.order_by(models.Group.name).all()]


@app.get("/groups/{group_id}", response_model=schemas.GroupDetail)
def get_group(group_id: int, db: Session = Depends(get_db), _: models.User = Depends(require_metodist)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    return _group_detail(g)


@app.post("/groups", response_model=schemas.GroupRead, status_code=201)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    g = models.Group(**payload.dict())
    db.add(g)
    db.flush()
    write_audit(db, entity_type="group", entity_id=g.id, action="create",
                changed_by_id=actor.id, new_value=payload.dict())
    db.commit()
    db.refresh(g)
    return _group_read(g)


@app.put("/groups/{group_id}", response_model=schemas.GroupRead)
def update_group(group_id: int, payload: schemas.GroupUpdate, db: Session = Depends(get_db), actor: models.User = Depends(require_metodist)):
    g = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(g, k, v)
    db.commit()
    db.refresh(g)
    return _group_read(g)


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
    gs = models.GroupStudent(group_id=group_id, student_id=payload.student_id)
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


@app.get("/payments", response_model=List[schemas.PaymentRead])
def list_payments(
    student_id: Optional[int] = Query(None),
    group_id: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
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
    return [_payment_read(p) for p in q.order_by(models.Payment.paid_at.desc()).all()]


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


# ── Statistics endpoints ──────────────────────────────────────────────────────

@app.get("/stats/overview", response_model=schemas.StatsOverview)
def stats_overview(db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    now = datetime.utcnow()
    cur_month, cur_year = now.month, now.year
    prev_month = cur_month - 1 if cur_month > 1 else 12
    prev_year = cur_year if cur_month > 1 else cur_year - 1

    total_students = db.query(func.count(models.Student.id)).scalar()
    active_students = db.query(func.count(models.Student.id)).filter(models.Student.is_active == True).scalar()
    total_groups = db.query(func.count(models.Group.id)).scalar()
    active_groups = db.query(func.count(models.Group.id)).filter(models.Group.is_active == True).scalar()

    def month_income(m, y):
        r = db.query(func.sum(models.Payment.amount)).filter(
            models.Payment.month == m, models.Payment.year == y
        ).scalar()
        return r or Decimal(0)

    this_income = month_income(cur_month, cur_year)
    last_income = month_income(prev_month, prev_year)
    change_pct = float((this_income - last_income) / last_income * 100) if last_income else 0.0

    # Last 12 months history
    history = []
    for i in range(11, -1, -1):
        m = (cur_month - i - 1) % 12 + 1
        y = cur_year - (i + cur_month - 1) // 12
        income = month_income(m, y)
        pcount = db.query(func.count(models.Payment.id)).filter(
            models.Payment.month == m, models.Payment.year == y
        ).scalar()
        history.append(schemas.MonthlyStats(
            year=y, month=m, total_income=income,
            payment_count=pcount,
            active_students=active_students,
            active_groups=active_groups
        ))

    return schemas.StatsOverview(
        total_students=total_students,
        active_students=active_students,
        total_groups=total_groups,
        active_groups=active_groups,
        this_month_income=this_income,
        last_month_income=last_income,
        income_change_pct=change_pct,
        monthly_history=history,
    )


@app.get("/stats/export/excel")
def export_payments_excel(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
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
