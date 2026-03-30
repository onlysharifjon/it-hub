import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Numeric, Table
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    admin = "admin"        # superadmin — to'liq nazorat + daromad statistika
    metodist = "metodist"  # metodist   — dars CRUD + talabalar/guruhlar
    teacher = "teacher"    # o'qituvchi  — faqat metodika ko'rish


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default=UserRole.teacher.value)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    updated_lessons = relationship(
        "Lesson", back_populates="updated_by_user", foreign_keys="[Lesson.updated_by_id]"
    )
    audit_logs = relationship("AuditLog", back_populates="changed_by_user")
    teaching_groups = relationship("Group", back_populates="teacher")


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
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    action = Column(String(50), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    changed_by_user = relationship("User", back_populates="audit_logs")


# ── LMS Modellari ─────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    phone1 = Column(String(20), nullable=False)
    phone2 = Column(String(20), nullable=True)
    telegram_id = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    group_memberships = relationship("GroupStudent", back_populates="student")
    payments = relationship("Payment", back_populates="student")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    course_price = Column(Numeric(12, 2), nullable=False, default=0)
    schedule = Column(String(200), nullable=True)   # e.g. "Du,Cho,Ju 14:00"
    start_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    teacher = relationship("User", back_populates="teaching_groups")
    members = relationship("GroupStudent", back_populates="group")
    payments = relationship("Payment", back_populates="group")


class GroupStudent(Base):
    __tablename__ = "group_students"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    group = relationship("Group", back_populates="members")
    student = relationship("Student", back_populates="group_memberships")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    month = Column(Integer, nullable=False)   # 1-12
    year = Column(Integer, nullable=False)
    paid_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    student = relationship("Student", back_populates="payments")
    group = relationship("Group", back_populates="payments")
