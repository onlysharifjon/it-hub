from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from config import ADMIN_IDS
from database import async_session
from keyboards import roles_keyboard
from models import Employee, Role
from utils import apply_bot_commands, get_active_audit_account, get_employee, list_admins, reply_keyboard_for_employee

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
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
            text = (
                f"\U0001f44b Xush kelibsiz, {employee.full_name}!\n\n"
                "Siz — admin. Pastdagi tugmalar orqali boshqaring."
            )
        elif employee.role_id or (await get_active_audit_account(session, employee.id)):
            text = f"\U0001f44b Xush kelibsiz, {employee.full_name}!\n\nPastdagi tugmalar orqali davom eting."
        else:
            text = (
                f"\U0001f44b Xush kelibsiz, {employee.full_name}!\n\n"
                "Hozircha sizga rol berilmagan — admin tez orada rol beradi."
            )

        keyboard = await reply_keyboard_for_employee(session, employee)
        await message.answer(text, reply_markup=keyboard)
        await apply_bot_commands(message.bot, session, employee)

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
