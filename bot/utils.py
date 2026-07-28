import secrets
from datetime import datetime

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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import crm_client
from keyboards import (
    BTN_REQUEST_CHILD,
    admin_reply_keyboard,
    limited_admin_reply_keyboard,
    parent_reply_keyboard,
)
from models import AdminInviteLink, Employee, ParentLink, Role, Setting


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


async def create_invite_link(session: AsyncSession, tier: str, created_by_id: int) -> str:
    """Bir martalik admin/superadmin taklif tokeni yaratadi va qaytaradi."""
    token = secrets.token_urlsafe(16)
    session.add(AdminInviteLink(token=token, tier=tier, created_by_id=created_by_id))
    await session.commit()
    return token


async def consume_invite_link(session: AsyncSession, token: str, employee: Employee) -> str | None:
    """Token to'g'ri va hali ishlatilmagan bo'lsa, employee'ni shu darajaga ko'taradi
    va havolani 'ishlatilgan' deb belgilaydi. Muvaffaqiyatli bo'lsa daraja nomini
    ("admin"|"superadmin") qaytaradi, aks holda (token yaroqsiz) None."""
    result = await session.execute(
        select(AdminInviteLink).where(AdminInviteLink.token == token, AdminInviteLink.used_at.is_(None))
    )
    link = result.scalar_one_or_none()
    if link is None:
        return None
    employee.is_admin = True
    employee.is_superadmin = link.tier == "superadmin"
    link.used_by_id = employee.id
    link.used_at = datetime.utcnow()
    await session.commit()
    return link.tier


def format_new_links_notice(names: list[str]) -> str:
    if len(names) == 1:
        return (
            f"\U0001f465 Farzandingiz {names[0]} sizga ulandi!\n"
            "Endi \"Farzandim\" tugmasi orqali uning davomati va dars jadvalini kuzatib borishingiz mumkin."
        )
    joined = ", ".join(names)
    return (
        f"\U0001f465 Farzandlaringiz sizga ulandi: {joined}.\n"
        "Endi \"Farzandim\" tugmasi orqali ularning davomati va dars jadvalini kuzatib borishingiz mumkin."
    )


async def sync_parent_links_from_crm(session: AsyncSession, employee: Employee) -> list[str]:
    """CRM administratori o'quvchining telegram_user_id maydoniga shu xodimning Telegram
    ID'sini kiritgan bo'lsa (CRM'ning o'zida, botdan tashqarida), topilgan o'quvchi(lar)
    uchun avtomatik ParentLink yaratadi (agar hali bo'lmasa, botning o'z bazasida).
    Yangi bog'langan o'quvchilar ismlarini qaytaradi."""
    try:
        students = await crm_client.get_students_by_telegram_id(employee.telegram_id)
    except crm_client.CRMError:
        return []
    if not students:
        return []
    newly_linked: list[str] = []
    for student in students:
        existing = await session.execute(
            select(ParentLink).where(
                ParentLink.employee_id == employee.id, ParentLink.crm_student_id == student["id"]
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        session.add(
            ParentLink(
                employee_id=employee.id,
                crm_student_id=student["id"],
                student_name=student["full_name"],
                crm_group_id=student.get("group_id", 0),
                group_name=student.get("group_name", ""),
            )
        )
        newly_linked.append(student["full_name"])
    if newly_linked:
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return []
    return newly_linked


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
    commands: list[tuple[str, str]] = [
        ("start", "Botni qayta ishga tushirish"),
        ("info", "Yordam / imkoniyatlar ro'yxati"),
    ]
    if employee.is_admin:
        commands += [
            ("panel", "Boshqaruv paneli"),
            ("otaona", "Ota-onani biriktirish"),
            ("davomat", "Kelish/ketish belgilash"),
            ("tolov", "O'quvchi to'lov holati"),
            ("tolovhisoboti", "To'lov hisoboti"),
        ]
        if employee.is_superadmin:
            commands += [
                ("otaonaid", "Standart ota-ona ID"),
                ("ishchilar", "Xodimlar va rollar"),
                ("rollar", "Rollarni boshqarish"),
            ]
    else:
        commands.append(("farzandbiriktir", "Farzand biriktirish so'rovi yuborish"))
        commands.append(("idyubor", "Telegram ID'ingizni CRM uchun adminga yuborish"))

    result = await session.execute(select(ParentLink).where(ParentLink.employee_id == employee.id))
    if result.scalar_one_or_none() is not None:
        commands += [
            ("jadval", "Farzandim dars jadvali"),
            ("farzandim", "Farzandim kelish/ketish tarixi"),
        ]
    return commands


async def build_info_text(session: AsyncSession, employee: Employee) -> str:
    """Xodimning roliga mos, u nima qila olishi haqidagi to'liq ma'lumot matni —
    /info komandasi va tegishli rollar uchun /start'da avtomatik yuboriladi."""
    commands = await commands_for_employee(session, employee)

    roles_present: list[str] = []
    if employee.is_admin:
        roles_present.append("Superadmin (CEO)" if employee.is_superadmin else "Admin")
    if employee.role_id:
        roles_present.append(employee.role.name if employee.role else "Xodim")
    result = await session.execute(select(ParentLink).where(ParentLink.employee_id == employee.id))
    if result.scalar_one_or_none() is not None:
        roles_present.append("Ota-ona")
    role_line = ", ".join(roles_present) if roles_present else "Foydalanuvchi"

    lines = [f"\U00002139\U0000fe0f Siz: {role_line}", "", "Sizda quyidagi imkoniyatlar bor:", ""]
    for name, description in commands:
        if name in ("start", "info"):
            continue
        lines.append(f"/{name} — {description}")
    lines.append("")
    lines.append("Bularning aksariyatini pastdagi doimiy tugmalar orqali ham bajarish mumkin.")
    return "\n".join(lines)


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
        base = admin_reply_keyboard() if employee.is_superadmin else limited_admin_reply_keyboard()
        rows = list(base.keyboard)
        if is_parent:
            rows.extend(parent_reply_keyboard().keyboard)
        return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)

    rows = []
    if is_parent:
        rows.extend(parent_reply_keyboard().keyboard)
    rows.append([KeyboardButton(text=BTN_REQUEST_CHILD)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)
