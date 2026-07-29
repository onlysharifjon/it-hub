from datetime import timedelta

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

import crm_client
from config import ADMIN_IDS
from database import async_session
from keyboards import BTN_MY_WARNINGS, roles_keyboard
from models import Employee, ParentLink, Role
from utils import (
    apply_bot_commands,
    build_info_text,
    consume_invite_link,
    format_new_links_notice,
    get_employee,
    list_admins,
    reply_keyboard_for_employee,
    sync_parent_links_from_crm,
)

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    tg_user = message.from_user
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else None

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

        newly_linked = await sync_parent_links_from_crm(session, employee)

        invited_tier = None
        if payload and payload.startswith("invite_"):
            invited_tier = await consume_invite_link(session, payload[len("invite_"):], employee)

        if invited_tier:
            tier_label = "Superadmin (CEO)" if invited_tier == "superadmin" else "Admin"
            text = (
                f"\U0001f451 Xush kelibsiz, {employee.full_name}!\n\n"
                f"Havola orqali sizga {tier_label} huquqi berildi. Pastdagi tugmalar orqali boshqaring."
            )
        elif employee.is_admin:
            text = (
                f"\U0001f44b Xush kelibsiz, {employee.full_name}!\n\n"
                "Siz — admin. Pastdagi tugmalar orqali boshqaring."
            )
        elif employee.role_id:
            text = f"\U0001f44b Xush kelibsiz, {employee.full_name}!\n\nPastdagi tugmalar orqali davom eting."
        else:
            text = (
                f"\U0001f44b Xush kelibsiz, {employee.full_name}!\n\n"
                "Hozircha sizga rol berilmagan — admin tez orada rol beradi."
            )

        keyboard = await reply_keyboard_for_employee(session, employee)
        await message.answer(text, reply_markup=keyboard)
        if newly_linked:
            await message.answer(format_new_links_notice(newly_linked))

        parent_result = await session.execute(
            select(ParentLink).where(ParentLink.employee_id == employee.id)
        )
        is_parent = parent_result.scalar_one_or_none() is not None
        if employee.is_admin or is_parent:
            await message.answer(await build_info_text(session, employee))

        await apply_bot_commands(message.bot, session, employee)

        if created and not employee.is_admin:
            await _notify_admins(message, session, employee)


@router.message(F.text == "/info")
async def cmd_info(message: Message) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if employee is None:
            await message.answer("Avval botga /start bosing.")
            return
        await message.answer(await build_info_text(session, employee))


@router.message(F.text == "/idyubor")
async def cmd_send_id(message: Message) -> None:
    """Xodim shu komandani yuborsa, ismi va Telegram ID'si adminlarga xabar
    qilinadi — admin shu ID'ni CRM'da xodimning profiliga yozadi (masalan,
    audit ogohlantirishlari shu ID orqali Telegram'ga yetkaziladi)."""
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if employee is None:
            await message.answer("Avval botga /start bosing.")
            return
        username_part = f"@{employee.username}" if employee.username else "username yo'q"
        text = (
            "\U0001f194 CRM uchun Telegram ID so'rovi:\n"
            f"{employee.full_name} ({username_part})\n"
            f"ID: <code>{employee.telegram_id}</code>"
        )
        admins = await list_admins(session)
        sent = False
        for admin in admins:
            try:
                await message.bot.send_message(admin.telegram_id, text)
                sent = True
            except Exception:
                continue
    if sent:
        await message.answer("✅ ID'ingiz adminlarga yuborildi.")
    else:
        await message.answer("Adminlarga yetkazib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")


_SEVERITY_ICON = {"gray": "⚪️", "yellow": "\U0001f7e1", "red": "\U0001f534"}


@router.message(F.text.in_({"/ogohlantirishlarim", BTN_MY_WARNINGS}))
async def cmd_my_warnings(message: Message) -> None:
    """CRM'da audit tomonidan berilgan, shu xodimga tegishli ogohlantirishlar
    ro'yxati — bot faqat CRM bazasidan o'qib ko'rsatadi (o'zi hech narsa
    yozmaydi). Bekor qilinganlari ham ko'rinadi, "bekor qilingan" belgisi bilan."""
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
    if employee is None:
        await message.answer("Avval botga /start bosing.")
        return
    try:
        data = await crm_client.get_staff_warnings(employee.telegram_id)
    except crm_client.CRMError:
        await message.answer("Hozircha ma'lumotni olib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")
        return
    if not data["linked"]:
        await message.answer(
            "Sizning Telegram ID'ingiz CRM'ga hali bog'lanmagan.\n"
            "/idyubor komandasi orqali ID'ingizni adminga yuboring."
        )
        return
    warnings = data["warnings"]
    if not warnings:
        await message.answer("Sizga hozircha ogohlantirish berilmagan. \U0001f44d")
        return
    lines = ["\U0001f4cb Sizning ogohlantirishlaringiz:", ""]
    for w in warnings:
        icon = _SEVERITY_ICON.get(w["severity"], "⚠️")
        local_time = (w["created_at"] + timedelta(hours=5)).strftime("%d.%m.%Y %H:%M")
        prefix = "❌ [BEKOR QILINGAN] " if w["cancelled_at"] else ""
        code_part = f"{w['code']}-bandga ko'ra: " if w["code"] else ""
        lines.append(f"{icon} {prefix}{local_time}")
        lines.append(f"  {code_part}{w['reason']}")
        if w["issued_by_name"]:
            lines.append(f"  Berdi: {w['issued_by_name']}")
        lines.append("")
    await message.answer("\n".join(lines))


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
