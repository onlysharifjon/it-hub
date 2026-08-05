"""Botning o'z SQLite bazasiga (Employee/Role/AdminInviteLink/Setting) to'g'ridan-to'g'ri
o'qish/yozish — bot CRM Postgres bazasini qanday to'g'ridan-to'g'ri o'qiyotgan bo'lsa
(bot/crm_client.py), shu yerda teskari yo'nalishda xuddi shunday ishlaydi.

Botning o'zi bu jadvallarni o'qib/yozib turadi (aiosqlite, WAL rejimida) — shu bazaga
yozuvchi ikkinchi jarayon bo'lgani uchun bot.py'dagi PRAGMA journal_mode=WAL va
busy_timeout=5000 sozlamalariga tayanamiz (bir nechta jarayon bir vaqtda yozishi
mumkin bo'lishi uchun ishlatiladi).

Bu modul bot'ning ORM modellarini QAYTA E'LON QILMAYDI (import qilib bo'lmaydi —
bot alohida paket, aiogram-ga bog'liq) — shuning uchun bot/models.py'dagi jadvallarning
mustaqil, minimal ko'chirmasi shu yerda saqlanadi. Ustunlar o'zgarsa, ikkalasini ham
yangilash kerak.
"""
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BOT_DB = REPO_ROOT / "bot" / "data" / "bot.db"

BOT_DB_URL = os.getenv("BOT_DB_URL", f"sqlite:///{_DEFAULT_BOT_DB}")

bot_engine = create_engine(BOT_DB_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)
BotSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bot_engine)

BotBase = declarative_base()


class BotEmployee(BotBase):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    full_name = Column(String(255))
    username = Column(String(255), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_superadmin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("BotRole")


class BotRole(BotBase):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True)
    is_active = Column(Boolean, default=True)
    is_parent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class BotAdminInviteLink(BotBase):
    __tablename__ = "admin_invite_links"

    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True)
    tier = Column(String(16))
    created_by_id = Column(Integer, ForeignKey("employees.id"))
    used_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)


class BotSetting(BotBase):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True)
    value = Column(String(255))


class BotMessage(BotBase):
    """Bot orqali kelgan/yuborilgan har bir xabar jurnali — bot/models.py'dagi
    ko'chirma (mustaqil, mos jadval nomi bilan)."""
    __tablename__ = "bot_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, index=True)
    direction = Column(String(3))          # "in" | "out"
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    text = Column(Text, nullable=True)
    message_type = Column(String(30), default="text")
    sent_ok = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def log_bot_message(chat_id, direction: str, text: str = None, message_type: str = "auto_notify",
                     sent_ok: bool = True, full_name: str = None, username: str = None) -> None:
    """CRM'dan yuborilgan avtomatik xabarni jurnalga yozadi (Chatbot inbox uchun).
    Jurnalga yozib bo'lmasa ham asosiy oqim (xabar yuborish) to'xtamasligi kerak."""
    if not chat_id:
        return
    db = BotSessionLocal()
    try:
        db.add(BotMessage(
            chat_id=int(chat_id), direction=direction, text=text,
            full_name=full_name, username=username,
            message_type=message_type, sent_ok=sent_ok,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_bot_db():
    db = BotSessionLocal()
    try:
        yield db
    finally:
        db.close()
