"""Voronkaga "Javob bermadi" bosqichini qo'shadi (bir martalik migratsiya).

Nima uchun skript: `ensure_default_pipeline()` faqat `lead_stages` jadvali
BO'SH bo'lganda ishlaydi (mavjud sozlamalarni bosib ketmasligi uchun), ya'ni
ishlab turgan bazaga yangi standart bosqich o'z-o'zidan qo'shilmaydi.

Bosqich "Qo'ng'iroq qilindi" (20) va "Qayta qo'ng'iroq" (30) orasiga,
order=25 bilan qo'yiladi — hech bir mavjud bosqichning tartibi o'zgarmaydi.
Idempotent: qayta ishga tushirilsa hech narsa qilmaydi.

Ishga tushirish:  PYTHONPATH=/var/www/it-hub .venv/bin/python backend/scripts/add_no_answer_stage.py
"""

from datetime import datetime

from backend.database import SessionLocal
from backend import models

SLUG = "no_answer"
STAGE = {
    "slug": SLUG, "name": "Javob bermadi", "order": 25,
    "color": "slate", "icon": "phone-slash", "kind": "lead",
}


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(models.LeadStage).filter(models.LeadStage.slug == SLUG).first()
        if existing:
            print(f"Bosqich allaqachon bor (id={existing.id}, order={existing.order}) — o'zgarish yo'q.")
            return
        stage = models.LeadStage(**STAGE, created_at=datetime.utcnow())
        db.add(stage)
        db.commit()
        db.refresh(stage)
        print(f"Qo'shildi: id={stage.id} '{stage.name}' (slug={stage.slug}, order={stage.order})")
        for s in db.query(models.LeadStage).order_by(models.LeadStage.order).all():
            print(f"  {s.order:>3}  {s.name:<22} {s.slug:<15} {s.kind}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
