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
    """student_id bo'yicha ism va telegram_id ni qaytaradi."""
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT id, full_name, telegram_id FROM students WHERE id = :id"),
                {"id": student_id},
            ).mappings().first()
            return dict(row) if row else None
    except Exception as exc:  # baza yo'q bo'lsa ham servis ishlashda davom etadi
        log.warning("Bazadan o'qishda xatolik (student_id=%s): %s", student_id, exc)
        return None
