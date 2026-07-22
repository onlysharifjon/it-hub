from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select

from config import ADMIN_IDS
from database import async_session
from keyboards import roles_keyboard
from models import Employee, Role
from utils import get_active_audit_account, get_employee, list_admins

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_user = message.from_user
    async with async_session() as session:
        employee = await get_employee(session, tg_user.id)
        created = False
        if employee is None:
            employee = Employee(
                telegram_id=tg_user.id,
                full_name=tg_user.full_name,
                username=tg_user.username,
                is_admin=tg_user.id in ADMIN_IDS,
            )
            session.add(employee)
            await session.commit()
            await session.refresh(employee)
            created = True

        if employee.is_admin:
            await message.answer("Xush kelibsiz, admin!\n\n/panel — boshqaruv paneli")
        else:
            has_audit = await get_active_audit_account(session, employee.id) is not None
            lines = [f"Xush kelibsiz, {employee.full_name}!"] if employee.role_id else [
                "Xush kelibsiz! Hozircha sizga rol berilmagan, admin tez orada rol beradi."
            ]
            if has_audit:
                lines.append("\n/panel — audit paneli")
            elif employee.role_id:
                lines.append("\n/shtraflarim — mening shtraflarim")
            await message.answer("\n".join(lines))

        if created and not employee.is_admin:
            await _notify_admins(message, session, employee)


async def _notify_admins(message: Message, session, employee: Employee) -> None:
    admins = await list_admins(session)
    username_part = f"@{employee.username}" if employee.username else "username yo'q"
    text = (
        "\U0001f195 Yangi foydalanuvchi botga start berdi:\n"
        f"{employee.full_name} ({username_part})\n"
        f"ID: <code>{employee.telegram_id}</code>\n\n"
        "Rol tanlang:"
    )
    result = await session.execute(select(Role).where(Role.is_active.is_(True)).order_by(Role.name))
    roles = result.scalars().all()
    keyboard = roles_keyboard(roles, f"set_role:{employee.id}")
    for admin in admins:
        try:
            await message.bot.send_message(admin.telegram_id, text, reply_markup=keyboard)
        except Exception:
            continue
