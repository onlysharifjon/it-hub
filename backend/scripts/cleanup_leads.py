"""Lidlar bo'limidagi to'plangan ma'lumot muammolarini tozalash (bir martalik).

Bajaradi:
  1. Dublikat lidlarni birlashtiradi (telefon formatlash farqi tufayli
     to'plangan — Facebook webhook aynan matn bo'yicha solishtirar edi).
  2. Egasi o'chirilgan foydalanuvchiga ishora qiluvchi lidlarni tizim
     adminiga bog'laydi.
  3. Yetim bildirishnoma va eslatmalarni o'chiradi.
  4. Referral statistikasini haqiqiy lidlardan qayta hisoblaydi.

Ishlatish:
    .venv/bin/python -m backend.scripts.cleanup_leads --dry-run
    .venv/bin/python -m backend.scripts.cleanup_leads --apply
"""
import argparse
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from ..database import SessionLocal
from .. import models
from ..models import UserRole
from ..phone_utils import dedup_key

# Bosqich turi bo'yicha ustunlik: to'lagan > jarayonda > rad etilgan
KIND_RANK = {"won": 3, "lead": 2, "lost": 1}


def _rank(lead: models.Lead, stages: dict) -> tuple:
    st = stages.get(lead.stage_id)
    kind_rank = KIND_RANK.get(st.kind if st else "lead", 2)
    order = st.order if st else 0
    return (kind_rank, order, lead.created_at or datetime.min)


def merge_duplicates(db: Session, apply: bool) -> int:
    stages = {s.id: s for s in db.query(models.LeadStage).all()}
    groups = defaultdict(list)
    for lead in db.query(models.Lead).all():
        key = dedup_key(lead.phone)
        if key:
            groups[key].append(lead)

    merged = 0
    for key, leads in groups.items():
        if len(leads) < 2:
            continue
        # Eng "uzoqqa borgan" yozuvni saqlaymiz, qolganlarini unga qo'shamiz
        leads.sort(key=lambda l: _rank(l, stages), reverse=True)
        keeper, losers = leads[0], leads[1:]
        for loser in losers:
            note_lines = [
                f"Dublikat lid #{loser.id} (tel: {loser.phone}, "
                f"bosqich: {loser.status}, qo'shilgan: "
                f"{loser.created_at:%d.%m.%Y}) shu lidga birlashtirildi."
            ]
            if loser.notes and (not keeper.notes or loser.notes not in keeper.notes):
                note_lines.append(f"Dublikatdagi izoh:\n{loser.notes}")
            print(f"  #{loser.id} -> #{keeper.id}  ({loser.phone} / {keeper.phone})")
            if not apply:
                merged += 1
                continue

            # Tarix, eslatma va Facebook havolalarini saqlab qolamiz
            db.query(models.LeadActivity).filter(
                models.LeadActivity.lead_id == loser.id
            ).update({"lead_id": keeper.id}, synchronize_session=False)
            db.query(models.Reminder).filter(
                models.Reminder.lead_id == loser.id
            ).update({"lead_id": keeper.id}, synchronize_session=False)
            db.query(models.FacebookLead).filter(
                models.FacebookLead.lead_id == loser.id
            ).update({"lead_id": keeper.id}, synchronize_session=False)

            # Bo'sh maydonlarni dublikatdagi ma'lumot bilan to'ldiramiz
            for field in ("callback_at", "date_of_birth", "parent_phone",
                          "parent2_phone", "interested_group_id", "course_interest"):
                if getattr(keeper, field) is None and getattr(loser, field) is not None:
                    setattr(keeper, field, getattr(loser, field))

            db.add(models.LeadActivity(
                lead_id=keeper.id, action="note",
                description="\n".join(note_lines),
                author_id=None, created_at=datetime.utcnow(),
            ))
            db.delete(loser)
            merged += 1
        if apply:
            keeper.phone_key = dedup_key(keeper.phone)
            keeper.updated_at = datetime.utcnow()
    if apply:
        db.commit()
    return merged


def fix_orphan_owners(db: Session, apply: bool) -> int:
    system_admin = (
        db.query(models.User)
        .filter(models.User.role == UserRole.admin.value, models.User.is_active == True)  # noqa: E712
        .order_by(models.User.id.asc()).first()
    )
    if not system_admin:
        print("  Tizim admini topilmadi — o'tkazib yuborildi")
        return 0
    alive = {u[0] for u in db.query(models.User.id).all()}
    orphans = [l for l in db.query(models.Lead).all() if l.created_by_id not in alive]
    print(f"  {len(orphans)} ta lid -> {system_admin.username} (#{system_admin.id})")
    if apply:
        for l in orphans:
            l.created_by_id = system_admin.id
        db.commit()
    return len(orphans)


def drop_orphan_rows(db: Session, apply: bool) -> int:
    alive = {u[0] for u in db.query(models.User.id).all()}
    fallback = (
        db.query(models.User)
        .filter(models.User.role == UserRole.admin.value, models.User.is_active == True)  # noqa: E712
        .order_by(models.User.id.asc()).first()
    )
    lead_ids = {l[0] for l in db.query(models.Lead.id).all()}
    bad_notifs = [n for n in db.query(models.Notification).all() if n.user_id not in alive]
    bad_rems = [
        r for r in db.query(models.Reminder).all()
        if r.lead_id not in lead_ids
        or (r.assigned_to_id and r.assigned_to_id not in alive)
        or r.created_by_id not in alive
    ]
    print(f"  {len(bad_notifs)} yetim bildirishnoma, {len(bad_rems)} yetim eslatma")
    if apply:
        for n in bad_notifs:
            db.delete(n)
        for r in bad_rems:
            # Eslatma o'zi haqiqiy lidga tegishli bo'lsa — faqat yetim
            # foydalanuvchi havolasini uzamiz, yozuvni saqlaymiz.
            if r.lead_id in lead_ids:
                if r.assigned_to_id and r.assigned_to_id not in alive:
                    r.assigned_to_id = None
                if r.created_by_id not in alive:
                    # created_by_id NOT NULL — bo'sh qoldirib bo'lmaydi,
                    # tizim adminiga o'tkazamiz.
                    r.created_by_id = r.assigned_to_id or (fallback.id if fallback else r.created_by_id)
            else:
                db.delete(r)
        db.commit()
    return len(bad_notifs) + len(bad_rems)


def recompute_referrals(db: Session, apply: bool) -> int:
    won_stage_ids = {
        s.id for s in db.query(models.LeadStage).filter(models.LeadStage.kind == "won").all()
    }
    leads = db.query(models.Lead).all()

    # 1. "To'landi"dan chiqib ketgan lidlarda hisob belgisi qolmasin
    for l in leads:
        in_won = l.stage_id in won_stage_ids
        if not in_won and l.referral_credited_at:
            l.referral_credited_at = None
        elif in_won and not l.referral_credited_at:
            l.referral_credited_at = l.updated_at or l.created_at

    # 2. Statistikani haqiqiy lidlardan qayta yig'amiz
    fresh = defaultdict(lambda: {"leads": 0, "paid": 0})
    for l in leads:
        if not l.referred_by_id:
            continue
        if l.created_at:
            fresh[(l.referred_by_id, l.created_at.strftime("%Y-%m"))]["leads"] += 1
        if l.referral_credited_at:
            fresh[(l.referred_by_id, l.referral_credited_at.strftime("%Y-%m"))]["paid"] += 1

    existing = {(s.referrer_id, s.period): s for s in db.query(models.LeadReferralStat).all()}
    changed = 0
    for (rid, period), vals in sorted(fresh.items()):
        row = existing.pop((rid, period), None)
        if row:
            if row.leads_count != vals["leads"] or row.paid_count != vals["paid"]:
                print(f"  #{rid} {period}: lidlar {row.leads_count}->{vals['leads']}, "
                      f"to'landi {row.paid_count}->{vals['paid']}")
                changed += 1
                if apply:
                    row.leads_count = vals["leads"]
                    row.paid_count = vals["paid"]
                    row.updated_at = datetime.utcnow()
        else:
            print(f"  #{rid} {period}: yangi qator ({vals['leads']} / {vals['paid']})")
            changed += 1
            if apply:
                db.add(models.LeadReferralStat(
                    referrer_id=rid, period=period,
                    leads_count=vals["leads"], paid_count=vals["paid"],
                    created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
                ))
    for (rid, period), row in existing.items():
        print(f"  #{rid} {period}: lid qolmagan, nolga tushiriladi "
              f"({row.leads_count} / {row.paid_count})")
        changed += 1
        if apply:
            row.leads_count = 0
            row.paid_count = 0
            row.updated_at = datetime.utcnow()
    if apply:
        db.commit()
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="o'zgarishlarni yozish")
    ap.add_argument("--dry-run", action="store_true", help="faqat ko'rsatish (default)")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    try:
        print(f"\n{'=== QO‘LLANMOQDA ===' if apply else '=== SINOV (dry-run) ==='}\n")
        print("1. Dublikat lidlarni birlashtirish")
        n1 = merge_duplicates(db, apply)
        print(f"   -> {n1} ta yozuv birlashtirildi\n")
        print("2. Egasi o'chirilgan lidlar")
        n2 = fix_orphan_owners(db, apply)
        print()
        print("3. Yetim bildirishnoma/eslatmalar")
        n3 = drop_orphan_rows(db, apply)
        print()
        print("4. Referral statistikasini qayta hisoblash")
        n4 = recompute_referrals(db, apply)
        print(f"   -> {n4} ta qator o'zgardi\n")
        if not apply:
            print("Hech narsa yozilmadi. Qo'llash uchun: --apply")
    finally:
        db.close()


if __name__ == "__main__":
    main()
