from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Literal

from pydantic import BaseModel, Field

from .models import UserRole, LeadStatus


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
    avatar: Optional[str] = None
    blocked_reason:  Optional[str] = None
    blocked_contact: Optional[str] = None
    blocked_at:      Optional[datetime] = None
    expires_at:      Optional[datetime] = None
    created_at: datetime

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    role: UserRole = UserRole.teacher
    expires_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    password:        Optional[str]      = Field(None, min_length=8, max_length=128)
    full_name:       Optional[str]      = None
    role:            Optional[UserRole] = None
    is_active:       Optional[bool]     = None
    expires_at:      Optional[datetime] = None
    blocked_reason:  Optional[str]      = None
    blocked_contact: Optional[str]      = None


class ProfileUpdate(BaseModel):
    """O'z profilini tahrirlash — har qanday foydalanuvchi o'zi uchun."""
    full_name:        Optional[str] = Field(None, max_length=200)
    password:         Optional[str] = Field(None, min_length=8, max_length=128)
    current_password: Optional[str] = None


# ── Leads ─────────────────────────────────────────────────────────────────────

# ── Lead stages (pipeline) ──────────────────────────────────────────────────

class LeadStageCreate(BaseModel):
    name:  str = Field(..., min_length=1, max_length=80)
    color: str = Field("slate", max_length=20)
    icon:  str = Field("circle", max_length=40)
    kind:  str = Field("lead", regex="^(lead|won|lost)$")


class LeadStageUpdate(BaseModel):
    name:  Optional[str] = Field(None, min_length=1, max_length=80)
    color: Optional[str] = None
    icon:  Optional[str] = None
    kind:  Optional[str] = Field(None, regex="^(lead|won|lost)$")
    is_archived: Optional[bool] = None


class LeadStageRead(BaseModel):
    id:          int
    name:        str
    slug:        str
    order:       int
    color:       str
    icon:        str
    kind:        str
    is_archived: bool
    lead_count:  int = 0

    class Config:
        orm_mode = True


class StageReorder(BaseModel):
    ordered_ids: List[int]


# ── Lead sources ────────────────────────────────────────────────────────────

class LeadSourceCreate(BaseModel):
    name:        str  = Field(..., min_length=1, max_length=80)
    is_campaign: bool = False


class LeadSourceUpdate(BaseModel):
    name:        Optional[str]  = Field(None, min_length=1, max_length=80)
    is_campaign: Optional[bool] = None
    is_active:   Optional[bool] = None


class LeadSourceRead(BaseModel):
    id:          int
    name:        str
    is_campaign: bool
    is_default:  bool
    is_active:   bool

    class Config:
        orm_mode = True


# ── Lead activities (timeline) ──────────────────────────────────────────────

class LeadActivityRead(BaseModel):
    id:          int
    action:      str
    description: Optional[str]      = None
    author_name: Optional[str]      = None
    created_at:  datetime

    class Config:
        orm_mode = True


# ── Leads ───────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    full_name:           str            = Field(..., min_length=2, max_length=200)
    phone:               str            = Field(..., min_length=7, max_length=30)
    course_interest:     Optional[str]  = None
    source_id:           Optional[int]  = None
    notes:               Optional[str]  = None
    date_of_birth:       Optional[date]  = None
    parent_phone:        Optional[str]  = Field(None, max_length=30)
    parent2_phone:       Optional[str]  = Field(None, max_length=30)
    interested_group_id: Optional[int]  = None


class LeadStatusUpdate(BaseModel):
    status:      LeadStatus
    callback_at: Optional[datetime] = None
    notes:       Optional[str]      = None


class LeadStageMove(BaseModel):
    stage_id:    int
    callback_at: Optional[datetime] = None
    notes:       Optional[str]      = None


class LeadRead(BaseModel):
    id:              int
    full_name:       str
    phone:           str
    course_interest: Optional[str]      = None
    status:          str
    stage_id:        Optional[int]      = None
    stage_name:      Optional[str]      = None
    stage_color:     Optional[str]      = None
    stage_icon:      Optional[str]      = None
    stage_kind:      Optional[str]      = None
    source_id:       Optional[int]      = None
    source_name:     Optional[str]      = None
    callback_at:     Optional[datetime] = None
    notes:           Optional[str]      = None
    date_of_birth:       Optional[date] = None
    parent_phone:        Optional[str]  = None
    parent2_phone:       Optional[str]  = None
    interested_group_id: Optional[int]  = None
    interested_group_name: Optional[str] = None
    is_shared:       bool               = False
    claimed_by_id:   Optional[int]      = None
    claimed_by_name: Optional[str]      = None
    created_by_id:   int
    created_by_name: Optional[str]      = None
    updated_by_name: Optional[str]      = None
    created_at:      datetime
    updated_at:      Optional[datetime] = None

    class Config:
        orm_mode = True


class LeadStageStat(BaseModel):
    slug:  str
    name:  str
    color: str
    icon:  str
    kind:  str
    order: int
    count: int


class LeadStatsRead(BaseModel):
    total:  int
    stages: List[LeadStageStat]


# ── Reminders / tasks ───────────────────────────────────────────────────────

class ReminderCreate(BaseModel):
    lead_id:        int
    due_at:         datetime
    body:           Optional[str] = None
    kind:           str = Field("call", regex="^(call|visit|other)$")
    assigned_to_id: Optional[int] = None


class ReminderUpdate(BaseModel):
    due_at:         Optional[datetime] = None
    body:           Optional[str]      = None
    kind:           Optional[str]      = Field(None, regex="^(call|visit|other)$")
    status:         Optional[str]      = Field(None, regex="^(pending|done|dismissed)$")
    snoozed_until:  Optional[datetime] = None
    assigned_to_id: Optional[int]      = None


class ReminderRead(BaseModel):
    id:               int
    lead_id:          int
    lead_name:        Optional[str]      = None
    lead_phone:       Optional[str]      = None
    assigned_to_id:   Optional[int]      = None
    assigned_to_name: Optional[str]      = None
    due_at:           datetime
    body:             Optional[str]      = None
    kind:             str
    status:           str
    snoozed_until:    Optional[datetime] = None
    is_overdue:       bool = False
    created_at:       datetime

    class Config:
        orm_mode = True


# ── Notifications ───────────────────────────────────────────────────────────

class NotificationRead(BaseModel):
    id:                int
    notification_type: str
    title:             str
    body:              Optional[str] = None
    link:              Optional[str] = None
    is_read:           bool
    created_at:        datetime

    class Config:
        orm_mode = True


# ── Lead analytics ──────────────────────────────────────────────────────────

class FunnelStep(BaseModel):
    slug:       str
    name:       str
    color:      str
    count:      int
    percentage: float


class SourceStat(BaseModel):
    source:          str
    total:           int
    enrolled:        int
    conversion_rate: float


class LeadAnalyticsRead(BaseModel):
    total:        int
    won:          int
    lost:         int
    conversion:   float
    distribution: List[FunnelStep]
    sources:      List[SourceStat]


# ── Intake forms (public lead capture) ──────────────────────────────────────

class IntakeFormCreate(BaseModel):
    name:        str           = Field(..., min_length=1, max_length=150)
    title:       Optional[str] = None
    description: Optional[str] = None
    source_id:   Optional[int] = None


class IntakeFormUpdate(BaseModel):
    name:        Optional[str]  = Field(None, min_length=1, max_length=150)
    title:       Optional[str]  = None
    description: Optional[str]  = None
    source_id:   Optional[int]  = None
    is_active:   Optional[bool] = None


class IntakeFormRead(BaseModel):
    id:          int
    slug:        str
    name:        str
    title:       Optional[str] = None
    description: Optional[str] = None
    source_id:   Optional[int] = None
    source_name: Optional[str] = None
    is_active:   bool
    submissions: int
    created_at:  datetime

    class Config:
        orm_mode = True


class PublicIntakeConfig(BaseModel):
    slug:        str
    name:        str
    title:       Optional[str] = None
    description: Optional[str] = None
    is_active:   bool


class PublicLeadSubmit(BaseModel):
    full_name:       str           = Field(..., min_length=2, max_length=200)
    phone:           str           = Field(..., min_length=7, max_length=30)
    course_interest: Optional[str] = Field(None, max_length=200)
    parent_phone:    Optional[str] = Field(None, max_length=30)
    notes:           Optional[str] = Field(None, max_length=2000)


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

# ── Courses ───────────────────────────────────────────────────────────────────

class CourseRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    total_lessons: int
    duration_months: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    total_lessons: int = Field(..., ge=1)
    duration_months: Optional[int] = Field(None, ge=1)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    total_lessons: Optional[int] = Field(None, ge=1)
    duration_months: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


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
    telegram_user_id: Optional[str] = None
    photo: Optional[str] = None
    photo_url:   Optional[str] = None
    notes: Optional[str] = None
    advance_balance: Optional[Decimal] = Decimal('0')
    is_active: bool
    is_archived: bool = False
    created_at: datetime
    group_count: Optional[int] = 0
    group_names: Optional[List[str]] = []
    # Joriy oy to'lov holati
    owed_month:      Optional[Decimal] = None
    paid_month:      Optional[Decimal] = None
    debt:            Optional[Decimal] = None
    advance_applied: Optional[Decimal] = None   # qarzni qoplashga ishlatilgan avans
    payment_status:  Optional[str]     = None   # paid | partial | debtor | none

    class Config:
        orm_mode = True


class CameraCheckin(BaseModel):
    student_id: int
    event: str          # "arrival" | "departure"
    detected_at: Optional[datetime] = None


class StudentCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    phone1: str = Field(..., min_length=7, max_length=20)
    father_name:  Optional[str] = Field(None, max_length=200)
    father_phone: Optional[str] = Field(None, max_length=20)
    mother_name:  Optional[str] = Field(None, max_length=200)
    mother_phone: Optional[str] = Field(None, max_length=20)
    telegram_id: Optional[str] = Field(None, max_length=120)
    telegram_user_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    advance: Decimal = Field(Decimal('0'), ge=0)   # avans (yangi ro'yxatda)


class StudentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    phone1: Optional[str] = Field(None, min_length=7, max_length=20)
    father_name:  Optional[str] = Field(None, max_length=200)
    father_phone: Optional[str] = Field(None, max_length=20)
    mother_name:  Optional[str] = Field(None, max_length=200)
    mother_phone: Optional[str] = Field(None, max_length=20)
    telegram_id: Optional[str] = Field(None, max_length=120)
    telegram_user_id: Optional[str] = Field(None, max_length=50)
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
    course_id: Optional[int] = None
    course_name: Optional[str] = None
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    course_price: Decimal
    teacher_pay_per_student: Decimal = Decimal('0')
    schedule: Optional[str] = None
    start_date: Optional[datetime] = None
    is_active: bool
    telegram_chat_id: Optional[str] = None
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
    course_id: Optional[int] = None
    teacher_id: Optional[int] = None
    course_price: Decimal = Field(..., ge=0)
    teacher_pay_per_student: Decimal = Field(Decimal('0'), ge=0)
    schedule: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    telegram_chat_id: Optional[str] = Field(None, max_length=50)


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    stage: Optional[str] = None
    course_id: Optional[int] = None
    teacher_id: Optional[int] = None
    course_price: Optional[Decimal] = Field(None, ge=0)
    teacher_pay_per_student: Optional[Decimal] = Field(None, ge=0)
    schedule: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    telegram_chat_id: Optional[str] = Field(None, max_length=50)


class AddStudentToGroup(BaseModel):
    student_id: int
    tariff_id: Optional[int] = None


# ── Payments ──────────────────────────────────────────────────────────────────

class StudentGroupFee(BaseModel):
    group_id:   int
    group_name: str
    owed:       Decimal
    paid:       Decimal
    remaining:  Decimal


class StudentPaymentSummary(BaseModel):
    student_id:      int
    student_name:    str
    month:           int
    year:            int
    advance_balance: Decimal
    total_owed:      Decimal
    total_paid:      Decimal
    debt:            Decimal
    payment_status:  str
    groups:          List[StudentGroupFee]
    recent_payments: List["PaymentRead"]


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
    recorded_by_name: Optional[str] = None    # kim qabul qilgan
    # Oylik qarz holati (student-group-month bo'yicha):
    expected: Optional[Decimal] = None    # to'liq oylik summa
    paid_total: Optional[Decimal] = None  # shu oy uchun jami to'langan
    remaining: Optional[Decimal] = None   # qolgan summa
    status: Optional[str] = None          # 'paid' | 'partial'

    class Config:
        orm_mode = True


StudentPaymentSummary.update_forward_refs()


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


# ── Parent akkaunt boshqaruvi (hunter/admin) ─────────────────────────────────

class ParentAccountCreate(BaseModel):
    full_name:    str            = Field(..., min_length=2, max_length=200)
    phone:        str            = Field(..., min_length=7, max_length=30)
    username:     Optional[str]  = Field(None, min_length=3, max_length=100)  # bo'sh -> telefon
    password:     Optional[str]  = Field(None, min_length=6, max_length=128)  # bo'sh -> avto
    display_name: Optional[str]  = Field(None, max_length=120)
    student_ids:  List[int]      = []


class ParentAccountUpdate(BaseModel):
    full_name:    Optional[str]  = Field(None, min_length=2, max_length=200)
    display_name: Optional[str]  = None
    phone:        Optional[str]  = Field(None, min_length=7, max_length=30)
    is_active:    Optional[bool] = None


class ResetParentPassword(BaseModel):
    password: Optional[str] = Field(None, min_length=6, max_length=128)   # bo'sh -> avto


class LinkChildRequest(BaseModel):
    student_id: int


class ParentChildInfo(BaseModel):
    student_id:   int
    student_name: str


class ParentAccountRead(BaseModel):
    id:           int
    full_name:    str
    display_name: Optional[str] = None
    phone:        str
    username:     str
    is_active:    bool
    created_at:   datetime
    children:     List[ParentChildInfo] = []

    class Config:
        orm_mode = True


class ParentAccountCreated(ParentAccountRead):
    # Yaratilganda parolni BIR MARTA qaytaramiz (keyin ko'rsatilmaydi)
    generated_password: Optional[str] = None


# ── Schedule slotlar (strukturaviy jadval) ───────────────────────────────────

class ScheduleSlotCreate(BaseModel):
    day_of_week: int           = Field(..., ge=1, le=7)   # 1=Du .. 7=Yak
    start_time:  str           = Field(..., regex=r"^\d{2}:\d{2}$")
    end_time:    str           = Field(..., regex=r"^\d{2}:\d{2}$")
    room:        Optional[str] = Field(None, max_length=50)


class ScheduleSlotRead(BaseModel):
    id:          int
    group_id:    int
    day_of_week: int
    start_time:  str
    end_time:    str
    room:        Optional[str] = None

    class Config:
        orm_mode = True


# ── Student visits (Notifications: keldi/ketdi) ──────────────────────────────

class StudentVisitRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    student_photo: Optional[str] = None
    kind: str                                # arrived | left
    noted_by_name: Optional[str] = None
    telegram_sent: bool = False
    telegram_error: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class StudentVisitCreate(BaseModel):
    student_id: int
    kind: str = Field(..., regex="^(arrived|left)$")


# ── Special chegirmalar ───────────────────────────────────────────────────────

class SpecialDiscountRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    kind: str                                # free_month | monthly
    amount: Optional[Decimal] = None
    month: Optional[int] = None
    year: Optional[int] = None
    reason: Optional[str] = None
    is_active: bool
    created_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class SpecialDiscountCreate(BaseModel):
    student_id: int
    group_id: Optional[int] = None           # NULL = barcha guruhlar
    kind: str = Field(..., regex="^(free_month|monthly)$")
    amount: Optional[Decimal] = Field(None, gt=0)   # monthly uchun
    month: Optional[int] = Field(None, ge=1, le=12) # free_month uchun
    year: Optional[int] = Field(None, ge=2020)      # free_month uchun
    reason: Optional[str] = Field(None, max_length=300)


class SpecialDiscountUpdate(BaseModel):
    is_active: Optional[bool] = None
    reason: Optional[str] = Field(None, max_length=300)


# ── Holidays (dam olish kunlari) ──────────────────────────────────────────────

class HolidayRead(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    created_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class HolidayCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=300)
    start_date: date
    end_date: date


# ── Homework (uy vazifasi) ────────────────────────────────────────────────────

class HomeworkRead(BaseModel):
    id: int
    group_id: int
    group_name: Optional[str] = None
    lesson_id: Optional[int] = None
    lesson_number: Optional[int] = None
    lesson_title: Optional[str] = None
    text: str
    lesson_date: date
    created_by_name: Optional[str] = None
    created_at: datetime
    telegram_sent: bool = False
    telegram_error: Optional[str] = None

    class Config:
        orm_mode = True


class HomeworkCreate(BaseModel):
    text: str = Field(..., min_length=2)
    lesson_date: Optional[date] = None       # default: bugun
    lesson_id: Optional[int] = None          # metodikadagi dars (ixtiyoriy)
    lesson_number: Optional[int] = None
    lesson_title: Optional[str] = Field(None, max_length=500)


class NextLessonInfo(BaseModel):
    """Guruh uchun metodika bo'yicha navbatdagi (bugungi) dars."""
    lesson_id: Optional[int] = None
    lesson_number: Optional[int] = None
    lesson_title: Optional[str] = None
    homework: Optional[str] = None
    category: Optional[str] = None
    completed_lessons: int = 0
    total_lessons: int = 0


# ── Akademik: baholar / izohlar / sertifikatlar / tadbirlar ──────────────────

class StudentBrief(BaseModel):
    id: int
    full_name: str


class AcademicGroupOption(BaseModel):
    """Baholash mumkin bo'lgan guruh + talabalari (teacher — faqat o'z guruhlari)."""
    group_id: int
    group_name: str
    students: List[StudentBrief]


class GradeRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    subject: str
    score: int
    max_score: int
    exam_type: str
    exam_date: date
    comment: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime


class GradeCreate(BaseModel):
    student_id: int
    group_id: Optional[int] = None
    subject: str = Field(..., min_length=1, max_length=200)
    score: int = Field(..., ge=0)
    max_score: int = Field(100, gt=0)
    exam_type: str = Field("exam", regex="^(exam|test|quiz|project)$")
    exam_date: Optional[date] = None         # default: bugun
    comment: Optional[str] = None


class GradeUpdate(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    score: Optional[int] = Field(None, ge=0)
    max_score: Optional[int] = Field(None, gt=0)
    exam_type: Optional[str] = Field(None, regex="^(exam|test|quiz|project)$")
    exam_date: Optional[date] = None
    comment: Optional[str] = None


class TeacherFeedbackRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    teacher_name: Optional[str] = None
    comment: str
    created_at: datetime
    status: str = "new"                                  # new | resolved | no_answer
    status_updated_by_name: Optional[str] = None
    status_updated_at: Optional[datetime] = None


class TeacherFeedbackStatusUpdate(BaseModel):
    status: Literal["new", "resolved", "no_answer"]


class TeacherFeedbackCreate(BaseModel):
    student_id: int
    group_id: Optional[int] = None
    comment: str = Field(..., min_length=2)


class TeacherFeedbackUpdate(BaseModel):
    comment: str = Field(..., min_length=2)


class CertificateRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    title: str
    file_url: str
    issued_at: Optional[date] = None
    created_by_name: Optional[str] = None
    created_at: datetime


class CertificateCreate(BaseModel):
    student_id: int
    title: str = Field(..., min_length=2, max_length=300)
    file_url: str = Field(..., min_length=5, max_length=500)
    issued_at: Optional[date] = None


class CertificateUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    file_url: Optional[str] = Field(None, min_length=5, max_length=500)
    issued_at: Optional[date] = None


class EventRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    event_date: datetime
    location: Optional[str] = None
    is_active: bool = True
    created_by_name: Optional[str] = None
    created_at: datetime


class EventCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    description: Optional[str] = None
    event_date: datetime
    location: Optional[str] = Field(None, max_length=300)


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    description: Optional[str] = None
    event_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=300)
    is_active: Optional[bool] = None


# ── Coinlar ──────────────────────────────────────────────────────────────────

class CoinSummary(BaseModel):
    """Joriy oy uchun coin budjeti (teacher uchun limit, admin uchun cheksiz)."""
    month: int
    year: int
    budget: Optional[int] = None             # None — cheksiz (admin/metodist/hunter)
    spent: int = 0
    remaining: Optional[int] = None          # None — cheksiz


class CoinGive(BaseModel):
    student_id: int
    group_id: Optional[int] = None
    amount: int = Field(..., ge=1, le=1000)   # bitta amalda maks. 1000; real chek — oylik budjet
    reason: Optional[str] = Field(None, max_length=300)


class CoinTransactionRead(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    group_name: Optional[str] = None
    teacher_name: Optional[str] = None
    amount: int
    reason: Optional[str] = None
    created_at: datetime


class StudentCoinTotal(BaseModel):
    student_id: int
    student_name: str
    total: int


class CoinDeduct(BaseModel):
    """Admin talabadan coin yechadi (jarima/tuzatish) — manfiy yozuv sifatida saqlanadi."""
    student_id: int
    amount: int = Field(..., ge=1, le=100000)
    reason: Optional[str] = Field(None, max_length=300)
