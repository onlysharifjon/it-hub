"""Ota-ona API uchun Pydantic sxemalar. JSON — snake_case, mobil kontraktga mos."""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────────────────────────

class ParentLoginRequest(BaseModel):
    username: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Profil / bolalar ─────────────────────────────────────────────────────────

class ParentProfile(BaseModel):
    full_name: str
    display_name: Optional[str] = None
    phone: str
    avatar: Optional[str] = None             # base64 (mobil ilova yuklagan rasm)


class ParentProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=120)
    avatar_base64: Optional[str] = Field(None, max_length=2_800_000)  # ~2MB rasm chegarasi


class ChildRead(BaseModel):
    id: int
    full_name: str
    group_name: Optional[str] = None
    stage: Optional[str] = None
    teacher_name: Optional[str] = None
    schedule: Optional[str] = None          # inson o'qiy oladigan qisqa satr
    tariff: int = 0                          # oylik narx (so'm, butun son)
    start_date: Optional[date] = None
    discount_percent: int = 0
    avatar: Optional[str] = None


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
    notes: Optional[str] = None
    recorded_by_name: Optional[str] = None
    group_name: Optional[str] = None


class ChildPaymentSummary(BaseModel):
    month: int
    year: int
    total_owed: int
    total_paid: int
    advance_balance: int
    advance_applied: int
    debt: int
    payment_status: str                      # paid | partial | debtor | none
    groups: List[ChildGroupFee]
    recent_payments: List[ChildPaymentItem]


# ── Davomat ──────────────────────────────────────────────────────────────────

class AttendanceRecord(BaseModel):
    lesson_date: datetime
    is_present: bool
    group_name: Optional[str] = None


class ChildAttendance(BaseModel):
    percent: int
    records: List[AttendanceRecord]


# ── Jadval ───────────────────────────────────────────────────────────────────

class ScheduleSlotRead(BaseModel):
    day_of_week: int                         # 1 = Dushanba .. 7 = Yakshanba
    start_time: str
    end_time: str
    group_name: Optional[str] = None
    teacher_name: Optional[str] = None
    stage: Optional[str] = None
    room: Optional[str] = None


# ── Bildirishnomalar ─────────────────────────────────────────────────────────

class ParentNotificationRead(BaseModel):
    id: int
    type: str
    title: str
    body: Optional[str] = None
    created_at: datetime
    is_read: bool


# ── O'quv jarayoni (baholar / uy vazifasi / izohlar) ─────────────────────────

class GradeRead(BaseModel):
    id: int
    subject: str
    score: int
    max_score: int
    exam_type: str                           # exam | test | quiz | project
    date: date
    comment: Optional[str] = None
    group_name: Optional[str] = None


class HomeworkRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None        # vazifa matni
    assigned_date: date
    due_date: Optional[date] = None
    status: str                              # pending | submitted | graded
    grade: Optional[int] = None              # graded bo'lsa: ball
    teacher_comment: Optional[str] = None
    group_name: Optional[str] = None


class FeedbackRead(BaseModel):
    id: int
    teacher_name: str
    comment: str
    date: date
    group_name: Optional[str] = None


# ── O'qituvchi / tadbirlar / sertifikatlar ───────────────────────────────────

class TeacherContact(BaseModel):
    name: str
    phone: Optional[str] = None
    telegram: Optional[str] = None           # @username
    group_name: Optional[str] = None
    avatar: Optional[str] = None


class EventRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    date: datetime
    location: Optional[str] = None


class CertificateRead(BaseModel):
    id: int
    title: str
    file_url: str                            # PDF havolasi
    issued_at: Optional[date] = None


# ── To'lov (stub) ────────────────────────────────────────────────────────────

class PayRequest(BaseModel):
    amount: int = Field(..., gt=0)
    group_id: int
    provider: str = Field("payme", regex="^(payme|click|uzum)$")


class CheckoutResponse(BaseModel):
    checkout_url: str


# ── Coinlar ──────────────────────────────────────────────────────────────────

class CoinItem(BaseModel):
    amount: int
    reason: Optional[str] = None
    teacher_name: Optional[str] = None
    date: datetime


class ChildCoins(BaseModel):
    total: int
    recent: List[CoinItem]
