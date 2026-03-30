from datetime import datetime
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
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.teacher


class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


# ── Lessons ───────────────────────────────────────────────────────────────────

class LessonRead(BaseModel):
    id: int
    month: int
    week: int
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
    month: int = Field(..., ge=1)
    week: int = Field(..., ge=1)
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
