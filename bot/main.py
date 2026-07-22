import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select

from config import ADMIN_IDS, AUDIT_SEED_ID, AUDIT_SEED_LOGIN, AUDIT_SEED_PASSWORD, BOT_TOKEN
from database import async_session, init_db
from handlers import admin, audit, panel, profile, start
from models import AuditAccount, Employee, FineTemplate, Role
from utils import hash_password

DEFAULT_ROLES = ["Main teacher", "Support teacher", "Reception", "Oddiy foydalanuvchi (Ota-ona)"]

DEFAULT_FINE_TEMPLATES = [
    "Kechikish",
    "Ishga kelmaslik",
    "Intizom buzilishi",
    "Formadan tashqari kiyinish",
    "Mijoz bilan noto'g'ri muomala",
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
        result = await session.execute(select(Role.name))
        existing = set(result.scalars().all())
        for name in DEFAULT_ROLES:
            if name not in existing:
                session.add(Role(name=name))
        await session.commit()


async def seed_fine_templates() -> None:
    async with async_session() as session:
        result = await session.execute(select(FineTemplate.text))
        existing = set(result.scalars().all())
        for text in DEFAULT_FINE_TEMPLATES:
            if text not in existing:
                session.add(FineTemplate(text=text))
        await session.commit()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN bot/.env faylida topilmadi")

    await init_db()
    await seed_roles()
    await seed_fine_templates()
    await seed_admins()
    await seed_audit_account()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(audit.router)
    dp.include_router(panel.router)
    dp.include_router(profile.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
