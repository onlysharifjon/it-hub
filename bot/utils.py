import hashlib
import os as _os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import AuditAccount, Employee, Fine


async def get_employee(session: AsyncSession, telegram_id: int) -> Employee | None:
    result = await session.execute(
        select(Employee).options(selectinload(Employee.role)).where(Employee.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def list_workers(session: AsyncSession) -> list[Employee]:
    result = await session.execute(
        select(Employee)
        .options(selectinload(Employee.role))
        .where(Employee.is_admin.is_(False))
        .order_by(Employee.full_name)
    )
    return list(result.scalars().all())


async def list_admins(session: AsyncSession) -> list[Employee]:
    result = await session.execute(select(Employee).where(Employee.is_admin.is_(True)))
    return list(result.scalars().all())


async def list_employees_with_fines(session: AsyncSession) -> list[Employee]:
    result = await session.execute(
        select(Employee)
        .join(Fine, Fine.employee_id == Employee.id)
        .options(selectinload(Employee.role))
        .distinct()
        .order_by(Employee.full_name)
    )
    return list(result.scalars().all())


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or _os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return digest, salt


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    digest, _ = hash_password(password, salt)
    return digest == password_hash


async def get_active_audit_account(session: AsyncSession, employee_id: int) -> AuditAccount | None:
    result = await session.execute(
        select(AuditAccount).where(
            AuditAccount.employee_id == employee_id, AuditAccount.is_active.is_(True)
        )
    )
    return result.scalar_one_or_none()


async def is_privileged(session: AsyncSession, employee: Employee | None) -> bool:
    if employee is None:
        return False
    if employee.is_admin:
        return True
    return await get_active_audit_account(session, employee.id) is not None
