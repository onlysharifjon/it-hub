"""Ota-onaga bildirishnoma yaratish — CRM hodisalaridan chaqiriladi (main.py hooklari).

Bu modul main.py ga bog'liq emas (bir tomonlama import) — circular import bo'lmaydi.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .. import models


def notify_parents_of_student(
    db: Session,
    *,
    student_id: int,
    ntype: str,
    title: str,
    body: str | None = None,
) -> int:
    """Talabaga bog'langan barcha (faol) ota-onalarga bildirishnoma qo'shadi.

    db.add qiladi, commit qilmaydi — chaqiruvchi tranzaksiyaga qo'shiladi.
    Nechta ota-onaga yuborilganini qaytaradi.
    """
    parent_ids = [
        row[0]
        for row in (
            db.query(models.ParentChild.parent_id)
            .join(models.Parent, models.Parent.id == models.ParentChild.parent_id)
            .filter(
                models.ParentChild.student_id == student_id,
                models.Parent.is_active.is_(True),
            )
            .all()
        )
    ]
    now = datetime.utcnow()
    for pid in parent_ids:
        db.add(models.ParentNotification(
            parent_id=pid, student_id=student_id, type=ntype,
            title=title, body=body, created_at=now,
        ))
    return len(parent_ids)
