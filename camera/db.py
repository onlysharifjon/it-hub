"""Backend bazasidan o'quvchi ma'lumotlarini o'qish (faqat o'qish uchun)."""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import config

log = logging.getLogger("camera.db")

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)
    return _engine


def get_student(student_id: int) -> dict | None:
    """student_id bo'yicha ism, telegram_id va guruhlar ro'yxatini qaytaradi."""
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT id, full_name, telegram_id FROM students WHERE id = :id"),
                {"id": student_id},
            ).mappings().first()
            if not row:
                return None
            data = dict(row)
            # Guruhlarni ham yuklaymiz
            groups_rows = conn.execute(
                text("""
                    SELECT g.id, g.name FROM groups g
                    JOIN group_students gs ON gs.group_id = g.id
                    WHERE gs.student_id = :sid AND g.is_active = true
                """),
                {"sid": student_id},
            ).mappings().all()
            data["groups"] = [{"id": r["id"], "name": r["name"]} for r in groups_rows]
            return data
    except Exception as exc:
        log.warning("Bazadan o'qishda xatolik (student_id=%s): %s", student_id, exc)
        return None


def get_staff(user_id: int) -> dict | None:
    """user_id bo'yicha xodim ma'lumotlarini qaytaradi."""
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT id, full_name, username, role FROM users WHERE id = :id AND is_active = true"),
                {"id": user_id},
            ).mappings().first()
            if not row:
                return None
            data = dict(row)
            data["groups"] = []  # xodimlar uchun guruh yo'q
            return data
    except Exception as exc:
        log.warning("Bazadan o'qishda xatolik (user_id=%s): %s", user_id, exc)
        return None
