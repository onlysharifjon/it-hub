import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _parse_ids(raw: str) -> set[int]:
    return {int(part) for part in raw.replace(" ", "").split(",") if part}


ADMIN_IDS = _parse_ids(os.getenv("ADMIN_IDS", ""))

# Ixtiyoriy: birinchi marta ishga tushirishda bitta audit akkaunt urug'lash uchun
AUDIT_SEED_ID = os.getenv("AUDIT_SEED_ID", "")
AUDIT_SEED_LOGIN = os.getenv("AUDIT_SEED_LOGIN", "")
AUDIT_SEED_PASSWORD = os.getenv("AUDIT_SEED_PASSWORD", "")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'bot.db'}")

# CRM (backend) bilan bog'lanish uchun — guruhlar/o'quvchilar va davomat shu orqali olinadi
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "http://localhost:8000")
# Production'da nginx API so'rovlarini /api ostida backendga yo'naltiradi; to'g'ridan-to'g'ri
# uvicorn (masalan lokal http://localhost:8000) uchun bo'sh qoldiring: CRM_API_PREFIX=
CRM_API_PREFIX = os.getenv("CRM_API_PREFIX", "/api")
CRM_USERNAME = os.getenv("CRM_USERNAME", "admin")
CRM_PASSWORD = os.getenv("CRM_PASSWORD", "Admin@2026")

# Davomat xabarlari yuboriladigan standart ota-ona Telegram ID (har bir o'quvchi uchun
# alohida biriktirish ishlamaguncha, hammasi shu bitta ID ga boradi). Admin panel orqali
# keyinchalik o'zgartirish mumkin — bu faqat birinchi marta urug'lash uchun.
DEFAULT_PARENT_CHAT_ID = os.getenv("DEFAULT_PARENT_CHAT_ID", "8213783370")
