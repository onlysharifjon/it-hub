"""Space ↔ CRM o'quv jarayoni: guruh dasturi (metodika) va uy vazifalari.

* Guruh dasturi — CRM `lessons` (guruh bosqichi bo'yicha) + o'tilgan darslar soni (davomatdan).
  Ustoz uchun yozilgan `guide`/`extra_notes` o'quvchiga berilmaydi.
* Uy vazifasi — CRM `homeworks` (ustoz yozadi); o'quvchi javobini shu yerdan topshiradi,
  ustoz CRM'da baholaydi (main.py: /homeworks/{id}/submissions).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from .. import core_calc, models, schemas, tz
from .errors import MinarError
from .models import MinarAccount

ANSWER_MAX = 5000
LINK_MAX = 500
HOMEWORK_LIMIT = 30
LATE_AFTER_DAYS = 7   # muddat ko'rsatilmagan vazifa — dars sanasidan shuncha kun


def active_groups(db: Session, student_id: int) -> list[models.Group]:
    return (
        db.query(models.Group)
        .join(models.GroupStudent, models.GroupStudent.group_id == models.Group.id)
        .filter(models.GroupStudent.student_id == student_id, models.GroupStudent.left_at.is_(None),
                models.Group.is_active.is_(True))
        .order_by(models.GroupStudent.joined_at.desc())
        .all()
    )


# ── Guruh dasturi ───────────────────────────────────────────────────────────

def curriculum(db: Session, acc: MinarAccount) -> dict:
    groups = active_groups(db, acc.student_id)
    if not groups:
        return {"group": None, "lessons": [], "completed": 0, "total": 0}
    g = next((g for g in groups if g.id == acc.active_group_id), groups[0])
    stage = g.stage or "foundation"
    total = g.course.total_lessons if g.course else schemas.STAGE_TOTAL_LESSONS.get(stage, 24)
    completed = core_calc.group_completed_lessons(db, [g.id]).get(g.id, 0)
    rows = db.query(models.Lesson).filter(models.Lesson.category == stage) \
        .order_by(models.Lesson.lesson_number).all()
    homework = {}
    for hw in db.query(models.Homework).filter(models.Homework.group_id == g.id,
                                                models.Homework.lesson_number.isnot(None)) \
            .order_by(models.Homework.lesson_date).all():
        homework[hw.lesson_number] = hw.id          # eng oxirgisi
    lessons = []
    for l in rows:
        status = "done" if l.lesson_number <= completed else "next" if l.lesson_number == completed + 1 else "upcoming"
        lessons.append({"number": l.lesson_number, "title": l.title, "section": l.section,
                        "status": status, "homeworkId": homework.get(l.lesson_number)})
    return {"group": g.name, "stage": stage, "completed": min(completed, total), "total": total,
            "lessons": lessons}


# ── Uy vazifasi ─────────────────────────────────────────────────────────────

def _due(hw: models.Homework):
    return hw.due_date or (hw.lesson_date + timedelta(days=LATE_AFTER_DAYS))


def _homework_dict(hw: models.Homework, sub: Optional[models.HomeworkSubmission]) -> dict:
    status = sub.status if sub else "pending"
    return {
        "id": hw.id, "group": hw.group.name if hw.group else None,
        "lessonNumber": hw.lesson_number, "lessonTitle": hw.lesson_title, "text": hw.text,
        "lessonDate": hw.lesson_date.isoformat(), "dueDate": _due(hw).isoformat(),
        "overdue": status == "pending" and _due(hw) < tz.today(),
        "status": status,
        "answer": sub.answer if sub else None, "link": sub.link if sub else None,
        "submittedAt": tz.isoformat(sub.submitted_at) if sub and sub.submitted_at else None,
        "grade": sub.grade if sub and status == "graded" else None,
        "comment": sub.teacher_comment if sub and status in ("graded", "returned") else None,
        "coins": sub.coins if sub and status == "graded" else 0,
    }


def homework_list(db: Session, acc: MinarAccount, offset: int = 0, status: str = "all") -> list[dict]:
    group_ids = [g.id for g in active_groups(db, acc.student_id)]
    if not group_ids:
        return []
    q = _homework_query(db, acc, group_ids)
    if status != "all":
        q = q.filter(or_(models.HomeworkSubmission.id.is_(None), models.HomeworkSubmission.status.in_(("pending", "returned")))) if status == "pending" else q.filter(models.HomeworkSubmission.status == status)
    hws = q.order_by(models.Homework.lesson_date.desc(), models.Homework.id.desc()).offset(max(0, offset)).limit(HOMEWORK_LIMIT).all()
    subs = {s.homework_id: s for s in db.query(models.HomeworkSubmission).filter(
        models.HomeworkSubmission.student_id == acc.student_id,
        models.HomeworkSubmission.homework_id.in_([h.id for h in hws] or [0])).all()}
    return [_homework_dict(h, subs.get(h.id)) for h in hws]


def _homework_query(db, acc, group_ids):
    return db.query(models.Homework).outerjoin(models.HomeworkSubmission, and_(
        models.HomeworkSubmission.homework_id == models.Homework.id,
        models.HomeworkSubmission.student_id == acc.student_id)).filter(models.Homework.group_id.in_(group_ids))


def pending_count(db: Session, acc: MinarAccount) -> int:
    gids = [g.id for g in active_groups(db, acc.student_id)]
    return _homework_query(db, acc, gids).filter(or_(models.HomeworkSubmission.id.is_(None),
        models.HomeworkSubmission.status.in_(("pending", "returned")))).count()


def _clean_link(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > LINK_MAX:
        raise MinarError(400, "Havola noto‘g‘ri.")
    value = value.strip()
    u = urlparse(value)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise MinarError(400, "Havola http:// yoki https:// bilan boshlanishi kerak.")
    return value


def submit(db: Session, acc: MinarAccount, homework_id: int, payload: dict) -> dict:
    hw = db.query(models.Homework).filter(models.Homework.id == homework_id).first()
    if not hw or hw.group_id not in {g.id for g in active_groups(db, acc.student_id)}:
        raise MinarError(404, "Uy vazifasi topilmadi.")
    from .support import clean_draft
    cleaned = clean_draft(db, acc, payload)
    answer = cleaned["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise MinarError(400, "Javobingni yoz.")
    if len(answer) > ANSWER_MAX:
        raise MinarError(400, f"Javob {ANSWER_MAX} belgidan oshmasin.")
    link = _clean_link(payload.get("link"))
    sub = db.query(models.HomeworkSubmission).filter(
        models.HomeworkSubmission.homework_id == hw.id,
        models.HomeworkSubmission.student_id == acc.student_id).with_for_update().first()
    if sub and sub.status == "graded":
        raise MinarError(409, "Bu vazifa baholangan — javobni o‘zgartirib bo‘lmaydi.")
    now = datetime.utcnow()
    first = not sub or sub.status != "submitted"
    if not sub:
        sub = models.HomeworkSubmission(homework_id=hw.id, student_id=acc.student_id, created_at=now)
        db.add(sub)
    sub.status, sub.answer, sub.link, sub.submitted_at = "submitted", answer.strip(), link, now
    if first and hw.group and hw.group.teacher_id:
        student = db.query(models.Student.full_name).filter(models.Student.id == acc.student_id).scalar()
        db.add(models.Notification(
            user_id=hw.group.teacher_id, notification_type="homework",
            title=f"{student} uy vazifasini topshirdi",
            body=f"{hw.group.name} · {hw.lesson_title or hw.lesson_date.strftime('%d.%m.%Y')}",
            link=f"/groups/{hw.group_id}", is_read=False, created_at=now,
        ))
    from .models import MinarRevision, MinarDraft
    import json
    db.add(MinarRevision(account_id=acc.id,homework_id=hw.id,payload=json.dumps(cleaned),status="submitted"))
    db.query(MinarDraft).filter_by(account_id=acc.id,homework_id=hw.id).delete()
    db.commit()
    return _homework_dict(hw, sub)
