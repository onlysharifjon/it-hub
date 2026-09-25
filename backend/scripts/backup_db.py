"""Kunlik avtomatik backup: SQLite bazasi (onlayn, izchil nusxa) + uploads papkasi.

Cron (ubuntu foydalanuvchisi, har kuni 03:30 Toshkent = 22:30 UTC):
    30 22 * * * cd /var/www/it-hub && .venv/bin/python -m backend.scripts.backup_db >> data/backups/auto/backup.log 2>&1

- Baza `sqlite3.Connection.backup()` bilan nusxalanadi — backend ishlab turganda
  ham (WAL rejimida) izchil nusxa beradi, oddiy `cp` esa yarim yozilgan faylni olishi mumkin.
- Nusxa `PRAGMA integrity_check` bilan tekshiriladi va gzip qilinadi.
- Oxirgi KEEP_DAYS kunlik nusxa saqlanadi, eskilari o'chiriladi.
"""
import gzip
import os
import shutil
import sqlite3
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "14"))
DEST = Path(os.getenv("BACKUP_DIR", str(ROOT / "data" / "backups" / "auto")))


def _db_path() -> Path:
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("sqlite:///"):
        sys.exit(f"Faqat SQLite qo'llab-quvvatlanadi (DATABASE_URL={url.split(':', 1)[0]}...)")
    return Path(url[len("sqlite:///"):])


def backup_db(stamp: str) -> Path:
    src = _db_path()
    tmp = DEST / f"ithub-{stamp}.db"
    s, d = sqlite3.connect(f"file:{src}?mode=ro", uri=True), sqlite3.connect(tmp)
    try:
        s.backup(d)
        ok = d.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        s.close()
        d.close()
    if ok != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity_check xato: {ok}")
    out = tmp.with_suffix(".db.gz")
    with open(tmp, "rb") as f, gzip.open(out, "wb") as g:
        shutil.copyfileobj(f, g)
    tmp.unlink()
    return out


def backup_uploads(stamp: str) -> Path | None:
    up = Path(os.getenv("UPLOAD_DIR", str(ROOT / "uploads")))
    if not up.is_dir():
        return None
    out = DEST / f"uploads-{stamp}.tar.gz"
    with tarfile.open(out, "w:gz") as t:
        t.add(up, arcname="uploads")
    return out


def prune() -> int:
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    n = 0
    for p in DEST.glob("*.gz"):
        if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
            p.unlink()
            n += 1
    return n


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    os.chmod(DEST, 0o700)  # ichida parol hashlari bor — faqat egasi o'qiy olsin
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    db = backup_db(stamp)
    up = backup_uploads(stamp)
    for p in (db, up):
        if p:
            os.chmod(p, 0o600)
    removed = prune()
    print(f"{datetime.now():%F %T} OK db={db.name} ({db.stat().st_size} B)"
          f" uploads={up.name if up else '-'} pruned={removed}")


if __name__ == "__main__":
    main()
