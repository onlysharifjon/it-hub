"""Ish markazi uchun ikkita YANGI jadval yaratadi.

  call_activities — qo'ng'iroq yozuvlari (o'zgartirilmaydigan tarix)
  work_tasks      — vazifa holati (bajarildi / surildi / o'tkazib yuborildi)

Faqat QO'SHADI: mavjud jadvallarga, ustunlarga yoki ma'lumotga tegmaydi.
`create_all` idempotent — jadval allaqachon bo'lsa hech narsa qilmaydi,
shuning uchun skriptni qayta ishga tushirish xavfsiz.

Ishga tushirish:
    .venv/bin/python backend/scripts/create_work_center_tables.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, "/var/www/it-hub")

DB = os.environ.get("ITHUB_DB", "/var/www/it-hub/data/ithub.db")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + DB)

from backend.database import engine          # noqa: E402
from backend import models                   # noqa: E402

NEW_TABLES = [models.CallActivity.__table__, models.WorkTask.__table__]


def main() -> int:
    before = _tables()
    print("Baza:", DB)
    print("Mavjud jadvallar:", len(before))

    models.Base.metadata.create_all(engine, tables=NEW_TABLES)

    after = _tables()
    created = sorted(after - before)
    for t in ("call_activities", "work_tasks"):
        state = "yaratildi" if t in created else ("allaqachon bor edi" if t in after else "YARATILMADI")
        print(f"  {t:18} — {state}")
    if not {"call_activities", "work_tasks"} <= after:
        print("XATO: jadvallar yaratilmadi", file=sys.stderr)
        return 1
    print("Boshqa jadvallarga tegilmadi:", len(after) - len(created), "ta o'zgarishsiz")
    return 0


def _tables() -> set:
    db = sqlite3.connect(DB)
    try:
        return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
