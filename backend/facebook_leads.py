"""Facebook Lead Ads webhook — Make.com shu yerga POST qiladi.

Oqim: Facebook Lead Ads -> Make.com -> POST /leads/facebook (bu fayl).
Himoya: X-Webhook-Token header FACEBOOK_WEBHOOK_TOKEN'ga teng bo'lishi shart.
Har doim 200 yoki 4xx qaytariladi (5xx emas) — aks holda Make xatolik deb
qayta-qayta yuborib, dublikat lidlar hosil qiladi.

Har bir kelgan lid ikki joyga yoziladi:
  1. facebook_leads — xom capture jadvali (dedup/audit uchun).
  2. leads (CRM) — Lidlar bo'limida hunter/sales/call_center ko'radigan asosiy
     jadval, "Facebook" manba (LeadSource) bilan, umumiy havzaga (is_shared=True).
CRM lead faqat BIRINCHI (dublikat bo'lmagan) so'rovda yaratiladi — keyingi
takroriy so'rovlar xodimlar tomonidan kiritilgan qo'lda ma'lumotlarni
(masalan yozgan izohlarini) bosib yozib yubormasligi uchun CRM tomonini
qayta yangilamaydi, faqat xom facebook_leads yozuvini merge qiladi.

Telefon raqami: ba'zi Facebook formalar faqat email so'raydi, telefon
umuman kelmasligi mumkin — bunday holda ham lid rad etilmaydi (422 emas),
CRM'da vaqtinchalik "no-phone-<id>" belgisi bilan saqlanadi va izohda
xodimga aniq ko'rsatiladi.
"""
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .models import UserRole

load_dotenv()

FACEBOOK_WEBHOOK_TOKEN = os.getenv("FACEBOOK_WEBHOOK_TOKEN", "")

# Loyihada markazlashgan logging config yo'q — pm2/uvicorn stderr'ga chiqishi uchun
# shu yerda o'zimiz sozlaymiz (root logger'da handler bo'lmasa, basicConfig qo'shadi).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("facebook_leads")
logger.setLevel(logging.INFO)

router = APIRouter(tags=["facebook-leads"])

DEDUP_WINDOW = timedelta(minutes=5)


def _require_webhook_token(x_webhook_token: Optional[str] = Header(None, alias="X-Webhook-Token")) -> None:
    if not FACEBOOK_WEBHOOK_TOKEN or not x_webhook_token or not secrets.compare_digest(x_webhook_token, FACEBOOK_WEBHOOK_TOKEN):
        logger.warning("Rad etildi: noto'g'ri yoki yo'q X-Webhook-Token")
        raise HTTPException(status_code=401, detail="Noto'g'ri webhook token")


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_created_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    # Facebook/Make ba'zan offset'ni ':' siz yuboradi (masalan +0000) — fromisoformat buni tushunmaydi
    normalized = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', normalized)
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        logger.warning("created_time formatini o'qib bo'lmadi: %r", value)
        return None


def _get_or_create_facebook_source(db: Session) -> models.LeadSource:
    src = db.query(models.LeadSource).filter(models.LeadSource.name == "Facebook").first()
    if not src:
        src = models.LeadSource(name="Facebook", is_campaign=True, is_default=False, is_active=True)
        db.add(src)
        db.flush()
    return src


def _default_stage(db: Session) -> Optional[models.LeadStage]:
    return (
        db.query(models.LeadStage)
        .filter(models.LeadStage.is_archived == False, models.LeadStage.kind == "lead")  # noqa: E712
        .order_by(models.LeadStage.order.asc())
        .first()
    )


REAPPLICATION_SLUG = "reapplication"


def _reapplication_stage(db: Session) -> Optional[models.LeadStage]:
    """"Qayta ariza" bosqichi — telefon raqami bazada boshqa bosqichda allaqachon
    bor bo'lsa, Facebook'dan qayta kelgan lid "Yangi"ga emas, shu bosqichga tushadi.
    Bosqich mavjud bo'lmasa, birinchi chaqiriqda avtomatik yaratiladi."""
    stage = db.query(models.LeadStage).filter(models.LeadStage.slug == REAPPLICATION_SLUG).first()
    if stage:
        return stage
    new_stage_order = (
        db.query(models.LeadStage)
        .filter(models.LeadStage.slug == "new")
        .with_entities(models.LeadStage.order)
        .scalar()
    )
    stage = models.LeadStage(
        name="Qayta ariza",
        slug=REAPPLICATION_SLUG,
        order=(new_stage_order + 5) if new_stage_order is not None else 15,
        color="orange",
        icon="circle",
        kind="lead",
    )
    db.add(stage)
    db.flush()
    return stage


def _current_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _bump_referral_stat(db: Session, referrer_id: Optional[int], *, leads_delta: int = 0, paid_delta: int = 0) -> None:
    """Manba egasi (masalan Facebook/Instagram'ni yurituvchi sales) uchun
    joriy oy statistikasini oshiradi — tarix saqlanishi uchun har oy alohida qator."""
    if not referrer_id:
        return
    period = _current_period()
    stat = (
        db.query(models.LeadReferralStat)
        .filter(models.LeadReferralStat.referrer_id == referrer_id, models.LeadReferralStat.period == period)
        .first()
    )
    if not stat:
        stat = models.LeadReferralStat(
            referrer_id=referrer_id, period=period, leads_count=0, paid_count=0,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(stat)
        db.flush()
    stat.leads_count += leads_delta
    stat.paid_count += paid_delta
    stat.updated_at = datetime.utcnow()


def _existing_lead_by_phone(db: Session, phone: str) -> Optional[models.Lead]:
    return (
        db.query(models.Lead)
        .filter(models.Lead.phone == phone)
        .order_by(models.Lead.created_at.desc())
        .first()
    )


def _system_user_id(db: Session) -> Optional[int]:
    u = (
        db.query(models.User.id)
        .filter(models.User.role == UserRole.admin.value)
        .order_by(models.User.id.asc()).first()
    )
    if not u:
        u = db.query(models.User.id).order_by(models.User.id.asc()).first()
    return u[0] if u else None


def _crm_recipient_ids(db: Session):
    rows = (
        db.query(models.User.id)
        .filter(
            models.User.is_active == True,  # noqa: E712
            models.User.role.in_([UserRole.admin.value, UserRole.call_center.value]),
        ).all()
    )
    return [r[0] for r in rows]


def _create_crm_lead(db: Session, *, full_name: Optional[str], phone: str,
                      email: Optional[str], form_name: Optional[str],
                      created_time_raw: Optional[str], phone_missing: bool = False,
                      existing_lead: Optional[models.Lead] = None) -> models.Lead:
    source = _get_or_create_facebook_source(db)
    stage = _reapplication_stage(db) if existing_lead is not None else _default_stage(db)
    owner_id = _system_user_id(db)

    notes_lines = ["Facebook Lead Ads orqali (Make.com webhook) avtomatik yaratildi."]
    if existing_lead is not None:
        notes_lines.append(
            f"Bu raqam bazada allaqachon bor edi (lid #{existing_lead.id}, "
            f"bosqich: {existing_lead.status}) — shuning uchun \"Qayta ariza\"ga tushdi."
        )
    if phone_missing:
        notes_lines.append(
            "DIQQAT: Facebook'dan telefon raqami kelmagan (forma faqat email so'ragan bo'lishi mumkin) — "
            "mijoz bilan email orqali bog'laning yoki telefonni qo'lda toping va shu yerga kiriting."
        )
    if email:
        notes_lines.append(f"Email: {email}")
    if form_name:
        notes_lines.append(f"Forma: {form_name}")
    if created_time_raw:
        notes_lines.append(f"Facebook'da yaratilgan vaqt: {created_time_raw}")

    display_name = full_name or ("Facebook lid (telefon yo'q)" if phone_missing else f"Facebook lid ({phone})")
    lead = models.Lead(
        full_name=display_name,
        phone=phone,
        status=stage.slug if stage else models.LeadStatus.new.value,
        stage_id=stage.id if stage else None,
        source_id=source.id,
        notes="\n".join(notes_lines),
        is_shared=True,
        created_by_id=owner_id,
        referred_by_id=source.referrer_id,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.flush()
    _bump_referral_stat(db, source.referrer_id, leads_delta=1)

    db.add(models.LeadActivity(
        lead_id=lead.id,
        action="created",
        description="Facebook Lead Ads webhook orqali avtomatik yaratildi",
        author_id=None,
        created_at=datetime.utcnow(),
    ))
    recipients = _crm_recipient_ids(db)
    if recipients:
        now = datetime.utcnow()
        contact = f"email: {email}" if phone_missing and email else lead.phone
        for uid in set(recipients):
            db.add(models.Notification(
                user_id=uid, notification_type="new_lead",
                title="Facebook'dan yangi lid",
                body=f"{lead.full_name} · {contact}",
                link=f"/leads?lead={lead.id}",
                is_read=False, created_at=now,
            ))
    return lead


@router.post("/leads/facebook")
def receive_facebook_lead(
    payload: schemas.FacebookLeadIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_require_webhook_token),
):
    client_ip = request.client.host if request.client else None
    raw_phone = _blank_to_none(payload.phone)
    logger.info(
        "Qabul qilindi: phone=%s full_name=%r form=%r ip=%s",
        raw_phone, payload.full_name, payload.form_name, client_ip,
    )

    # Telefon bo'lmagan (faqat email so'ragan forma) lidlarni dedup qila olmaymiz —
    # bunday holatda har doim yangi yozuv sifatida saqlaymiz (hech narsa yo'qolmasin).
    existing = None
    if raw_phone is not None:
        cutoff = datetime.utcnow() - DEDUP_WINDOW
        existing = (
            db.query(models.FacebookLead)
            .filter(models.FacebookLead.phone == raw_phone, models.FacebookLead.received_at >= cutoff)
            .order_by(models.FacebookLead.received_at.desc())
            .first()
        )
    if existing:
        # Merge: yangi qiymat bo'sh bo'lmasa yangilaymiz, bo'sh bo'lsa eski (mavjud)
        # ma'lumotni saqlab qolamiz. CRM'dagi Lead'ga tegilmaydi — xodim allaqachon
        # ustida ishlagan bo'lishi mumkin, qo'lda kiritilgan narsani bosib yozmaymiz.
        new_full_name = _blank_to_none(payload.full_name)
        new_email = _blank_to_none(payload.email)
        new_form_name = _blank_to_none(payload.form_name)
        new_created_time = _parse_created_time(payload.created_time)
        if new_full_name is not None:
            existing.full_name = new_full_name
        if new_email is not None:
            existing.email = new_email
        if new_form_name is not None:
            existing.form_name = new_form_name
        if new_created_time is not None:
            existing.created_time = new_created_time
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Dublikatni birlashtirishda xatolik: phone=%s", raw_phone)
            raise HTTPException(status_code=400, detail="Lidni saqlab bo'lmadi")
        logger.info("Dublikat, mavjud yozuv bilan birlashtirildi: phone=%s existing_id=%s existing_lead_id=%s",
                    raw_phone, existing.id, existing.lead_id)
        return {"status": "ok", "lead_id": existing.id, "duplicate": True}

    fb_lead = models.FacebookLead(
        full_name=_blank_to_none(payload.full_name),
        phone=raw_phone,
        email=_blank_to_none(payload.email),
        form_name=_blank_to_none(payload.form_name),
        source="facebook",
        created_time=_parse_created_time(payload.created_time),
        received_at=datetime.utcnow(),
    )
    try:
        db.add(fb_lead)
        db.flush()
        phone_missing = fb_lead.phone is None
        crm_phone = fb_lead.phone or f"no-phone-{fb_lead.id}"
        existing_lead = None if phone_missing else _existing_lead_by_phone(db, crm_phone)
        crm_lead = _create_crm_lead(
            db,
            full_name=fb_lead.full_name,
            phone=crm_phone,
            email=fb_lead.email,
            form_name=fb_lead.form_name,
            created_time_raw=payload.created_time,
            phone_missing=phone_missing,
            existing_lead=existing_lead,
        )
        fb_lead.lead_id = crm_lead.id
        db.commit()
        db.refresh(fb_lead)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Bazaga yozishda xatolik: phone=%s", raw_phone)
        raise HTTPException(status_code=400, detail="Lidni saqlab bo'lmadi")

    logger.info("Saqlandi: facebook_lead_id=%s lead_id=%s phone=%s", fb_lead.id, fb_lead.lead_id, fb_lead.phone)
    return {"status": "ok", "lead_id": fb_lead.id}
