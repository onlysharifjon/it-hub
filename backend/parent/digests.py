"""Daily parent reminders, based on existing CRM debt rules and real weekly data."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
import threading
import time

from sqlalchemy.orm import Session

from .. import models, tz, work_center
from ..database import SessionLocal
from .engagement import weekly_summary

log = logging.getLogger("ithub.parent.digests")


def _linked_parents(db: Session, student_id: int) -> list[int]:
    return [pid for (pid,) in db.query(models.ParentChild.parent_id).join(
        models.Parent, models.Parent.id == models.ParentChild.parent_id,
    ).filter(models.ParentChild.student_id == student_id,
             models.Parent.is_active.is_(True)).all()]


def _add_once(db: Session, parent_id: int, student_id: int, ntype: str,
              title: str, body: str) -> bool:
    exists = db.query(models.ParentNotification.id).filter(
        models.ParentNotification.parent_id == parent_id,
        models.ParentNotification.student_id == student_id,
        models.ParentNotification.type == ntype,
        models.ParentNotification.title == title,
        models.ParentNotification.body == body,
    ).first()
    if exists:
        return False
    db.add(models.ParentNotification(
        parent_id=parent_id, student_id=student_id,
        type=ntype, title=title, body=body, created_at=datetime.utcnow(),
    ))
    return True


def run_daily(db: Session, payment_map_fn, *, today=None) -> int:
    """Idempotent. Day 5/15 mirror CRM's high/critical debt follow-up days.

    There is no configured contractual due date in CRM, so the message says
    payment *status* should be checked; it never claims a due date.
    """
    if os.getenv("PARENT_DIGESTS_ENABLED", "false").lower() != "true":
        return 0
    today = today or tz.today()
    count = 0
    if today.day in (work_center.DEBT_HIGH_DAY, work_center.DEBT_CRITICAL_DAY):
        local_now = datetime.combine(today, datetime.min.time())
        for task in work_center._gen_debtors(db, local_now, payment_map_fn):
            body = f"{today:%Y-%m} oyi uchun to'lov holatini tekshiring ({today.day}-kun eslatmasi)."
            for parent_id in _linked_parents(db, task.entity_id):
                count += _add_once(db, parent_id, task.entity_id, "payment",
                                   "Oylik to'lovni tekshiring", body)

    # Previous week is complete on Monday; Tuesday catches a Monday outage.
    if today.weekday() in (0, 1):
        previous_monday = today - timedelta(days=today.weekday() + 7)
        student_ids = {sid for (sid,) in db.query(models.ParentChild.student_id).join(
            models.Parent, models.Parent.id == models.ParentChild.parent_id,
        ).filter(models.Parent.is_active.is_(True)).all()}
        for student in db.query(models.Student).filter(models.Student.id.in_(student_ids or {0})).all():
            summary = weekly_summary(db, student, previous_monday)
            if not (summary.scheduled_lessons or summary.homework_total or
                    summary.average_grade is not None or summary.teacher_recommendation):
                continue
            body = f"{previous_monday:%Y-%m-%d} haftasi bo'yicha xulosa tayyor."
            for parent_id in _linked_parents(db, student.id):
                count += _add_once(db, parent_id, student.id, "weekly_summary",
                                   "Haftalik hisobot tayyor", body)
    db.commit()
    return count


def start_scheduler(payment_map_fn) -> threading.Thread | None:
    if os.getenv("PARENT_DIGESTS_ENABLED", "false").lower() != "true":
        return None

    def loop():
        last_day = None
        while True:
            current = tz.today()
            if current != last_day:
                db = SessionLocal()
                try:
                    run_daily(db, payment_map_fn, today=current)
                    last_day = current
                except Exception:
                    db.rollback()
                    log.exception("Parent daily reminder failed")
                finally:
                    db.close()
            time.sleep(60)

    thread = threading.Thread(target=loop, name="parent-digests", daemon=True)
    thread.start()
    return thread
