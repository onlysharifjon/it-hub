import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _parse_ids(raw: str) -> set[int]:
    return {int(part) for part in raw.replace(" ", "").split(",") if part}


ADMIN_IDS = _parse_ids(os.getenv("ADMIN_IDS", ""))

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'bot.db'}")

# CRM ma'lumotlari (guruhlar/o'quvchilar/to'lovlar) endi backendning o'z Postgres bazasidan
# to'g'ridan-to'g'ri (faqat SELECT) o'qiladi — HTTP/login shart emas. Bu backendning o'zi
# ishlatadigan DATABASE_URL bilan bir xil bo'lishi kerak (masalan bot va backend bir serverda
# bo'lsa: postgresql://postgres:PAROL@localhost:5432/ithub_db). Bo'sh qoldirilsa, backend/database.py
# o'zining standart qiymatiga (yoki backend/.env'iga) tayanadi.
CRM_DB_URL = os.getenv("CRM_DB_URL", "")

# Davomat xabarlari yuboriladigan standart ota-ona Telegram ID (har bir o'quvchi uchun
# alohida biriktirish ishlamaguncha, hammasi shu bitta ID ga boradi). Admin panel orqali
# keyinchalik o'zgartirish mumkin — bu faqat birinchi marta urug'lash uchun.
DEFAULT_PARENT_CHAT_ID = os.getenv("DEFAULT_PARENT_CHAT_ID", "")
