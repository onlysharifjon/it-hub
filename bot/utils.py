import hashlib
import os as _os
import secrets
import string

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from keyboards import (
    BTN_REQUEST_CHILD,
    admin_reply_keyboard,
    audit_reply_keyboard,
    parent_reply_keyboard,
    worker_reply_keyboard,
)
from models import AuditAccount, Employee, Fine, FineTemplate, ParentLink, Role, Setting


async def safe_edit_text(
    message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise


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


async def list_parents(session: AsyncSession) -> list[Employee]:
    result = await session.execute(
        select(Employee)
        .options(selectinload(Employee.role))
        .join(Role, Employee.role_id == Role.id)
        .where(Role.is_parent.is_(True))
    )
    return list(result.scalars().all())


async def list_staff(session: AsyncSession) -> list[Employee]:
    result = await session.execute(
        select(Employee)
        .options(selectinload(Employee.role))
        .outerjoin(Role, Employee.role_id == Role.id)
        .where(Employee.is_admin.is_(False))
        .where((Employee.role_id.is_(None)) | (Role.is_parent.is_(False)))
    )
    return list(result.scalars().all())


async def list_staff_without_audit(session: AsyncSession) -> list[Employee]:
    """/ishchilar ("Xodimlar") ro'yxati uchun — audit huquqi berilganlar bu yerda
    ko'rinmaydi (ular "Audit akkauntlari" bo'limida boshqariladi)."""
    active_audit_ids = select(AuditAccount.employee_id).where(AuditAccount.is_active.is_(True))
    result = await session.execute(
        select(Employee)
        .options(selectinload(Employee.role))
        .outerjoin(Role, Employee.role_id == Role.id)
        .where(Employee.is_admin.is_(False))
        .where((Employee.role_id.is_(None)) | (Role.is_parent.is_(False)))
        .where(Employee.id.not_in(active_audit_ids))
    )
    return list(result.scalars().all())


SEVERITY_LABELS = {
    "gray": "⚪ Kulrang eslatma",
    "yellow": "\U0001f7e1 Sariq ogohlantirish",
    "red": "\U0001f534 Qizil ogohlantirish",
}


def money_and_warning_summary(fines: list[Fine]) -> str:
    money_total = sum(fine.amount for fine in fines if not fine.severity)
    money_str = f"{money_total:,}".replace(",", " ")
    warning_counts: dict[str, int] = {}
    for fine in fines:
        if fine.severity:
            warning_counts[fine.severity] = warning_counts.get(fine.severity, 0) + 1
    lines = [f"\U0001f4b0 Shtraf (pul): {money_str} so'm"]
    if warning_counts:
        lines.append(
            "⚠️ Jarima (rang bo'yicha): "
            + " | ".join(f"{SEVERITY_LABELS.get(sev, sev)}: {count}" for sev, count in warning_counts.items())
        )
    return "\n".join(lines)


def fine_line(fine: Fine) -> str:
    timestamp = f"{fine.created_at:%d.%m.%Y %H:%M}"
    if fine.severity:
        label = SEVERITY_LABELS.get(fine.severity, fine.severity)
        band = f"{fine.code}-bandga ko'ra: " if fine.code else ""
        return f"• {timestamp} — {label}\n  {band}{fine.reason}"
    amount_str = f"{fine.amount:,}".replace(",", " ")
    return f"• {timestamp} — {amount_str} so'm ({fine.reason})"


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


async def ensure_audit_account(session: AsyncSession, employee: Employee) -> tuple[str, str] | None:
    """Employee uchun audit akkaunt bo'lmasa, avtomatik login/parol bilan yaratadi
    (masalan admin qilib tayinlanganda — keyin adminlikdan olinsa ham audit huquqi
    saqlanib qolishi uchun). Yangi yaratilgan bo'lsa (login, parol) qaytaradi,
    aks holda (allaqachon bor bo'lsa) None."""
    existing = await session.execute(select(AuditAccount).where(AuditAccount.employee_id == employee.id))
    if existing.scalar_one_or_none() is not None:
        return None
    login = f"audit{employee.id}"
    while True:
        taken = await session.execute(select(AuditAccount).where(AuditAccount.login == login))
        if taken.scalar_one_or_none() is None:
            break
        login = f"audit{employee.id}_{secrets.token_hex(2)}"
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for _ in range(10))
    password_hash, salt = hash_password(password)
    session.add(
        AuditAccount(employee_id=employee.id, login=login, password_hash=password_hash, salt=salt)
    )
    await session.commit()
    return login, password


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


async def visible_fine_templates(session: AsyncSession, employee: Employee) -> list[FineTemplate]:
    query = select(FineTemplate).where(FineTemplate.is_active.is_(True))
    if not employee.is_admin:
        query = query.where(or_(FineTemplate.owner == "audit", FineTemplate.shared_with_audit.is_(True)))
    result = await session.execute(query.order_by(FineTemplate.short_name))
    return list(result.scalars().all())


async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        session.add(Setting(key=key, value=value))
    else:
        setting.value = value
    await session.commit()


async def commands_for_employee(session: AsyncSession, employee: Employee) -> list[tuple[str, str]]:
    commands: list[tuple[str, str]] = [("start", "Botni qayta ishga tushirish")]
    if employee.is_admin:
        commands += [
            ("panel", "Boshqaruv paneli"),
            ("otaona", "Ota-onani biriktirish"),
            ("davomat", "Kelish/ketish belgilash"),
            ("tolov", "O'quvchi to'lov holati"),
            ("tolovhisoboti", "To'lov hisoboti"),
            ("otaonaid", "Standart ota-ona ID"),
            ("rasmsozlama", "Shtrafda rasm majburiymi"),
            ("ishchilar", "Xodimlar va rollar"),
            ("rollar", "Rollarni boshqarish"),
            ("auditlar", "Audit akkauntlari"),
            ("shablonlar", "Shtraf shablonlari"),
            ("hisobot", "Jarima/shtraf hisoboti"),
        ]
    else:
        account = await get_active_audit_account(session, employee.id)
        if account is not None:
            commands += [
                ("panel", "Audit paneli"),
                ("audit", "Audit rejimiga kirish"),
                ("hisobot", "Jarima/shtraf hisoboti"),
            ]
        if employee.role_id:
            commands.append(("shtraflarim", "Mening jarima/shtraflarim"))
        commands.append(("farzandbiriktir", "Farzand biriktirish so'rovi yuborish"))

    result = await session.execute(select(ParentLink).where(ParentLink.employee_id == employee.id))
    if result.scalar_one_or_none() is not None:
        commands += [
            ("jadval", "Farzandim dars jadvali"),
            ("farzandim", "Farzandim kelish/ketish tarixi"),
        ]
    return commands


async def apply_bot_commands(bot: Bot, session: AsyncSession, employee: Employee) -> None:
    commands = await commands_for_employee(session, employee)
    try:
        await bot.set_my_commands(
            [BotCommand(command=name, description=description) for name, description in commands],
            scope=BotCommandScopeChat(chat_id=employee.telegram_id),
        )
    except Exception:
        pass


async def reply_keyboard_for_employee(
    session: AsyncSession, employee: Employee
) -> ReplyKeyboardMarkup | None:
    result = await session.execute(select(ParentLink).where(ParentLink.employee_id == employee.id))
    is_parent = result.scalar_one_or_none() is not None

    if employee.is_admin:
        rows = list(admin_reply_keyboard().keyboard)
        if is_parent:
            rows.extend(parent_reply_keyboard().keyboard)
        return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)

    rows = []
    account = await get_active_audit_account(session, employee.id)
    if account is not None:
        rows.extend(audit_reply_keyboard().keyboard)
    if employee.role_id:
        rows.extend(worker_reply_keyboard().keyboard)
    if is_parent:
        rows.extend(parent_reply_keyboard().keyboard)
    rows.append([KeyboardButton(text=BTN_REQUEST_CHILD)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)
