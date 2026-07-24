import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from sqlalchemy import select

from config import (
    ADMIN_IDS,
    AUDIT_SEED_ID,
    AUDIT_SEED_LOGIN,
    AUDIT_SEED_PASSWORD,
    BOT_TOKEN,
    DEFAULT_PARENT_CHAT_ID,
)
from database import async_session, init_db
from handlers import admin, audit, crm, panel, profile, start
from handlers.crm import payment_reminder_loop
from models import AuditAccount, Employee, FineTemplate, Role
from utils import apply_bot_commands, get_setting, hash_password, set_setting

DEFAULT_ROLES = [
    ("Main teacher", False),
    ("Support teacher", False),
    ("Reception", False),
    ("Oddiy foydalanuvchi (Ota-ona)", True),
]

DEFAULT_FINE_TEMPLATES = [
    ("Kechikish", "Kechikish"),
    ("Ishga kelmaslik", "Kelmaslik"),
    ("Intizom buzilishi", "Intizom"),
    ("Formadan tashqari kiyinish", "Kiyim"),
    ("Mijoz bilan noto'g'ri muomala", "Muomala"),
]

DEFAULT_AUDIT_FINE_TEMPLATES = [
    ("Ishga kech kelish", "Kech kelish"),
    ("Ish joyini ruxsatsiz tark etish", "Joy tashlash"),
    ("O'quvchi/mijoz bilan qo'pol muomala qilish", "Qo'pol muomala"),
    ("Ishxona ichki tartibini buzish", "Tartib buzish"),
    ("Ish vaqtida telefondan ortiqcha foydalanish", "Telefon"),
    ("Hisobot yoki vazifani vaqtida topshirmaslik", "Kech hisobot"),
    ("Ishxona mulkiga beparvo munosabat", "Mulkka beparvo"),
    ("Xavfsizlik qoidalarini buzish", "Xavfsizlik"),
]


async def seed_admins() -> None:
    if not ADMIN_IDS:
        return
    async with async_session() as session:
        for tg_id in ADMIN_IDS:
            result = await session.execute(select(Employee).where(Employee.telegram_id == tg_id))
            employee = result.scalar_one_or_none()
            if employee is None:
                session.add(Employee(telegram_id=tg_id, full_name=f"Admin {tg_id}", is_admin=True))
            elif not employee.is_admin:
                employee.is_admin = True
        await session.commit()


async def seed_audit_account() -> None:
    if not (AUDIT_SEED_ID and AUDIT_SEED_LOGIN and AUDIT_SEED_PASSWORD):
        return
    tg_id = int(AUDIT_SEED_ID)
    async with async_session() as session:
        result = await session.execute(select(Employee).where(Employee.telegram_id == tg_id))
        employee = result.scalar_one_or_none()
        if employee is None:
            employee = Employee(telegram_id=tg_id, full_name=f"Audit {tg_id}")
            session.add(employee)
            await session.commit()
            await session.refresh(employee)

        result = await session.execute(select(AuditAccount).where(AuditAccount.employee_id == employee.id))
        account = result.scalar_one_or_none()
        if account is not None:
            return

        password_hash, salt = hash_password(AUDIT_SEED_PASSWORD)
        session.add(
            AuditAccount(
                employee_id=employee.id,
                login=AUDIT_SEED_LOGIN,
                password_hash=password_hash,
                salt=salt,
            )
        )
        await session.commit()


async def seed_roles() -> None:
    async with async_session() as session:
        result = await session.execute(select(Role))
        existing = {role.name: role for role in result.scalars().all()}
        for name, is_parent in DEFAULT_ROLES:
            role = existing.get(name)
            if role is None:
                session.add(Role(name=name, is_parent=is_parent))
            elif role.is_parent != is_parent:
                role.is_parent = is_parent
        await session.commit()


async def seed_fine_templates() -> None:
    async with async_session() as session:
        result = await session.execute(select(FineTemplate.text))
        existing = set(result.scalars().all())
        for text, short_name in DEFAULT_FINE_TEMPLATES:
            if text not in existing:
                session.add(FineTemplate(text=text, short_name=short_name, owner="admin"))
        for text, short_name in DEFAULT_AUDIT_FINE_TEMPLATES:
            if text not in existing:
                session.add(FineTemplate(text=text, short_name=short_name, owner="audit"))
        await session.commit()


async def seed_settings() -> None:
    async with async_session() as session:
        if await get_setting(session, "default_parent_chat_id") is None:
            await set_setting(session, "default_parent_chat_id", DEFAULT_PARENT_CHAT_ID)


async def refresh_all_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands([BotCommand(command="start", description="Botni ishga tushirish")])
    async with async_session() as session:
        employees = (await session.execute(select(Employee))).scalars().all()
        for employee in employees:
            await apply_bot_commands(bot, session, employee)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN bot/.env faylida topilmadi")

    await init_db()
    await seed_roles()
    await seed_fine_templates()
    await seed_admins()
    await seed_audit_account()
    await seed_settings()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(audit.router)
    dp.include_router(crm.router)
    dp.include_router(panel.router)
    dp.include_router(profile.router)

    asyncio.create_task(payment_reminder_loop(bot))
    await refresh_all_bot_commands(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
