"""O'quvchi bildirishnomalari: yozish (CRM va Space amallaridan) va o'qish.

Yozuvchi funksiyalar commit qilmaydi — chaqiruvchi tranzaksiyasining bir qismi bo'ladi.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from .. import tz
from .errors import MinarError
from .models import MinarAccount, MinarNotification

KEEP = 100          # har o'quvchi uchun saqlanadigan oxirgi bildirishnomalar
LIST_LIMIT = 50


def to_account(db: Session, account_id: int, kind: str, title: str,
               body: Optional[str] = None, link: Optional[str] = None) -> None:
    db.add(MinarNotification(account_id=account_id, kind=kind, title=title[:200], body=body,
                             link=link, created_at=datetime.utcnow()))


def to_student(db: Session, student_id: int, kind: str, title: str,
               body: Optional[str] = None, link: Optional[str] = None) -> bool:
    """Talabaning Minar akkaunti bo'lsa bildirishnoma qo'shadi (bo'lmasa — jimgina o'tadi)."""
    acc_id = db.query(MinarAccount.id).filter(MinarAccount.student_id == student_id,
                                              MinarAccount.is_active.is_(True)).scalar()
    if acc_id is None:
        return False
    to_account(db, acc_id, kind, title, body, link)
    return True


def unread_count(db: Session, acc: MinarAccount) -> int:
    return db.query(MinarNotification.id).filter(MinarNotification.account_id == acc.id,
                                                 MinarNotification.read_at.is_(None)).count()


def _dict(n: MinarNotification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
            "time": tz.isoformat(n.created_at), "read": n.read_at is not None}


def list_for(db: Session, acc: MinarAccount) -> dict:
    rows = db.query(MinarNotification).filter(MinarNotification.account_id == acc.id) \
        .order_by(MinarNotification.created_at.desc(), MinarNotification.id.desc()).limit(KEEP + 1).all()
    if len(rows) > KEEP:   # eskilarini tozalash (ro'yxat ochilganda — yozish yo'lini sekinlashtirmaydi)
        db.query(MinarNotification).filter(MinarNotification.account_id == acc.id,
                                           MinarNotification.id < rows[KEEP - 1].id).delete()
        db.commit()
    return {"items": [_dict(n) for n in rows[:LIST_LIMIT]], "unread": unread_count(db, acc)}


def mark_read(db: Session, acc: MinarAccount, ids: Any) -> dict:
    q = db.query(MinarNotification).filter(MinarNotification.account_id == acc.id,
                                           MinarNotification.read_at.is_(None))
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > 200 or not all(isinstance(i, int) and not isinstance(i, bool)
                                                                  for i in ids):
            raise MinarError(400, "Bildirishnoma topilmadi.")
        q = q.filter(MinarNotification.id.in_(ids or [0]))
    q.update({MinarNotification.read_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return {"unread": unread_count(db, acc)}
