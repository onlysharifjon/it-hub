"""Ota-ona API biznes-logikasi. To'lov hisobi core_calc dan (yagona manba).

Barqaror qoidalar (docs/parent-api/README.md da hujjatlangan):
  * Asosiy (primary) guruh — bolaning hozirgi faol a'zoliklari orasida eng birinchi
    qo'shilgani (joined_at, keyin GroupStudent.id bo'yicha). /children va /teacher
    shu qoidani ishlatadi; payment-summary va schedule esa barcha guruhlarni qaytaradi.
  * Hech bir ro'yxat yashirin qisqartirilmaydi (limit yo'q).
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from .. import models, tz, uploads_sign
from ..core_calc import (
    _active_group_ids, active_special_discounts, apply_special_discounts,
    covers_month, group_billable_in,
    student_cumulative_owed, student_month_owed, student_month_paid,
    student_total_paid_all_time,
)
from . import schemas

DAY_SHORT = {1: "Du", 2: "Se", 3: "Chor", 4: "Pay", 5: "Ju", 6: "Sha", 7: "Yak"}

# Guruh.schedule matnidagi so'zlar → hafta kuni raqami (1=Dushanba .. 7=Yakshanba)
_DAY_WORDS = {
    'du': 1, 'dush': 1, 'dushanba': 1,
    'se': 2, 'sesh': 2, 'seshanba': 2,
    'chor': 3, 'cho': 3, 'chorshanba': 3,
    'pay': 4, 'payshanba': 4,
    'ju': 5, 'jum': 5, 'juma': 5,
    'sha': 6, 'shan': 6, 'shanba': 6,
    'yak': 7, 'yakshanba': 7,
}
_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")
NOTIFICATION_TYPES = {"payment", "attendance", "announcement"}
HOMEWORK_STATUSES = {"pending", "submitted", "graded"}

# Matnli jadvaldan (ScheduleSlot kiritilmagan guruh) slot yasashda dars davomiyligi.
import os as _os
DEFAULT_LESSON_MINUTES = int(_os.getenv("PARENT_DEFAULT_LESSON_MINUTES", "120"))
CERT_URL_TTL_SECONDS = int(_os.getenv("PARENT_CERT_URL_TTL_HOURS", "24")) * 3600


# ── Yordamchilar ─────────────────────────────────────────────────────────────

def _to_int(v) -> int:
    return int(Decimal(str(v or 0)).quantize(Decimal("1")))


def _user_name(u: Optional[models.User]) -> str:
    return ((u.full_name or u.username) if u else "") or ""


def hhmm(value: Optional[str]) -> Optional[str]:
    """'9:00' → '09:00'; noto'g'ri qiymat → None."""
    m = _HHMM.match((value or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def _add_minutes(hm: str, minutes: int) -> str:
    h, m = map(int, hm.split(":"))
    total = min(h * 60 + m + minutes, 23 * 60 + 59)
    return f"{total // 60:02d}:{total % 60:02d}"


def phone_e164(phone: Optional[str]) -> str:
    """'+998 90 123 45 67' → '+998901234567'. O'zbek raqami bo'lmasa — '+' va raqamlar."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 9:
        return "+998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return ("+" + digits) if digits and phone.strip().startswith("+") else digits


def telegram_username(value: Optional[str]) -> str:
    """'https://t.me/jasur' / 't.me/jasur' / 'jasur' → '@jasur'."""
    v = (value or "").strip()
    if not v:
        return ""
    v = re.sub(r"^(https?://)?(www\.)?(t|telegram)\.me/", "", v, flags=re.I).strip("/")
    v = v.split("?")[0].lstrip("@")
    return f"@{v}" if re.fullmatch(r"[A-Za-z0-9_]{3,64}", v) else ""


def _weekdays_from_text(schedule: Optional[str]) -> List[int]:
    """'Toq kunlar' / 'Juft kunlar' / 'Du, Chor, Ju' kabi erkin matnni hafta kunlariga aylantiradi."""
    if not schedule:
        return []
    s = schedule.lower()
    if 'toq' in s:
        return [1, 3, 5]   # Du, Chor, Ju
    if 'juft' in s:
        return [2, 4, 6]   # Se, Pay, Shan
    return sorted({_DAY_WORDS[t] for t in re.split(r'[\s,\-/·.]+', s) if t in _DAY_WORDS})


def active_memberships(student: models.Student) -> List[models.GroupStudent]:
    """Hozirgi faol a'zoliklar, barqaror tartibda (birinchisi — asosiy guruh)."""
    rows = [m for m in student.group_memberships if m.group and m.group.is_active and m.left_at is None]
    return sorted(rows, key=lambda m: (m.joined_at or datetime.min, m.id))


def _group_slots(db: Session, group: models.Group) -> List[tuple]:
    """[(day_of_week, start, end, room)] — ScheduleSlot'lardan, bo'lmasa matnli jadvaldan."""
    rows = (
        db.query(models.ScheduleSlot)
        .filter(models.ScheduleSlot.group_id == group.id)
        .order_by(models.ScheduleSlot.day_of_week.asc(), models.ScheduleSlot.start_time.asc())
        .all()
    )
    out = []
    for s in rows:
        start, end = hhmm(s.start_time), hhmm(s.end_time)
        if start and end and 1 <= s.day_of_week <= 7:
            out.append((s.day_of_week, start, end, s.room or None))
    if rows:
        return out
    start = hhmm(group.lesson_time)
    if not start:
        return []          # vaqt noma'lum — HH:mm shartnomasini buzmaslik uchun slot yo'q
    end = _add_minutes(start, DEFAULT_LESSON_MINUTES)
    return [(d, start, end, None) for d in _weekdays_from_text(group.schedule)]


def _schedule_summary(db: Session, group: models.Group) -> str:
    """'Du · Chor · Ju, 14:00' ko'rinishidagi qisqa satr."""
    slots = _group_slots(db, group)
    if not slots:
        return group.schedule or ""
    days = " · ".join(DAY_SHORT[d] for d in sorted({s[0] for s in slots}))
    times = {s[1] for s in slots}
    return f"{days}, {times.pop()}" if len(times) == 1 else days


# ── Farzandlar ───────────────────────────────────────────────────────────────

def _raw_price(m: models.GroupStudent) -> Decimal:
    if m.tariff:
        return Decimal(str(m.tariff.price or 0))
    return Decimal(str(m.group.course_price or 0))


def build_child(db: Session, student: models.Student) -> schemas.ChildRead:
    active = active_memberships(student)
    primary = active[0] if active else None
    g = primary.group if primary else None

    # Oylik tarif — barcha faol guruhlar bo'yicha xom narx; chegirma foizi — joriy oyda
    # amaldagi Special chegirmalar (core_calc qoidasi bilan) xom narxdan necha foiz.
    today = tz.today()
    discounts = active_special_discounts(db, student.id)
    active_ids = _active_group_ids(db, student.id)
    primary_gid = min(active_ids) if active_ids else None
    raw_total = discounted_total = Decimal(0)
    for m in active:
        raw = _raw_price(m)
        raw_total += raw
        discounted_total += apply_special_discounts(
            raw, discounts, m.group_id, today.month, today.year,
            apply_global=(primary_gid is None or primary_gid == m.group_id),
            active_group_ids=active_ids)
    discount_percent = 0
    if raw_total > 0:
        discount_percent = int(round((raw_total - discounted_total) / raw_total * 100))
        discount_percent = max(0, min(100, discount_percent))

    start = None
    if primary:
        joined = tz.to_local(primary.joined_at).date() if primary.joined_at else None
        gstart = g.start_date.date() if g.start_date else None
        start = max(d for d in (joined, gstart) if d) if (joined or gstart) else None

    return schemas.ChildRead(
        id=student.id,
        full_name=student.full_name,
        group_name=g.name if g else "",
        stage=(g.stage or "").capitalize() if g else "",
        teacher_name=_user_name(g.teacher) if g else "",
        schedule=_schedule_summary(db, g) if g else "",
        tariff=_to_int(raw_total),
        start_date=start,
        discount_percent=discount_percent,
        avatar=uploads_sign.public_url(student.photo),
    )


# ── To'lovlar ────────────────────────────────────────────────────────────────

def build_payment_summary(db: Session, student: models.Student, month: int, year: int) -> schemas.ChildPaymentSummary:
    """CRM `GET /students/{id}/payments/summary` bilan bir xil hisob (core_calc):
    groups/total_* — shu oy; debt/advance/status — shu oygacha jamlangan (kumulyativ)."""
    groups: List[schemas.ChildGroupFee] = []
    total_owed = total_paid = Decimal(0)
    for m in student.group_memberships:
        g = m.group
        if not g or not group_billable_in(g, month, year) or not covers_month(m, month, year):
            continue
        owed = student_month_owed(db, student.id, g.id, month, year)
        paid = Decimal(str(student_month_paid(db, student.id, g.id, month, year)))
        total_owed += owed
        total_paid += paid
        groups.append(schemas.ChildGroupFee(
            group_id=g.id, group_name=g.name,
            owed=_to_int(owed), paid=_to_int(paid),
            remaining=_to_int(max(Decimal(0), owed - paid)),
        ))

    cum_owed = student_cumulative_owed(db, student, upto_year=year, upto_month=month)
    cum_paid = student_total_paid_all_time(db, student.id)
    prepaid = Decimal(str(student.advance_balance or 0))
    balance = cum_paid + prepaid - cum_owed          # = core_calc.student_cumulative_balance
    debt = max(Decimal(0), -balance)
    advance_balance = max(Decimal(0), balance)
    # Avans (Student.advance_balance) to'lovlardan keyin qolgan qarzni yopadi.
    advance_applied = min(prepaid, max(Decimal(0), cum_owed - cum_paid)) if prepaid > 0 else Decimal(0)
    if debt <= 0:
        status = "paid"                              # qarz yo'q (to'lov talab qilinmagan davr ham)
    elif cum_paid + prepaid > 0:
        status = "partial"
    else:
        status = "debtor"

    payments = (
        db.query(models.Payment)
        .filter(models.Payment.student_id == student.id)
        .order_by(models.Payment.paid_at.desc(), models.Payment.id.desc())
        .all()
    )
    recent = [
        schemas.ChildPaymentItem(
            amount=_to_int(p.amount), month=p.month, year=p.year, paid_at=p.paid_at,
            recorded_by_name=_user_name(p.recorded_by), notes=p.notes or None,
            group_name=p.group.name if p.group else None,
        )
        for p in payments
    ]
    return schemas.ChildPaymentSummary(
        month=month, year=year,
        total_owed=_to_int(total_owed), total_paid=_to_int(total_paid),
        advance_balance=_to_int(advance_balance), advance_applied=_to_int(advance_applied),
        debt=_to_int(debt), payment_status=status,
        groups=groups, recent_payments=recent,
    )


# ── Davomat ──────────────────────────────────────────────────────────────────

def build_attendance(db: Session, student: models.Student, month: int, year: int) -> schemas.ChildAttendance:
    """Faqat belgilangan (keldi/kelmadi) va bugungacha bo'lgan darslar; har dars alohida yozuv."""
    rows = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.student_id == student.id,
            extract("month", models.Attendance.lesson_date) == month,
            extract("year", models.Attendance.lesson_date) == year,
            models.Attendance.is_present.isnot(None),
            models.Attendance.lesson_date <= tz.today(),
        )
        .order_by(models.Attendance.lesson_date.asc(), models.Attendance.group_id.asc())
        .all()
    )
    names = {g.id: g.name for g in db.query(models.Group).filter(
        models.Group.id.in_({r.group_id for r in rows} or {0})).all()}
    records = [
        schemas.AttendanceRecord(lesson_date=r.lesson_date, is_present=bool(r.is_present),
                                 group_name=names.get(r.group_id))
        for r in rows
    ]
    present = sum(1 for r in rows if r.is_present)
    percent = round(present / len(rows) * 100) if rows else 0
    return schemas.ChildAttendance(percent=percent, records=records)


# ── Jadval ───────────────────────────────────────────────────────────────────

def build_schedule(db: Session, student: models.Student) -> List[schemas.ScheduleSlotRead]:
    out: List[schemas.ScheduleSlotRead] = []
    for m in active_memberships(student):
        g = m.group
        teacher = _user_name(g.teacher)
        for day, start, end, room in _group_slots(db, g):
            out.append(schemas.ScheduleSlotRead(
                day_of_week=day, start_time=start, end_time=end,
                group_name=g.name or "", teacher_name=teacher,
                stage=(g.stage or "").capitalize(), room=room,
            ))
    out.sort(key=lambda x: (x.day_of_week, x.start_time, x.group_name))
    return out


# ── Bildirishnomalar ─────────────────────────────────────────────────────────

def notification_read(n: models.ParentNotification) -> schemas.ParentNotificationRead:
    return schemas.ParentNotificationRead(
        id=n.id, type=n.type if n.type in NOTIFICATION_TYPES else "announcement",
        title=n.title, body=n.body or "", created_at=n.created_at, is_read=n.read_at is not None,
    )


# ── O'quv jarayoni ───────────────────────────────────────────────────────────

def build_grades(db: Session, student: models.Student) -> List[schemas.GradeRead]:
    rows = (
        db.query(models.Grade)
        .filter(models.Grade.student_id == student.id, models.Grade.max_score > 0)
        .order_by(models.Grade.exam_date.desc(), models.Grade.id.desc())
        .all()
    )
    return [
        schemas.GradeRead(subject=g.subject, score=max(0, min(g.score, g.max_score)),
                          max_score=g.max_score, date=g.exam_date)
        for g in rows
    ]


def _local_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=tz.TASHKENT)


def _homework_deadline(h: models.Homework, slots: List[tuple]) -> datetime:
    """due_date bor — o'sha kun 23:59:59 (Toshkent). Yo'q — keyingi dars boshlanishi
    (CRM qoidasi: "bo'sh — keyingi dars"); jadval noma'lum bo'lsa — dars sanasidan 7 kun."""
    if h.due_date:
        return _local_dt(h.due_date, time(23, 59, 59))
    for i in range(1, 8):
        d = h.lesson_date + timedelta(days=i)
        starts = sorted(s[1] for s in slots if s[0] == d.isoweekday())
        if starts:
            hh, mm = map(int, starts[0].split(":"))
            return _local_dt(d, time(hh, mm))
    return _local_dt(h.lesson_date + timedelta(days=7), time(23, 59, 59))


def build_homework(db: Session, student: models.Student) -> List[schemas.HomeworkRead]:
    members = active_memberships(student)
    if not members:
        return []
    joined = {m.group_id: (tz.to_local(m.joined_at).date() if m.joined_at else date.min) for m in members}
    homeworks = [
        h for h in db.query(models.Homework).filter(models.Homework.group_id.in_(list(joined))).all()
        if h.lesson_date >= joined[h.group_id]      # bola qo'shilishidan oldingi vazifalar emas
    ]
    subs = {
        s.homework_id: s
        for s in db.query(models.HomeworkSubmission).filter(
            models.HomeworkSubmission.student_id == student.id,
            models.HomeworkSubmission.homework_id.in_([h.id for h in homeworks] or [0]),
        ).all()
    }
    slots_by_group = {m.group_id: _group_slots(db, m.group) for m in members}
    out: List[schemas.HomeworkRead] = []
    for h in homeworks:
        sub = subs.get(h.id)
        status = (sub.status if sub else "pending") or "pending"
        if status == "done":
            status = "submitted"
        if status not in HOMEWORK_STATUSES:
            status = "pending"
        title = (h.lesson_title or "").strip() or (
            h.text.strip().splitlines()[0][:100] if h.text and h.text.strip() else "Uy vazifasi")
        out.append(schemas.HomeworkRead(
            id=h.id, title=title, due_date=_homework_deadline(h, slots_by_group.get(h.group_id, [])),
            status=status,
        ))
    out.sort(key=lambda x: (x.due_date, x.id))
    return out


def build_feedback(db: Session, student: models.Student) -> List[schemas.FeedbackRead]:
    rows = (
        db.query(models.TeacherFeedback)
        .filter(models.TeacherFeedback.student_id == student.id)
        .order_by(models.TeacherFeedback.created_at.desc(), models.TeacherFeedback.id.desc())
        .all()
    )
    return [
        schemas.FeedbackRead(teacher_name=_user_name(f.teacher) or "O'qituvchi", comment=f.comment,
                             date=tz.to_local(f.created_at).date())
        for f in rows if (f.comment or "").strip()
    ]


def build_teacher(db: Session, student: models.Student) -> Optional[schemas.TeacherContact]:
    """Asosiy guruh o'qituvchisi; u faol bo'lmasa — keyingi faol guruh o'qituvchisi."""
    for m in active_memberships(student):
        t = m.group.teacher
        if t and t.is_active:
            return schemas.TeacherContact(
                name=_user_name(t) or "O'qituvchi",
                phone=phone_e164(t.phone), telegram=telegram_username(t.telegram),
            )
    return None


# ── Sertifikatlar ────────────────────────────────────────────────────────────

def certificate_file_url(cert_id: int) -> str:
    exp, sig = uploads_sign.sign_token(f"cert:{cert_id}", CERT_URL_TTL_SECONDS)
    return (f"{uploads_sign.PUBLIC_BASE_URL}{uploads_sign.PUBLIC_API_PREFIX}"
            f"/parent/certificates/{cert_id}/file?exp={exp}&sig={sig}")


def build_certificates(db: Session, student: models.Student) -> List[schemas.CertificateRead]:
    rows = (
        db.query(models.Certificate)
        .filter(models.Certificate.student_id == student.id)
        .all()
    )
    out = [
        schemas.CertificateRead(
            id=c.id, title=c.title,
            issue_date=c.issued_at or tz.to_local(c.created_at).date(),
            url=certificate_file_url(c.id),
        )
        for c in rows if (c.file_url or "").startswith("https://")
    ]
    out.sort(key=lambda c: (c.issue_date, c.id), reverse=True)
    return out


# ── Qo'shimcha (eski ilova versiyalari) ──────────────────────────────────────

def build_events(db: Session) -> List[schemas.EventRead]:
    rows = (
        db.query(models.Event)
        .filter(models.Event.is_active.is_(True))
        .order_by(models.Event.event_date.desc())
        .all()
    )
    return [
        schemas.EventRead(id=e.id, title=e.title, description=e.description,
                          date=e.event_date, location=e.location)
        for e in rows
    ]


def build_coins(db: Session, student: models.Student) -> schemas.ChildCoins:
    total = int(
        db.query(func.coalesce(func.sum(models.CoinTransaction.amount), 0))
        .filter(models.CoinTransaction.student_id == student.id)
        .scalar()
    )
    rows = (
        db.query(models.CoinTransaction)
        .filter(models.CoinTransaction.student_id == student.id)
        .order_by(models.CoinTransaction.created_at.desc())
        .limit(30)
        .all()
    )
    recent = [
        schemas.CoinItem(amount=t.amount, reason=t.reason,
                         teacher_name=_user_name(t.teacher) or None, date=t.created_at)
        for t in rows
    ]
    return schemas.ChildCoins(total=total, recent=recent)
