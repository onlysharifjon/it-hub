import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent
from sqlalchemy import select

from config import (
    ADMIN_IDS,
    AUDIT_SEED_ID,
    AUDIT_SEED_LOGIN,
    AUDIT_SEED_PASSWORD,
    BASE_DIR,
    BOT_TOKEN,
    DEFAULT_PARENT_CHAT_ID,
)
from database import async_session, init_db
from handlers import admin, audit, crm, panel, profile, start
from handlers.crm import payment_reminder_loop
from models import AuditAccount, Employee, FineTemplate, Role
from utils import apply_bot_commands, get_setting, hash_password, set_setting

logger = logging.getLogger(__name__)

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

# Ichki tartib qoidalari kodeksi — (kod, daraja, qisqa nom, to'liq qoida matni).
# Pulsiz: audit shu shablonni tanlasa, shtraf summasi so'ralmaydi (amount=0),
# faqat kulrang/sariq/qizil ogohlantirish sifatida qayd etiladi.
DISCIPLINE_CODE_TEMPLATES = [
    ("1.1", "gray", "1.1 Bedjik taqmaslik", "Korxona hududida doimo bedjik taqilgan holda bo'lish."),
    ("1.2", "gray", "1.2 Mijozga sovuqqonlik", "Mijozlar bilan doimo kulib, hushmuomilalikda gaplashish."),
    ("1.3", "gray", "1.3 Stolda begona buyum", "Administratsiya stoli ustida ortiqcha buyumlar, shaxsiy buyumlar, shaxsiy telefon, qog'ozlar, hujjatlar turishi taqiqlanadi."),
    ("1.4", "gray", "1.4 Stolga bosh qo'yish", "Administratsiya stoliga bosh qo'yib yotish taqiqlanadi."),
    ("1.5", "gray", "1.5 Idishsiz ichimlik", "Korxona hududida rangli ichimliklarni faqat shaxsiy kружка (finjon) ga solgan holda ichish talab etiladi."),
    ("1.6", "gray", "1.6 Kelmaganga bog'lanmaslik", "Darsga kelmagan o'quvchilar bilan bog'lanib ertangi kun soat 12:00 gacha kelmaganlik sababini aniqlash, kelasi darsga chaqirish hamda izohlarda kelmaganlik sababini kiritib o'tish talab etiladi."),
    ("1.7", "gray", "1.7 Hisobot to'ldirmaslik", "Filial kesmidagi hisobotlarni belgilangan vaqt ichida to'g'ri va to'liq to'ldirish talab etiladi."),
    ("1.8", "gray", "1.8 Muzlaganga bog'lanmaslik", "Muzlatilgan o'quvchilar bilan kelishi kerak bo'lgan sanada bog'lanish, darsga chaqirish hamda izohlarni yangilash talab etiladi."),
    ("2.1", "yellow", "2.1 Check-in/out qilmaslik", "Verefixdan to'g'ri va belgilangan tartibda foydalanish. Ishga kelgan vaqtda va ketayotganda o'z vaqtida check-in va check-out qilish talab etiladi."),
    ("2.2", "yellow", "2.2 Kiyinish tartibi buzilishi", "Kiyinish uslubi va tashqi ko'rinish talablariga rioya qilmaslik (erkaklar/ayollar uchun belgilangan klassik uslub, taqiqlangan kiyimlar)."),
    ("2.3", "yellow", "2.3 Ish vaqtida telefon", "Ish vaqtida shaxsiy telefondan foydalanish taqiqlanadi."),
    ("2.4", "yellow", "2.4 Ijtimoiy tarmoq", "Ish kompyuteridan ishga aloqador bo'lmagan ijtimoiy tarmoqlarga kirish taqiqlanadi."),
    ("2.5", "yellow", "2.5 Shaxsiy ish bilan band", "Ish vaqtida shaxsiy ishlar bilan shug'ullanish taqiqlanadi."),
    ("2.6", "yellow", "2.6 Kassaga sababsiz o'tish", "Kassa hududiga besabab o'tish taqiqlanadi."),
    ("2.7", "yellow", "2.7 O'tirib konsultatsiya", "Mijozlarga turgan holda konsultatsiya berish talab etiladi."),
    ("2.8", "yellow", "2.8 Tushlikda kech qolish", "Tushlikda ajratilgan vaqtdan ko'p qolib ketish, ajratilgan vaqtda emas boshqa vaqtda tushlik qilish taqiqlanadi."),
    ("2.9", "yellow", "2.9 20 daq gacha kechikish", "Korxonaga o'z vaqtida kelish (20 daqiqagacha kechikish)."),
    ("2.10", "yellow", "2.10 Ish joyini tark etish", "Ish joyini sababsiz tark etish taqiqlanadi (20 daqiqa va undan ko'p)."),
    ("2.11", "yellow", "2.11 Bedjiksiz (2-marta)", "Korxona hududida doimo bedjik taqilgan holda bo'lish — kun davomida 2-marotaba buzilgan holat."),
    ("3.1", "red", "3.1 Ovqatlanish (ma'muriyat)", "Administratsiya hududida ovqatlanish, yegulik yeyish taqiqlanadi."),
    ("3.2", "red", "3.2 Pardoz/soch tarash", "Administratsiya hududida pardoz qilish va soch tarash, stol ustida pardoz vositalarini turishi taqiqlanadi."),
    ("3.3", "red", "3.3 Mijozga qo'pol gapirish", "Mijozlar bilan baland ovozda va qo'pol ohangda gaplashish taqiqlanadi."),
    ("3.4", "red", "3.4 Baland ovozda gaplashish", "Jamoa a'zolari va hamkasblar bilan coworking hududi, administratsiya hududi va dars xonalarida baland ovozda ishdan tashqari mavzuda gaplashish taqiqlanadi."),
    ("3.5", "red", "3.5 Musiqa tinglash", "Administratsiya hududida musiqa tinglash taqiqlanadi."),
    ("3.6", "red", "3.6 3+ soat ish joyida yo'q", "Sababsiz va ogohlantirishsiz ish vaqtida 3 soat va undan ko'p ish joyida bo'lmaslik."),
    ("3.7", "red", "3.7 21+ daq kechikish", "Korxonaga o'z vaqtida kelish (21 daqiqa va undan ko'p kechikish)."),
    ("3.8", "red", "3.8 Ogohlantirmay kelmaslik", "Eng kamida 1 kun avval ogohlantirmasdan, ruxsat so'ramasdan ishga kelmaslik."),
    ("3.9", "red", "3.9 Ruxsatsiz ketish", "Ruxsat so'ramasdan, ogohlantirishsiz ish vaqtida korxonadan ketish taqiqlanadi."),
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
        for code, severity, short_name, text in DISCIPLINE_CODE_TEMPLATES:
            if text not in existing:
                session.add(
                    FineTemplate(
                        text=text, short_name=short_name, owner="audit", code=code, severity=severity
                    )
                )
        await session.commit()

        # Audit endi faqat bandga asoslangan (pulsiz) shablonlardan foydalanadi — eski
        # pullik audit shablonlari butunlay o'chiriladi (Fine yozuvlari reason/severity/code'ni
        # o'z ustunlarida alohida saqlaydi, shablonga bog'liq emas — o'chirish tarixga ta'sir qilmaydi).
        legacy_result = await session.execute(
            select(FineTemplate).where(
                FineTemplate.owner == "audit",
                FineTemplate.severity.is_(None),
            )
        )
        for template in legacy_result.scalars().all():
            await session.delete(template)
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

    @dp.errors()
    async def handle_errors(event: ErrorEvent) -> bool:
        logger.exception("Update handling failed: %s", event.update, exc_info=event.exception)
        return True

    asyncio.create_task(payment_reminder_loop(bot))
    await refresh_all_bot_commands(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot polling boshlanmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
