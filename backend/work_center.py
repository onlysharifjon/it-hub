"""Ish markazi — kunlik vazifa navbatini CRM ma'lumotidan yig'adi.

Asosiy g'oya: xodim "bugun kimga qo'ng'iroq qilaman?" deb o'ylamasligi kerak.
Javob allaqachon bazada bor — kechikkan callback, ketma-ket darsga kelmagan
o'quvchi, qarzdor talaba. Bu modul o'sha ma'lumotni bitta tartiblangan
ro'yxatga aylantiradi.

── Nega vazifalar bazada saqlanmaydi ────────────────────────────────────────
Generatorlar har so'rovda qayta ishlaydi. Bazada (`work_tasks`) faqat xodim
BIR NARSA QILGAN vazifa qatori paydo bo'ladi. Agar generator har safar qator
yozganida, bir necha kunda o'n minglab keraksiz qator to'planardi va
"bir xil to'lov eslatmasi soatiga 5 marta chiqdi" muammosi paydo bo'lardi.

Dublikatga qarshi himoya — deterministik `source_key`:
    payment:student:123:2026-09     (bitta talaba + bitta oy = bitta vazifa)
    absence:student:123:2026-09-02  (bitta talaba + oxirgi qoldirilgan dars)
    lead_callback:lead:88:2026-09-05
Kalit o'zgarmasa, vazifa ham o'zgarmaydi — nechchi marta so'ralishidan qat'i nazar.
"""
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from . import models, tz
from .models import UserRole

# Vazifa turlari (kengaytiriladigan — yangi tur qo'shish uchun generator yozish kifoya)
LEAD_CALL = "LEAD_CALL"
CALLBACK = "CALLBACK"
PARENT_CALL = "PARENT_CALL"
ABSENCE_FOLLOWUP = "ABSENCE_FOLLOWUP"
PAYMENT_REMINDER = "PAYMENT_REMINDER"
STUDENT_FOLLOWUP = "STUDENT_FOLLOWUP"
LEAD_FOLLOWUP = "LEAD_FOLLOWUP"
GENERAL_TASK = "GENERAL_TASK"

TASK_LABELS = {
    LEAD_CALL: "Yangi lid — qo'ng'iroq",
    CALLBACK: "Qayta qo'ng'iroq",
    PARENT_CALL: "Ota-ona bilan bog'lanish",
    ABSENCE_FOLLOWUP: "Davomat bo'yicha follow-up",
    PAYMENT_REMINDER: "To'lov eslatmasi",
    STUDENT_FOLLOWUP: "O'quvchi bo'yicha follow-up",
    LEAD_FOLLOWUP: "Lid bo'yicha follow-up",
    GENERAL_TASK: "Vazifa",
}

PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}

# Ketma-ket qoldirilgan darslar chegaralari. Bittadan ko'p chegara bor,
# chunki 2 ta qoldirish bilan 5 ta qoldirish bir xil shoshilinchlikda emas.
ABSENCE_THRESHOLDS = {5: "critical", 3: "critical", 2: "high"}

# Kechikkan callback qancha "yonayotgani" — kechikish uzunligiga qarab.
# Hammasini "critical" qilish mumkin emas edi: bazada 150+ ta uzoq muddat
# oldin kechikkan callback bor va ular qizil bo'lsa, ro'yxat butunlay
# ma'nosini yo'qotadi — xodim bugun nima muhimligini ajrata olmaydi.
CALLBACK_CRITICAL_DAYS = 2      # 2 kungacha kechikkan — hozir hal qilinadi
CALLBACK_HIGH_DAYS = 14         # 2 haftagacha — hali tirik
                                # undan uzoq — eski qoldiq, "normal"

# Qarz bo'yicha shoshilinchlik — oyning nechanchi kuni ekaniga qarab.
DEBT_CRITICAL_DAY = 15    # oyning yarmi o'tdi, hali to'lanmagan
DEBT_HIGH_DAY = 5

# Vaqt zonasi — yagona manba `backend/tz.py` da (eski nom moslik uchun qoldi).
TASHKENT = tz.OFFSET


def _local_now() -> datetime:
    """Toshkent vaqti (bazada vaqtlar naive UTC saqlanadi)."""
    return tz.now()


def _to_utc(local_dt: datetime) -> datetime:
    return tz.to_utc(local_dt)


class Task:
    """Generator chiqaradigan nomzod vazifa (hali bazada yo'q)."""

    __slots__ = ("source_key", "task_type", "title", "reason", "priority",
                 "due_at", "entity_type", "entity_id", "entity_name", "phone",
                 "phone2", "meta", "assigned_to_id")

    def __init__(self, *, source_key, task_type, title, reason=None, priority="normal",
                 due_at=None, entity_type=None, entity_id=None, entity_name=None,
                 phone=None, phone2=None, meta=None, assigned_to_id=None):
        self.source_key = source_key
        self.task_type = task_type
        self.title = title
        self.reason = reason
        self.priority = priority
        self.due_at = due_at
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.phone = phone
        self.phone2 = phone2
        self.meta = meta or {}
        self.assigned_to_id = assigned_to_id


# ── Generatorlar ────────────────────────────────────────────────────────────

def _callback_priority(due_utc: datetime, now_utc: datetime) -> tuple:
    """Kechikish uzunligiga qarab muhimlik + sabab matni."""
    if due_utc >= now_utc:
        return "high", "Bugun qayta qo'ng'iroq qilinadi"
    days = (now_utc - due_utc).days
    if days <= CALLBACK_CRITICAL_DAYS:
        return "critical", (f"{days} kun kechikdi" if days else "Vaqti o'tib ketdi")
    if days <= CALLBACK_HIGH_DAYS:
        return "high", f"{days} kun kechikdi"
    return "normal", f"{days} kundan beri kechikkan (eski qoldiq)"


def _gen_lead_callbacks(db: Session, now_local: datetime) -> list:
    """Kelish/qayta qo'ng'iroq vaqti kelgan yoki o'tib ketgan lidlar."""
    end_of_day = _to_utc(now_local.replace(hour=23, minute=59, second=59, microsecond=0))
    now_utc = datetime.utcnow()

    closed_ids = {
        s.id for s in db.query(models.LeadStage)
        .filter(models.LeadStage.kind.in_(["won", "lost"])).all()
    }
    q = (
        db.query(models.Lead)
        .options(joinedload(models.Lead.stage))
        .filter(models.Lead.callback_at != None,          # noqa: E711
                models.Lead.callback_at <= end_of_day)
    )
    if closed_ids:
        q = q.filter(~models.Lead.stage_id.in_(closed_ids))

    out = []
    for l in q.all():
        overdue = l.callback_at < now_utc
        local_due = tz.to_local(l.callback_at)
        priority, reason = _callback_priority(l.callback_at, now_utc)
        out.append(Task(
            source_key=f"lead_callback:lead:{l.id}:{local_due.date().isoformat()}",
            task_type=CALLBACK,
            title=l.full_name,
            reason=reason,
            priority=priority,
            due_at=l.callback_at,
            entity_type="lead", entity_id=l.id, entity_name=l.full_name,
            phone=l.phone,
            assigned_to_id=l.claimed_by_id or l.created_by_id,
            meta={"stage": l.stage.name if l.stage else l.status, "overdue": overdue},
        ))
    return out


def _gen_new_leads(db: Session, now_local: datetime) -> list:
    """Hech kim tegmagan yangi lidlar — 2 soatdan beri javobsiz turgan."""
    cutoff = datetime.utcnow() - timedelta(hours=2)
    first_stage = (
        db.query(models.LeadStage)
        .filter(models.LeadStage.is_archived == False,          # noqa: E712
                models.LeadStage.kind == "lead")
        .order_by(models.LeadStage.order.asc()).first()
    )
    if not first_stage:
        return []
    leads = (
        db.query(models.Lead)
        .filter(models.Lead.stage_id == first_stage.id,
                models.Lead.created_at <= cutoff)
        .order_by(models.Lead.created_at.asc())
        .limit(200).all()
    )
    if not leads:
        return []
    # Bosqichi o'zgargan lidlar bu ro'yxatga tushmasligi kerak: birinchi
    # bosqichda turgan bo'lsa ham, kimdir ular bilan ishlagan bo'lishi mumkin.
    ids = [l.id for l in leads]
    touched = {
        r[0] for r in db.query(models.LeadActivity.lead_id)
        .filter(models.LeadActivity.lead_id.in_(ids),
                models.LeadActivity.action.in_(["stage_changed", "note", "call"]))
        .distinct().all()
    }
    out = []
    for l in leads:
        if l.id in touched:
            continue
        age_h = (datetime.utcnow() - l.created_at).total_seconds() / 3600
        out.append(Task(
            source_key=f"lead_new:lead:{l.id}",
            task_type=LEAD_CALL,
            title=l.full_name,
            reason=f"Yangi lid — {int(age_h)} soatdan beri bog'lanilmagan",
            priority="high" if age_h >= 24 else "normal",
            due_at=l.created_at,
            entity_type="lead", entity_id=l.id, entity_name=l.full_name,
            phone=l.phone,
            assigned_to_id=l.claimed_by_id,     # band qilinmagan bo'lsa — umumiy havza
            meta={"source": l.source.name if l.source else None, "age_hours": int(age_h)},
        ))
    return out


def _gen_reminders(db: Session, now_local: datetime) -> list:
    """Mavjud eslatmalar tizimi — qayta ixtiro qilinmaydi, shu yerga qo'shiladi."""
    end_of_day = _to_utc(now_local.replace(hour=23, minute=59, second=59, microsecond=0))
    now_utc = datetime.utcnow()
    rows = (
        db.query(models.Reminder)
        .options(joinedload(models.Reminder.lead))
        .filter(models.Reminder.status == "pending",
                func.coalesce(models.Reminder.snoozed_until, models.Reminder.due_at) <= end_of_day)
        .all()
    )
    out = []
    for r in rows:
        due = r.snoozed_until or r.due_at
        overdue = due < now_utc
        lead = r.lead
        priority, reason = _callback_priority(due, now_utc)
        out.append(Task(
            source_key=f"reminder:{r.id}",
            task_type=CALLBACK,
            title=lead.full_name if lead else "Eslatma",
            reason=r.body or reason,
            priority=priority,
            due_at=due,
            entity_type="lead" if lead else None,
            entity_id=lead.id if lead else None,
            entity_name=lead.full_name if lead else None,
            phone=lead.phone if lead else None,
            assigned_to_id=r.assigned_to_id or r.created_by_id,
            meta={"reminder_id": r.id, "overdue": overdue},
        ))
    return out


def _gen_absences(db: Session, now_local: datetime) -> list:
    """Ketma-ket dars qoldirgan o'quvchilar.

    Yo'qlama `attendance` jadvalida dars sanasi bo'yicha yoziladi. Har talaba
    uchun oxirgi yozuvlardan boshlab teskari yurib, ketma-ket nechta `False`
    borligini sanaymiz — chegaradan oshsa vazifa tug'iladi.
    """
    since = now_local.date() - timedelta(days=45)
    rows = (
        db.query(models.Attendance.student_id, models.Attendance.lesson_date,
                 models.Attendance.is_present, models.Attendance.group_id)
        .filter(models.Attendance.lesson_date >= since)
        .order_by(models.Attendance.student_id, models.Attendance.lesson_date.desc())
        .all()
    )
    streaks = {}
    for sid, ldate, present, gid in rows:
        st = streaks.setdefault(sid, {"n": 0, "last": None, "done": False, "group_id": gid})
        if st["done"]:
            continue
        if present is False:
            st["n"] += 1
            if st["last"] is None:
                st["last"] = ldate
        elif present is True:
            st["done"] = True        # ketma-ketlik uzildi
        # present is None — yo'qlama qilinmagan, hisobga olinmaydi

    hit = {sid: st for sid, st in streaks.items()
           if st["n"] >= min(ABSENCE_THRESHOLDS)}
    if not hit:
        return []

    students = (
        db.query(models.Student)
        .filter(models.Student.id.in_(list(hit)),
                models.Student.is_archived == False,      # noqa: E712
                models.Student.is_active == True)         # noqa: E712
        .all()
    )
    groups = {g.id: g.name for g in db.query(models.Group).all()}
    out = []
    for s in students:
        st = hit[s.id]
        n = st["n"]
        priority = "normal"
        for threshold in sorted(ABSENCE_THRESHOLDS, reverse=True):
            if n >= threshold:
                priority = ABSENCE_THRESHOLDS[threshold]
                break
        out.append(Task(
            source_key=f"absence:student:{s.id}:{st['last'].isoformat()}",
            task_type=ABSENCE_FOLLOWUP,
            title=s.full_name,
            reason=f"{n} ta dars ketma-ket qoldirdi (oxirgi: {st['last'].strftime('%d.%m.%Y')})",
            priority=priority,
            due_at=None,
            entity_type="student", entity_id=s.id, entity_name=s.full_name,
            phone=s.father_phone or s.mother_phone or s.phone1,
            phone2=s.mother_phone if s.father_phone else None,
            meta={"missed": n, "last_absent": st["last"].isoformat(),
                  "group": groups.get(st["group_id"]),
                  "father_phone": s.father_phone, "mother_phone": s.mother_phone},
        ))
    return out


def _gen_debtors(db: Session, now_local: datetime, payment_map_fn) -> list:
    """Joriy oyda qarzi bor talabalar.

    Qarz `_students_payment_map` orqali hisoblanadi — moliya bo'limidagi
    AYNAN o'sha mantiq (ta'til, Special chegirma, avans hammasi hisobga olinadi).
    Bu yerda qayta hisoblash yozilmaydi: ikkita manba ikki xil raqam bersa,
    xodim qaysisiga ishonishni bilmay qolardi.
    """
    month, year = now_local.month, now_local.year
    students = (
        db.query(models.Student)
        .options(joinedload(models.Student.group_memberships)
                 .joinedload(models.GroupStudent.group),
                 joinedload(models.Student.group_memberships)
                 .joinedload(models.GroupStudent.tariff))
        .filter(models.Student.is_archived == False,       # noqa: E712
                models.Student.is_active == True)          # noqa: E712
        .all()
    )
    if not students:
        return []
    pay = payment_map_fn(db, students, month, year)

    day = now_local.day
    if day >= DEBT_CRITICAL_DAY:
        base_priority = "critical"
    elif day >= DEBT_HIGH_DAY:
        base_priority = "high"
    else:
        base_priority = "normal"

    out = []
    for s in students:
        owed, paid, debt, status, _adv = pay.get(s.id, (Decimal(0),) * 5)
        if status not in ("debtor", "partial") or debt <= 0:
            continue
        groups = [m.group.name for m in s.group_memberships
                 if m.group and m.group.is_active and m.left_at is None]
        out.append(Task(
            source_key=f"payment:student:{s.id}:{year}-{month:02d}",
            task_type=PAYMENT_REMINDER,
            title=s.full_name,
            reason=(f"{int(debt):,}".replace(",", " ") + " so'm qarz"
                    + (" (qisman to'langan)" if status == "partial" else "")),
            priority=base_priority,
            due_at=None,
            entity_type="student", entity_id=s.id, entity_name=s.full_name,
            phone=s.father_phone or s.mother_phone or s.phone1,
            phone2=s.mother_phone if s.father_phone else None,
            meta={"debt": int(debt), "owed": int(owed), "paid": int(paid),
                  "status": status, "groups": groups, "period": f"{year}-{month:02d}",
                  "father_phone": s.father_phone, "mother_phone": s.mother_phone},
        ))
    return out


def generate(db: Session, now_local: datetime, payment_map_fn) -> list:
    """Barcha generatorlarni ishga tushiradi va nomzod vazifalarni qaytaradi."""
    tasks = []
    tasks += _gen_lead_callbacks(db, now_local)
    tasks += _gen_reminders(db, now_local)
    tasks += _gen_new_leads(db, now_local)
    tasks += _gen_absences(db, now_local)
    tasks += _gen_debtors(db, now_local, payment_map_fn)

    # Bir xil kalitli nomzod ikki generatordan kelib qolsa — birinchisi qoladi.
    seen, unique = set(), []
    for t in tasks:
        if t.source_key in seen:
            continue
        seen.add(t.source_key)
        unique.append(t)
    return unique


def visible_to(task_assigned_to: Optional[int], actor: models.User,
               entity_type: Optional[str], created_by_id: Optional[int] = None) -> bool:
    """Vazifa shu xodimga ko'rinadimi.

    Qoida mavjud ruxsat modelidan kelib chiqadi:
      * admin       — hammasi;
      * hunter      — o'ziga biriktirilgan + egasiz (umumiy havza);
      * call_center — xuddi shunday;
      * sales       — faqat o'zining lid vazifalari (talaba/moliya emas).
    """
    role = actor.role
    if role == UserRole.admin.value:
        return True
    if role == UserRole.sales.value:
        return entity_type == "lead" and task_assigned_to == actor.id
    if role in (UserRole.hunter.value, UserRole.call_center.value):
        return task_assigned_to is None or task_assigned_to == actor.id
    return False
