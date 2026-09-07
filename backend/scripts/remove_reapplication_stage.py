"""Bir martalik migratsiya: avtomatik yaratilgan "Qayta ariza" bosqichini olib tashlash.

Bu bosqichni hech kim so'ramagan — uni Facebook Lead Ads webhook'i
(`backend/facebook_leads.py`) 2026-08-29 da o'zi yaratib qo'ygan edi: telefon
raqami bazada allaqachon bor bo'lgan lid "Yangi"ga emas, o'sha ko'rinmas
ustunga tushardi. Voronkada bunday bosqich yo'q, shuning uchun lidlar u yerda
qo'ng'iroqsiz yig'ilib qolgan.

Skript:
  1. o'sha bosqichdagi lidlarni "Yangi" (slug='new') bosqichiga ko'chiradi;
  2. izohlardagi endi mavjud bo'lmagan bosqichga havolani to'g'rilaydi;
  3. har bir lid uchun tarix yozuvini qoldiradi;
  4. bosqichning o'zini o'chiradi.

Idempotent — ikkinchi marta ishga tushirilsa hech narsani o'zgartirmaydi.
Ishga tushirish:  python3 backend/scripts/remove_reapplication_stage.py
"""
import datetime
import os
import sqlite3
import sys

DB = os.environ.get("ITHUB_DB", "/var/www/it-hub/data/ithub.db")
SLUG = "reapplication"
TARGET_SLUG = "new"


def main() -> int:
    db = sqlite3.connect(DB)
    cur = db.cursor()

    stage = cur.execute(
        "SELECT id, name FROM lead_stages WHERE slug = ?", (SLUG,)
    ).fetchone()
    if not stage:
        print(f'"{SLUG}" bosqichi topilmadi — allaqachon olib tashlangan.')
        return 0
    stage_id, stage_name = stage

    target = cur.execute(
        "SELECT id FROM lead_stages WHERE slug = ?", (TARGET_SLUG,)
    ).fetchone()
    if not target:
        print(f'XATO: "{TARGET_SLUG}" bosqichi yo\'q — ko\'chirish mumkin emas.', file=sys.stderr)
        return 1
    target_id = target[0]

    ids = [
        r[0] for r in cur.execute(
            "SELECT id FROM leads WHERE stage_id = ? OR status = ?", (stage_id, SLUG)
        )
    ]
    print(f'"{stage_name}" (id={stage_id}) bosqichida {len(ids)} ta lid bor.')

    now = datetime.datetime.utcnow().isoformat(sep=" ")

    cur.execute(
        "UPDATE leads SET stage_id = ?, status = ? WHERE stage_id = ? OR status = ?",
        (target_id, TARGET_SLUG, stage_id, SLUG),
    )
    print(f'  "Yangi" bosqichiga ko\'chirildi: {cur.rowcount}')

    cur.execute(
        """UPDATE leads SET notes = REPLACE(notes,
               ' — shuning uchun "Qayta ariza"ga tushdi.', ' — takroriy ariza.')
           WHERE notes LIKE '%Qayta ariza%'"""
    )
    print(f"  izohlar to'g'rilandi: {cur.rowcount}")

    for lead_id in ids:
        cur.execute(
            """INSERT INTO lead_activities (lead_id, action, description, author_id, created_at)
               VALUES (?, 'stage_changed', ?, NULL, ?)""",
            (lead_id,
             'Avtomatik "Qayta ariza" bosqichi olib tashlandi — lid "Yangi" bosqichiga ko\'chirildi',
             now),
        )

    cur.execute("DELETE FROM lead_stages WHERE slug = ?", (SLUG,))
    print(f"  bosqich o'chirildi: {cur.rowcount}")

    db.commit()

    print("\nYakuniy holat:")
    for name, slug, count in db.execute(
        """SELECT s.name, s.slug, COUNT(l.id) FROM lead_stages s
           LEFT JOIN leads l ON l.stage_id = s.id
           GROUP BY s.id ORDER BY s."order" """
    ):
        print(f"  {name:24} {slug:14} {count}")
    left = db.execute(
        "SELECT COUNT(*) FROM leads WHERE status = ? OR notes LIKE '%Qayta ariza%'", (SLUG,)
    ).fetchone()[0]
    print(f'\nQolgan "Qayta ariza" izlari: {left}')
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
