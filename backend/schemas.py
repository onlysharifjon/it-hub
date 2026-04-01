from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from .models import UserRole


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Users ─────────────────────────────────────────────────────────────────────

class UserRead(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    blocked_reason:  Optional[str] = None
    blocked_contact: Optional[str] = None
    blocked_at:      Optional[datetime] = None
    expires_at:      Optional[datetime] = None
    created_at: datetime

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: UserRole = UserRole.teacher
    expires_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    password:        Optional[str]      = Field(None, min_length=6)
    full_name:       Optional[str]      = None
    role:            Optional[UserRole] = None
    is_active:       Optional[bool]     = None
    expires_at:      Optional[datetime] = None
    blocked_reason:  Optional[str]      = None
    blocked_contact: Optional[str]      = None


class BlockUserRequest(BaseModel):
    reason:  str = Field(..., min_length=3)
    contact: str = Field(..., min_length=3)


# ── Lessons ───────────────────────────────────────────────────────────────────

LESSON_CATEGORIES = {'foundation', 'frontend', 'backend'}


class LessonRead(BaseModel):
    id: int
    category: str
    lesson_number: int
    title: str
    section: Optional[str] = None
    guide: Optional[str] = None
    homework: Optional[str] = None
    extra_notes: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by_username: Optional[str] = None

    class Config:
        orm_mode = True

    @classmethod
    def from_orm(cls, obj):
        data = super().from_orm(obj)
        if obj.updated_by_user:
            data.updated_by_username = obj.updated_by_user.username
        return data


class LessonCreate(BaseModel):
    category: str = Field('foundation')
    lesson_number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=500)
    section: Optional[str] = None
    guide: Optional[str] = None
    homework: Optional[str] = None
    extra_notes: Optional[str] = None


class LessonUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    section: Optional[str] = None
    guide: Optional[str] = None
    homework: Optional[str] = None
    extra_notes: Optional[str] = None


class ReorderItem(BaseModel):
    id: int
    lesson_number: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLogRead(BaseModel):
    id: int
    entity_type: str
    entity_id: Optional[int]
    action: str
    changed_by_id: int
    changed_by_username: Optional[str] = None
    changed_at: datetime
    old_value: Optional[str] = None
    new_value: Optional[str] = None

    class Config:
        orm_mode = True

    @classmethod
    def from_orm(cls, obj):
        data = super().from_orm(obj)
        if obj.changed_by_user:
            data.changed_by_username = obj.changed_by_user.username
        return data


# ── Students ──────────────────────────────────────────────────────────────────

# ── Tariffs ───────────────────────────────────────────────────────────────────

class TariffRead(BaseModel):
    id: int
    name: str
    price: Decimal
    description: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class TariffCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    price: Decimal = Field(..., ge=0)
    description: Optional[str] = None


class TariffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    price: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ── Students ──────────────────────────────────────────────────────────────────

class StudentRead(BaseModel):
    id: int
    full_name: str
    phone1: str
    father_name:  Optional[str] = None
    father_phone: Optional[str] = None
    mother_name:  Optional[str] = None
    mother_phone: Optional[str] = None
    telegram_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    is_archived: bool = False
    created_at: datetime
    group_count: Optional[int] = 0

    class Config:
        orm_mode = True


class StudentCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    phone1: str = Field(..., min_length=7, max_length=20)
    father_name:  Optional[str] = Field(None, max_length=200)
    father_phone: Optional[str] = Field(None, max_length=20)
    mother_name:  Optional[str] = Field(None, max_length=200)
    mother_phone: Optional[str] = Field(None, max_length=20)
    telegram_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class StudentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    phone1: Optional[str] = Field(None, min_length=7, max_length=20)
    father_name:  Optional[str] = Field(None, max_length=200)
    father_phone: Optional[str] = Field(None, max_length=20)
    mother_name:  Optional[str] = Field(None, max_length=200)
    mother_phone: Optional[str] = Field(None, max_length=20)
    telegram_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None


# ── Groups ────────────────────────────────────────────────────────────────────

class GroupStudentRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    student_phone: Optional[str] = None
    joined_at: datetime
    tariff_id: Optional[int] = None
    tariff_name: Optional[str] = None
    tariff_price: Optional[Decimal] = None

    class Config:
        orm_mode = True


STAGE_LABELS = {'foundation': 'Foundation', 'frontend': 'Frontend', 'backend': 'Backend'}
STAGE_TOTAL_LESSONS = {'foundation': 24, 'frontend': 72, 'backend': 108}


class GroupRead(BaseModel):
    id: int
    name: str
    stage: str = 'foundation'
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    course_price: Decimal
    teacher_pay_per_student: Decimal = Decimal('0')
    schedule: Optional[str] = None
    start_date: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    student_count: Optional[int] = 0
    total_lessons: int = 24
    completed_lessons: int = 0
    remaining_lessons: int = 24
    progress_pct: float = 0.0

    class Config:
        orm_mode = True


class GroupDetail(GroupRead):
    members: List[GroupStudentRead] = []


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    stage: str = Field('foundation')
    teacher_id: Optional[int] = None
    course_price: Decimal = Field(..., ge=0)
    teacher_pay_per_student: Decimal = Field(Decimal('0'), ge=0)
    schedule: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    stage: Optional[str] = None
    teacher_id: Optional[int] = None
    course_price: Optional[Decimal] = Field(None, ge=0)
    teacher_pay_per_student: Optional[Decimal] = Field(None, ge=0)
    schedule: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class AddStudentToGroup(BaseModel):
    student_id: int
    tariff_id: Optional[int] = None


# ── Payments ──────────────────────────────────────────────────────────────────

class PaymentRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    group_id: int
    group_name: Optional[str] = None
    amount: Decimal
    month: int
    year: int
    paid_at: datetime
    notes: Optional[str] = None

    class Config:
        orm_mode = True


class PaymentCreate(BaseModel):
    student_id: int
    group_id: int
    amount: Decimal = Field(..., gt=0)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)
    notes: Optional[str] = None


class PaymentUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    month: Optional[int] = Field(None, ge=1, le=12)
    year: Optional[int] = Field(None, ge=2020)
    notes: Optional[str] = None


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseRead(BaseModel):
    id: int
    name: str
    amount: Decimal
    month: int
    year: int
    created_at: datetime

    class Config:
        orm_mode = True


class ExpenseCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=300)
    amount: Decimal = Field(..., gt=0)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)


class ExpenseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=300)
    amount: Optional[Decimal] = Field(None, gt=0)
    month: Optional[int] = Field(None, ge=1, le=12)
    year: Optional[int] = Field(None, ge=2020)


# ── Statistics ────────────────────────────────────────────────────────────────

class MonthlyStats(BaseModel):
    year: int
    month: int
    total_income: Decimal
    payment_count: int
    active_students: int
    active_groups: int
    teacher_salary: Decimal = Decimal('0')
    external_expenses: Decimal = Decimal('0')
    total_expenses: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class StatsOverview(BaseModel):
    total_students: int
    active_students: int
    total_groups: int
    active_groups: int
    this_month_income: Decimal
    last_month_income: Decimal
    income_change_pct: float
    teacher_salary: Decimal = Decimal('0')
    external_expenses: Decimal = Decimal('0')
    total_expenses: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    monthly_history: List[MonthlyStats]
