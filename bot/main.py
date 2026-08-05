import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent, Message
from sqlalchemy import select

from config import ADMIN_IDS, BASE_DIR, BOT_TOKEN, DEFAULT_PARENT_CHAT_ID
from database import async_session, init_db
from handlers import admin, crm, panel, profile, start
from handlers.crm import payment_reminder_loop
from keyboards import KEYBOARD_VERSION
from models import Employee, Role
from utils import apply_bot_commands, get_setting, log_inbound_message, reply_keyboard_for_employee, set_setting

logger = logging.getLogger(__name__)

DEFAULT_ROLES = [
    ("Main teacher", False),
    ("Support teacher", False),
    ("Reception", False),
    ("Oddiy foydalanuvchi (Ota-ona)", True),
]


async def seed_admins() -> None:
    """.env'dagi ADMIN_IDS — botning boshlang'ich (bootstrap) egalari, shuning uchun
    to'liq huquqli superadmin sifatida urug'lanadi."""
    if not ADMIN_IDS:
        return
    async with async_session() as session:
        for tg_id in ADMIN_IDS:
            result = await session.execute(select(Employee).where(Employee.telegram_id == tg_id))
            employee = result.scalar_one_or_none()
            if employee is None:
                employee = Employee(
                    telegram_id=tg_id, full_name=f"Admin {tg_id}", is_admin=True, is_superadmin=True
                )
                session.add(employee)
                await session.commit()
                await session.refresh(employee)
            elif not employee.is_admin or not employee.is_superadmin:
                employee.is_admin = True
                employee.is_superadmin = True
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


async def refresh_reply_keyboards_if_changed(bot: Bot) -> None:
    """Doimiy pastki tugmalar tarkibi (KEYBOARD_VERSION) o'zgargan bo'lsa, hamma
    foydalanuvchiga jim (bildirishnomasiz) yangilangan tugmalarni qayta yuboradi —
    aks holda Telegram eski tugmalarni saqlab qoladi (faqat yangi xabar bilan yangilanadi)."""
    async with async_session() as session:
        stored_version = await get_setting(session, "keyboard_version")
        if stored_version == KEYBOARD_VERSION:
            return
        employees = (await session.execute(select(Employee))).scalars().all()
        for employee in employees:
            keyboard = await reply_keyboard_for_employee(session, employee)
            if keyboard is None:
                continue
            try:
                await bot.send_message(
                    employee.telegram_id,
                    "\U0001f504 Pastdagi tugmalar yangilandi.",
                    reply_markup=keyboard,
                    disable_notification=True,
                )
            except Exception:
                continue
        await set_setting(session, "keyboard_version", KEYBOARD_VERSION)


def _setup_logging() -> None:
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), file_handler],
    )


async def main() -> None:
    _setup_logging()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN bot/.env faylida topilmadi")

    await init_db()
    await seed_roles()
    await seed_admins()
    await seed_settings()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    async def _log_inbound_middleware(handler, event: Message, data: dict) -> object:
        try:
            await log_inbound_message(event)
        except Exception:
            logger.exception("Kiruvchi xabarni jurnalga yozib bo'lmadi")
        return await handler(event, data)

    dp.message.outer_middleware(_log_inbound_middleware)

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(crm.router)
    dp.include_router(panel.router)
    dp.include_router(profile.router)

    @dp.errors()
    async def handle_errors(event: ErrorEvent) -> bool:
        logger.exception("Update handling failed: %s", event.update, exc_info=event.exception)
        return True

    asyncio.create_task(payment_reminder_loop(bot))
    await refresh_all_bot_commands(bot)
    await refresh_reply_keyboards_if_changed(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot polling boshlanmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
