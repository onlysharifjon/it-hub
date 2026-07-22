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
