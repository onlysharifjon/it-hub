from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator

MAX_MONEY = Decimal("999999999999.99")
METHOD_RE = "^(cash|card|bank_transfer|online)$"
CURRENCY_RE = "^(UZS|USD|EUR|RUB)$"


def _strip(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class IncomeCreate(BaseModel):
    student_id: int
    group_id: int
    amount: Decimal = Field(..., gt=0, le=MAX_MONEY)
    currency: Optional[str] = Field(None, regex=CURRENCY_RE)
    fx_rate: Optional[Decimal] = Field(None, gt=0, le=Decimal("10000000"))
    op_date: Optional[date] = None
    method: str = Field(..., regex=METHOD_RE)
    account_id: int
    period_month: int = Field(..., ge=1, le=12)
    period_year: int = Field(..., ge=2020, le=2100)
    external_ref: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None, max_length=2000)
    document_path: Optional[str] = Field(None, max_length=500)
    responsible_id: Optional[int] = None
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=80)
    confirm: bool = False

    _s = validator("external_ref", "notes", "document_path", allow_reuse=True, pre=True)(_strip)


class ExpenseCreate(BaseModel):
    category_id: int
    amount: Decimal = Field(..., gt=0, le=MAX_MONEY)
    currency: Optional[str] = Field(None, regex=CURRENCY_RE)
    fx_rate: Optional[Decimal] = Field(None, gt=0, le=Decimal("10000000"))
    op_date: Optional[date] = None
    method: str = Field("cash", regex=METHOD_RE)
    account_id: Optional[int] = None   # ixtiyoriy — tanlanmasa hisob qoldig'iga ta'sir qilmaydi
    counterparty: Optional[str] = Field(None, max_length=200)
    responsible_id: Optional[int] = None
    staff_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=2000)
    document_path: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=80)
    confirm: bool = False

    _s = validator("counterparty", "notes", "document_path", allow_reuse=True, pre=True)(_strip)


class ReasonIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class RefundCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, le=MAX_MONEY)
    reason: str = Field(..., min_length=3, max_length=1000)
    account_id: Optional[int] = None
    method: Optional[str] = Field(None, regex=METHOD_RE)
    op_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)
    document_path: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=80)


class AdjustmentCreate(BaseModel):
    amount: Decimal = Field(..., ge=-MAX_MONEY, le=MAX_MONEY)   # + ko'paytiradi, − kamaytiradi
    reason: str = Field(..., min_length=3, max_length=1000)
    account_id: Optional[int] = None
    op_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=80)


class TransferCreate(BaseModel):
    account_id: int
    to_account_id: int
    amount: Decimal = Field(..., gt=0, le=MAX_MONEY)
    op_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=80)


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    kind: str = Field("cash", regex="^(cash|bank|card|online)$")
    currency: str = Field("UZS", regex=CURRENCY_RE)
    opening_balance: Decimal = Field(Decimal("0"), ge=-MAX_MONEY, le=MAX_MONEY)
    note: Optional[str] = Field(None, max_length=1000)


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    is_active: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=1000)
    opening_balance: Optional[Decimal] = Field(None, ge=-MAX_MONEY, le=MAX_MONEY)
    reason: Optional[str] = Field(None, max_length=1000)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    is_active: Optional[bool] = None


class SettingsUpdate(BaseModel):
    due_day: Optional[int] = Field(None, ge=1, le=28)
    upcoming_days: Optional[int] = Field(None, ge=1, le=60)


class PermissionsUpdate(BaseModel):
    permissions: Optional[List[str]] = None   # None — rolning standart to'plami
