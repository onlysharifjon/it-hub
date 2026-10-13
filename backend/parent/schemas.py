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
    amount: int
    month: int
    year: int
    paid_at: datetime
    recorded_by_name: str = ""
    notes: Optional[str] = None             # nullable
    group_name: Optional[str] = None        # nullable


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
