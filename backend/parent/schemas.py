"""Ota-ona API uchun Pydantic sxemalar — Flutter ilovasi bilan shartnoma.

Qoidalar (docs/parent-api/README.md): snake_case, pul — butun so'm (int),
sana — YYYY-MM-DD, vaqt — ISO-8601 +05:00, ro'yxatlar — xom JSON array.
"Nullable" deb belgilanmagan maydonlar hech qachon null bo'lmaydi.
"""
from __future__ import annotations

from datetime import datetime, date
import re
from typing import List, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, StrictBool, conint, root_validator, validator


class _Strict(BaseModel):
    class Config:
        extra = "forbid"     # himoyalangan maydonlarni (phone, role, child_ids ...) yuborib bo'lmaydi


# ── Auth ─────────────────────────────────────────────────────────────────────

class ParentLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=200)


# ── App configuration ──────────────────────────────────────────────────────

class ParentAppCapabilities(BaseModel):
    payments_enabled: bool = False
    payment_providers: List[str] = []
    account_deletion_enabled: bool = True
    privacy_policy_url: str
    push_enabled: bool = False
    absence_explanations_enabled: bool = False
    weekly_summary_enabled: bool = False
    teacher_questions_enabled: bool = False
    receipts_enabled: bool = False


class ParentReleaseConfigPublic(BaseModel):
    maintenance_enabled: bool
    maintenance_title: str
    maintenance_message: str
    min_supported_build: int
    latest_build: int
    app_store_url: str


class ParentReleaseConfigAdmin(ParentReleaseConfigPublic):
    updated_at: Optional[datetime] = None
    updated_by_id: Optional[int] = None


class ParentReleaseConfigUpdate(_Strict):
    maintenance_enabled: StrictBool
    maintenance_title: str = Field(..., min_length=1, max_length=120)
    maintenance_message: str = Field(..., min_length=1, max_length=600)
    min_supported_build: conint(strict=True, ge=1, le=999999999)
    latest_build: conint(strict=True, ge=1, le=999999999)
    app_store_url: str = Field(..., min_length=1, max_length=500)

    @validator("maintenance_title", "maintenance_message")
    def nonblank_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Matn bo'sh bo'lishi mumkin emas")
        return value

    @validator("app_store_url")
    def apple_store_link(cls, value):
        value = value.strip()
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.netloc != "apps.apple.com"
                or parsed.query or parsed.fragment
                or not re.fullmatch(r"/[a-z]{2}/app(?:/[A-Za-z0-9-]+)?/id6820518218", parsed.path)):
            raise ValueError("Faqat Minar Parents App Store havolasi qabul qilinadi")
        return value

    @root_validator(skip_on_failure=True)
    def build_order(cls, values):
        if values["latest_build"] < values["min_supported_build"]:
            raise ValueError("latest_build min_supported_build dan kichik bo'lmasin")
        return values


# ── Profil / bolalar ─────────────────────────────────────────────────────────

class ParentProfile(BaseModel):
    display_name: str
    full_name: str
    phone: str


class ParentProfileUpdate(_Strict):
    display_name: Optional[str] = None
    avatar_base64: Optional[str] = Field(None, max_length=3_000_000)

    @validator("display_name")
    def _name(cls, v):
        if v is None:
            raise ValueError("display_name null bo'lishi mumkin emas")
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("Ism 1–100 belgi bo'lishi kerak")
        return v


class ChildRead(BaseModel):
    id: int
    full_name: str
    group_name: str = ""
    stage: str = ""
    teacher_name: str = ""
    schedule: str = ""
    tariff: int = 0
    start_date: Optional[date] = None       # nullable
    discount_percent: int = 0
    avatar: Optional[str] = None            # nullable, HTTPS


# ── To'lov ───────────────────────────────────────────────────────────────────

class ChildGroupFee(BaseModel):
    group_id: int
    group_name: str
    owed: int
    paid: int
    remaining: int


class ChildPaymentItem(BaseModel):
    payment_id: Optional[int] = None
    amount: int
    month: int
    year: int
    paid_at: datetime
    recorded_by_name: str = ""
    notes: Optional[str] = None             # nullable
    group_name: Optional[str] = None        # nullable
    receipt_url: Optional[str] = None


class ChildPaymentSummary(BaseModel):
    month: int
    year: int
    total_owed: int
    total_paid: int
    advance_balance: int
    advance_applied: int
    debt: int
    payment_status: str                     # paid | partial | debtor
    groups: List[ChildGroupFee]
    recent_payments: List[ChildPaymentItem]


class PayRequest(_Strict):
    amount: int = Field(..., gt=0)
    group_id: int
    provider: str = Field(..., regex="^(payme|click|uzum)$")

    @validator("amount", pre=True)
    def _int_amount(cls, v):
        # 250000.5 yoki "250 000" emas — faqat butun son
        if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
            raise ValueError("Musbat butun son kiriting.")
        return v


class CheckoutResponse(BaseModel):
    checkout_url: str


# ── Davomat ──────────────────────────────────────────────────────────────────

class AttendanceRecord(BaseModel):
    lesson_date: date
    is_present: bool
    group_name: Optional[str] = None        # nullable


class ChildAttendance(BaseModel):
    percent: int
    records: List[AttendanceRecord]


# ── Jadval ───────────────────────────────────────────────────────────────────

class ScheduleSlotRead(BaseModel):
    day_of_week: int                        # 1 = Dushanba .. 7 = Yakshanba
    start_time: str                         # HH:mm
    end_time: str                           # HH:mm
    group_name: str = ""
    teacher_name: str = ""
    stage: str = ""
    room: Optional[str] = None              # nullable


# ── Bildirishnomalar ─────────────────────────────────────────────────────────

class ParentNotificationRead(BaseModel):
    id: int
    type: str                               # payment | attendance | announcement
    title: str
    body: str = ""
    created_at: datetime
    is_read: bool


class PushDeviceCreate(_Strict):
    token: str = Field(..., regex=r"^[a-fA-F0-9]{64}$")
    platform: str = Field(..., regex="^ios$")
    environment: str = Field(..., regex="^(sandbox|production)$")


class NotificationPreferences(BaseModel):
    attendance: bool = True
    schedule: bool = True
    payments: bool = True
    homework: bool = True
    announcements: bool = True
    weekly_summary: bool = True
    teacher_messages: bool = True


class NotificationPreferencesUpdate(_Strict):
    attendance: Optional[StrictBool] = None
    schedule: Optional[StrictBool] = None
    payments: Optional[StrictBool] = None
    homework: Optional[StrictBool] = None
    announcements: Optional[StrictBool] = None
    weekly_summary: Optional[StrictBool] = None
    teacher_messages: Optional[StrictBool] = None


class AbsenceExplanationCreate(_Strict):
    lesson_date: date
    group_name: Optional[str] = Field(None, max_length=200)
    reason: str = Field(..., regex="^(sick|travel|family|other)$")
    note: str = Field("", max_length=1000)


class AbsenceExplanationRead(BaseModel):
    id: int
    child_id: int
    lesson_date: date
    group_name: str
    reason: str
    note: str
    status: str
    staff_note: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class StaffAbsenceReview(_Strict):
    status: str = Field(..., regex="^(approved|rejected)$")
    staff_note: Optional[str] = Field(None, max_length=500)


class WeeklySummaryRead(BaseModel):
    week_start: date
    week_end: date
    attended_lessons: int
    scheduled_lessons: int
    homework_completed: int
    homework_total: int
    average_grade: Optional[int] = None
    highlights: List[str]
    needs_attention: List[str]
    teacher_recommendation: Optional[str] = None


class TeacherQuestionCreate(_Strict):
    subject: str = Field(..., min_length=2, max_length=120)
    body: str = Field(..., min_length=5, max_length=2000)

    @validator("subject", "body")
    def nonblank_question(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Matn bo'sh bo'lishi mumkin emas")
        return value


class StaffTeacherReply(_Strict):
    body: str = Field(..., min_length=2, max_length=2000)

    @validator("body")
    def nonblank_reply(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Javob bo'sh bo'lishi mumkin emas")
        return value


class StaffWeeklyRecommendation(_Strict):
    text: str = Field(..., min_length=4, max_length=500)

    @validator("text")
    def nonblank_recommendation(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Tavsiya bo'sh bo'lishi mumkin emas")
        return value


class TeacherReplyRead(BaseModel):
    id: int
    body: str
    author_name: str
    created_at: datetime


class TeacherQuestionRead(BaseModel):
    id: int
    child_id: int
    subject: str
    body: str
    status: str
    created_at: datetime
    replies: List[TeacherReplyRead]


# ── O'quv jarayoni ───────────────────────────────────────────────────────────

class GradeRead(BaseModel):
    subject: str
    score: int
    max_score: int
    date: date


class HomeworkRead(BaseModel):
    id: int
    title: str
    due_date: datetime                      # aniq muddat, +05:00
    status: str                             # pending | submitted | graded


class FeedbackRead(BaseModel):
    teacher_name: str
    comment: str
    date: date


class TeacherContact(BaseModel):
    """Mobil ilova Map<String,String> sifatida o'qiydi — faqat string qiymatlar."""
    name: str
    phone: str = ""
    telegram: str = ""


class CertificateRead(BaseModel):
    id: int
    title: str
    issue_date: date
    url: str                                # imzolangan, muddatli HTTPS havola


# ── Qo'shimcha (joriy ilova chaqirmaydi, eski versiyalar uchun saqlangan) ────

class EventRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    date: datetime
    location: Optional[str] = None


class CoinItem(BaseModel):
    amount: int
    reason: Optional[str] = None
    teacher_name: Optional[str] = None
    date: datetime


class ChildCoins(BaseModel):
    total: int
    recent: List[CoinItem]
