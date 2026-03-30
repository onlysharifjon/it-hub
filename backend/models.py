import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    admin = "admin"        # superadmin — to'liq nazorat + foydalanuvchi boshqaruvi
    metodist = "metodist"  # metodist   — dars CRUD + audit log
    teacher = "teacher"    # o'qituvchi  — faqat ko'rish


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.teacher.value)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    updated_lessons = relationship(
        "Lesson", back_populates="updated_by_user", foreign_keys="[Lesson.updated_by_id]"
    )
    audit_logs = relationship("AuditLog", back_populates="changed_by_user")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    lesson_number = Column(Integer, nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)
    section = Column(Text, nullable=True)
    guide = Column(Text, nullable=True)
    homework = Column(Text, nullable=True)
    extra_notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    updated_by_user = relationship(
        "User", back_populates="updated_lessons", foreign_keys=[updated_by_id]
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)    # lesson / user
    entity_id = Column(Integer, nullable=True)
    action = Column(String(50), nullable=False)         # create / update / delete / reorder
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    old_value = Column(Text, nullable=True)             # JSON string
    new_value = Column(Text, nullable=True)             # JSON string

    changed_by_user = relationship("User", back_populates="audit_logs")
