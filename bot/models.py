from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_parent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    employees: Mapped[list["Employee"]] = relationship(back_populates="role")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role: Mapped["Role | None"] = relationship(back_populates="employees")
    fines_received: Mapped[list["Fine"]] = relationship(
        back_populates="employee", foreign_keys="Fine.employee_id"
    )
    audit_account: Mapped["AuditAccount | None"] = relationship(back_populates="employee")


class AuditAccount(Base):
    __tablename__ = "audit_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    salt: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    employee: Mapped["Employee"] = relationship(back_populates="audit_account")


class FineTemplate(Base):
    __tablename__ = "fine_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(255), unique=True)
    short_name: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(16))
    shared_with_audit: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Ichki tartib qoidalari kodeksidan: bob-band kodi va darajasi (gray/yellow/red).
    # Berilganda bu shablon pulsiz ogohlantirish hisoblanadi (Fine.amount = 0).
    code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Fine(Base):
    __tablename__ = "fines"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    issued_by_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    photo_file_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Tartib qoidalari kodeksidan berilgan bo'lsa: "gray"|"yellow"|"red". Oddiy pullik
    # shtraflarda None — amount maydoni ishlatiladi.
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)

    employee: Mapped["Employee"] = relationship(foreign_keys=[employee_id], back_populates="fines_received")
    issued_by: Mapped["Employee"] = relationship(foreign_keys=[issued_by_id])


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    crm_student_id: Mapped[int] = mapped_column(Integer, index=True)
    student_name: Mapped[str] = mapped_column(String(255))
    crm_group_id: Mapped[int] = mapped_column(Integer, index=True)
    group_name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(10))
    marked_by_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    marked_by: Mapped["Employee"] = relationship()


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[str] = mapped_column(String(255))


class ParentLinkRequest(Base):
    """Ota-ona '\U0001f517 Farzand biriktirish' orqali o'zi so'ragan, admin tasdiqlashini
    kutayotgan bog'lanish so'rovi — tasdiqlangach ParentLink'ga aylanadi."""

    __tablename__ = "parent_link_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    crm_student_id: Mapped[int] = mapped_column(Integer)
    student_name: Mapped[str] = mapped_column(String(255))
    crm_group_id: Mapped[int] = mapped_column(Integer, default=0)
    group_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    employee: Mapped["Employee"] = relationship()


class ParentLink(Base):
    """Ota-ona (Employee) va CRM o'quvchisi orasidagi bog'lanish — botning o'z bazasida
    saqlanadi, CRMga yozish shart emas (CRM roli yetarli bo'lmasa ham ishlaydi)."""

    __tablename__ = "parent_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    crm_student_id: Mapped[int] = mapped_column(Integer, index=True)
    student_name: Mapped[str] = mapped_column(String(255))
    crm_group_id: Mapped[int] = mapped_column(Integer)
    group_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    employee: Mapped["Employee"] = relationship()
