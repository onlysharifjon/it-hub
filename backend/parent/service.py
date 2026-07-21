"""Ota-ona API biznes-logikasi. To'lov hisobi core_calc dan (yagona manba)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from .. import models
from ..core_calc import student_month_owed, student_month_paid, payment_status
from . import schemas

DAY_SHORT = {1: "Du", 2: "Se", 3: "Chor", 4: "Pay", 5: "Ju", 6: "Sha", 7: "Yak"}


def _to_int(v) -> int:
    return int(Decimal(str(v or 0)).quantize(Decimal("1")))


def _active_memberships(student: models.Student) -> List[models.GroupStudent]:
    return [m for m in student.group_memberships if m.group and m.group.is_active]


def _schedule_summary(db: Session, group_id: int, fallback: Optional[str]) -> Optional[str]:
    """ScheduleSlot'lardan 'Du · Chor · Ju, 14:00' ko'rinishida satr. Bo'lmasa — matn fallback."""
    slots = (
        db.query(models.ScheduleSlot)
        .filter(models.ScheduleSlot.group_id == group_id)
        .order_by(models.ScheduleSlot.day_of_week.asc())
        .all()
    )
    if not slots:
        return fallback
    days = " · ".join(DAY_SHORT.get(s.day_of_week, "?") for s in slots)
    times = {s.start_time for s in slots}
    time_part = slots[0].start_time if len(times) == 1 else ""
    return f"{days}, {time_part}".strip().rstrip(",") if time_part else days


def build_child(db: Session, student: models.Student) -> schemas.ChildRead:
    active = _active_memberships(student)
    primary = active[0] if active else None
    g = primary.group if primary else None

    # Oylik narx — barcha faol guruhlar bo'yicha (xom narx, chegirmasiz)
    tariff_total = sum((student_month_owed(db, student.id, m.group.id) for m in active), Decimal(0))

    # Chegirmalar tizimi olib tashlangan — har doim 0 (mobil ilova mosligi uchun)
    discount_percent = 0

    start = None
    if g and g.start_date:
        start = g.start_date.date()
    elif primary:
        start = primary.joined_at.date()

    return schemas.ChildRead(
        id=student.id,
        full_name=student.full_name,
        group_name=g.name if g else None,
        stage=g.stage if g else None,
        teacher_name=(g.teacher.full_name or g.teacher.username) if (g and g.teacher) else None,
        schedule=_schedule_summary(db, g.id, g.schedule) if g else None,
        tariff=_to_int(tariff_total),
        start_date=start,
        discount_percent=discount_percent,
        avatar=None,
    )


def build_payment_summary(db: Session, student: models.Student, month: int, year: int) -> schemas.ChildPaymentSummary:
    groups: List[schemas.ChildGroupFee] = []
    total_owed = total_paid = Decimal(0)
    for m in _active_memberships(student):
        g = m.group
        owed = student_month_owed(db, student.id, g.id, month, year)
        paid = student_month_paid(db, student.id, g.id, month, year)
        total_owed += owed
        total_paid += paid
        groups.append(schemas.ChildGroupFee(
            group_id=g.id, group_name=g.name,
            owed=_to_int(owed), paid=_to_int(paid),
            remaining=_to_int(max(Decimal(0), owed - paid)),
        ))

    advance = Decimal(str(student.advance_balance or 0))
    advance_applied = min(advance, max(Decimal(0), total_owed - total_paid))
    debt = max(Decimal(0), total_owed - total_paid - advance)
    status = payment_status(total_owed, total_paid, advance)

    recent = (
        db.query(models.Payment)
        .filter(models.Payment.student_id == student.id)
        .order_by(models.Payment.paid_at.desc())
        .limit(24)
        .all()
    )
    recent_items = [
        schemas.ChildPaymentItem(
            amount=_to_int(p.amount), month=p.month, year=p.year, paid_at=p.paid_at,
            notes=p.notes,
            recorded_by_name=(p.recorded_by.full_name or p.recorded_by.username) if p.recorded_by else None,
            group_name=p.group.name if p.group else None,
        )
        for p in recent
    ]

    return schemas.ChildPaymentSummary(
        month=month, year=year,
        total_owed=_to_int(total_owed), total_paid=_to_int(total_paid),
        advance_balance=_to_int(advance), advance_applied=_to_int(advance_applied),
        debt=_to_int(debt), payment_status=status,
        groups=groups, recent_payments=recent_items,
    )


def build_attendance(db: Session, student: models.Student, month: int, year: int) -> schemas.ChildAttendance:
    from sqlalchemy import extract
    rows = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.student_id == student.id,
            extract("month", models.Attendance.lesson_date) == month,
            extract("year", models.Attendance.lesson_date) == year,
        )
        .order_by(models.Attendance.lesson_date.asc())
        .all()
    )
    group_names = {g.id: g.name for g in db.query(models.Group).all()}
    records = [
        schemas.AttendanceRecord(
            lesson_date=datetime(r.lesson_date.year, r.lesson_date.month, r.lesson_date.day),
            is_present=r.is_present,
            group_name=group_names.get(r.group_id),
        )
        for r in rows
    ]
    total = len(rows)
    present = sum(1 for r in rows if r.is_present)
    percent = round(present / total * 100) if total else 0
    return schemas.ChildAttendance(percent=percent, records=records)


def _user_name(u: Optional[models.User]) -> Optional[str]:
    return (u.full_name or u.username) if u else None


def build_grades(db: Session, student: models.Student) -> List[schemas.GradeRead]:
    rows = (
        db.query(models.Grade)
        .filter(models.Grade.student_id == student.id)
        .order_by(models.Grade.exam_date.desc(), models.Grade.id.desc())
        .limit(100)
        .all()
    )
    return [
        schemas.GradeRead(
            id=g.id, subject=g.subject, score=g.score, max_score=g.max_score,
            exam_type=g.exam_type, date=g.exam_date, comment=g.comment,
            group_name=g.group.name if g.group else None,
        )
        for g in rows
    ]


def build_homework(db: Session, student: models.Student) -> List[schemas.HomeworkRead]:
    group_ids = [m.group.id for m in _active_memberships(student)]
    if not group_ids:
        return []
    homeworks = (
        db.query(models.Homework)
        .filter(models.Homework.group_id.in_(group_ids))
        .order_by(models.Homework.lesson_date.desc(), models.Homework.id.desc())
        .limit(50)
        .all()
    )
    subs = {
        s.homework_id: s
        for s in db.query(models.HomeworkSubmission)
        .filter(
            models.HomeworkSubmission.student_id == student.id,
            models.HomeworkSubmission.homework_id.in_([h.id for h in homeworks] or [0]),
        )
        .all()
    }
    out: List[schemas.HomeworkRead] = []
    for h in homeworks:
        sub = subs.get(h.id)
        title = h.lesson_title or (h.text.strip().splitlines()[0][:100] if h.text else "Uy vazifasi")
        out.append(schemas.HomeworkRead(
            id=h.id, title=title, description=h.text,
            assigned_date=h.lesson_date, due_date=h.due_date,
            status=sub.status if sub else "pending",
            grade=sub.grade if sub else None,
            teacher_comment=sub.teacher_comment if sub else None,
            group_name=h.group.name if h.group else None,
        ))
    return out


def build_feedback(db: Session, student: models.Student) -> List[schemas.FeedbackRead]:
    rows = (
        db.query(models.TeacherFeedback)
        .filter(models.TeacherFeedback.student_id == student.id)
        .order_by(models.TeacherFeedback.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        schemas.FeedbackRead(
            id=f.id,
            teacher_name=_user_name(f.teacher) or "O'qituvchi",
            comment=f.comment, date=f.created_at.date(),
            group_name=f.group.name if f.group else None,
        )
        for f in rows
    ]


def build_teacher(db: Session, student: models.Student) -> Optional[schemas.TeacherContact]:
    """Bolaning asosiy (birinchi faol) guruhi o'qituvchisi kontaktlari."""
    for m in _active_memberships(student):
        t = m.group.teacher
        if t and t.is_active:
            return schemas.TeacherContact(
                name=_user_name(t), phone=t.phone, telegram=t.telegram,
                group_name=m.group.name, avatar=t.avatar,
            )
    return None


def build_certificates(db: Session, student: models.Student) -> List[schemas.CertificateRead]:
    rows = (
        db.query(models.Certificate)
        .filter(models.Certificate.student_id == student.id)
        .order_by(models.Certificate.issued_at.desc().nullslast(), models.Certificate.id.desc())
        .all()
    )
    return [
        schemas.CertificateRead(id=c.id, title=c.title, file_url=c.file_url, issued_at=c.issued_at)
        for c in rows
    ]


def build_events(db: Session) -> List[schemas.EventRead]:
    rows = (
        db.query(models.Event)
        .filter(models.Event.is_active.is_(True))
        .order_by(models.Event.event_date.desc())
        .limit(50)
        .all()
    )
    return [
        schemas.EventRead(
            id=e.id, title=e.title, description=e.description,
            date=e.event_date, location=e.location,
        )
        for e in rows
    ]


def build_schedule(db: Session, student: models.Student) -> List[schemas.ScheduleSlotRead]:
    out: List[schemas.ScheduleSlotRead] = []
    for m in _active_memberships(student):
        g = m.group
        slots = (
            db.query(models.ScheduleSlot)
            .filter(models.ScheduleSlot.group_id == g.id)
            .order_by(models.ScheduleSlot.day_of_week.asc(), models.ScheduleSlot.start_time.asc())
            .all()
        )
        teacher = (g.teacher.full_name or g.teacher.username) if g.teacher else None
        for s in slots:
            out.append(schemas.ScheduleSlotRead(
                day_of_week=s.day_of_week, start_time=s.start_time, end_time=s.end_time,
                group_name=g.name, teacher_name=teacher, stage=g.stage, room=s.room,
            ))
    out.sort(key=lambda x: (x.day_of_week, x.start_time))
    return out


def build_coins(db: Session, student: models.Student) -> schemas.ChildCoins:
    from sqlalchemy import func
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
        schemas.CoinItem(
            amount=t.amount, reason=t.reason,
            teacher_name=(t.teacher.full_name or t.teacher.username) if t.teacher else None,
            date=t.created_at,
        )
        for t in rows
    ]
    return schemas.ChildCoins(total=total, recent=recent)
