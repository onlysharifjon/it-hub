import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from config import CRM_DB_URL

# CRM ma'lumotlari (guruhlar/o'quvchilar/to'lovlar) backendning o'z Postgres bazasidan
# to'g'ridan-to'g'ri o'qiladi — backend.models + backend.core_calc orqali. Faqat SELECT
# so'rovlari ishlatiladi, hech qachon session.add/commit/delete chaqirilmaydi.

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # Oxiriga qo'shiladi (eng past ustuvorlik) — repo ildizidagi boshqa modullarni
    # (masalan it-hub/main.py) bot o'zining teng nomdagi modullaridan ustun qo'ymasligi uchun.
    sys.path.append(str(REPO_ROOT))

if CRM_DB_URL:
    os.environ["DATABASE_URL"] = CRM_DB_URL

from backend import core_calc  # noqa: E402
from backend import models as bm  # noqa: E402
from backend.database import SessionLocal  # noqa: E402

ZERO = Decimal("0")


class CRMError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _tashkent_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5)


async def _run(fn, *args):
    try:
        return await asyncio.to_thread(fn, *args)
    except CRMError:
        raise
    except Exception as error:
        raise CRMError(f"Bazaga so'rov yuborib bo'lmadi: {error}") from error


def _group_to_dict(group: "bm.Group") -> dict:
    return {"id": group.id, "name": group.name, "is_active": group.is_active}


def _member_to_dict(gs: "bm.GroupStudent") -> dict | None:
    student = gs.student
    if student is None or not student.is_active or student.is_archived:
        return None
    return {"student_id": student.id, "student_name": student.full_name}


def _sync_get_groups() -> list[dict]:
    with SessionLocal() as db:
        groups = (
            db.query(bm.Group)
            .filter(bm.Group.is_active.is_(True))
            .order_by(bm.Group.name)
            .all()
        )
        return [_group_to_dict(g) for g in groups]


def _sync_get_group_detail(group_id: int) -> dict:
    with SessionLocal() as db:
        group = db.get(bm.Group, group_id)
        if group is None:
            raise CRMError("Guruh topilmadi.", status_code=404)
        members = [_member_to_dict(gs) for gs in group.members]
        return {
            "id": group.id,
            "name": group.name,
            "is_active": group.is_active,
            "schedule": group.schedule or "",
            "members": [m for m in members if m is not None],
        }


def _sync_get_student(student_id: int) -> dict:
    with SessionLocal() as db:
        student = db.get(bm.Student, student_id)
        if student is None:
            raise CRMError("O'quvchi topilmadi.", status_code=404)
        return {
            "id": student.id,
            "full_name": student.full_name,
            "phone1": student.phone1,
        }


def _sync_search_students(query: str, page_size: int) -> list[dict]:
    with SessionLocal() as db:
        like = f"%{query}%"
        students = (
            db.query(bm.Student)
            .filter(bm.Student.full_name.ilike(like))
            .filter(bm.Student.is_archived.is_(False))
            .order_by(bm.Student.full_name)
            .limit(page_size)
            .all()
        )
        results = []
        for student in students:
            group_names = [
                gs.group.name for gs in student.group_memberships if gs.group is not None
            ]
            results.append(
                {"id": student.id, "full_name": student.full_name, "group_names": group_names}
            )
        return results


def _sync_get_students_by_telegram_id(telegram_id: str) -> list[dict]:
    """CRM administratori Student.telegram_user_id maydoniga ota-onaning Telegram ID'sini
    kiritadi — shu maydon orqali qaysi o'quvchi(lar) shu ota-onaga tegishli ekanini topamiz.
    Bitta ID bir nechta o'quvchiga (aka-uka/opa-singil) tegishli bo'lishi mumkin."""
    with SessionLocal() as db:
        students = (
            db.query(bm.Student)
            .filter(bm.Student.telegram_user_id == telegram_id)
            .filter(bm.Student.is_archived.is_(False))
            .all()
        )
        results = []
        for student in students:
            membership = (
                db.query(bm.GroupStudent).filter(bm.GroupStudent.student_id == student.id).first()
            )
            group_id = membership.group_id if membership else 0
            group_name = (membership.group.name if membership and membership.group else "") or ""
            results.append(
                {
                    "id": student.id,
                    "full_name": student.full_name,
                    "group_id": group_id,
                    "group_name": group_name,
                }
            )
        return results


def _sync_get_payment_summary(student_id: int, month: int | None, year: int | None) -> dict:
    now = _tashkent_now()
    month = month or now.month
    year = year or now.year
    with SessionLocal() as db:
        student = db.get(bm.Student, student_id)
        if student is None:
            raise CRMError("O'quvchi topilmadi.", status_code=404)
        memberships = (
            db.query(bm.GroupStudent).filter(bm.GroupStudent.student_id == student_id).all()
        )
        total_owed = ZERO
        total_paid = ZERO
        for membership in memberships:
            total_owed += core_calc.student_month_owed(db, student_id, membership.group_id, month, year)
            total_paid += core_calc.student_month_paid(db, student_id, membership.group_id, month, year)
        advance = Decimal(str(student.advance_balance or 0))
        status = core_calc.payment_status(total_owed, total_paid, advance)
        debt = max(ZERO, total_owed - total_paid - advance)
        return {
            "student_name": student.full_name,
            "month": month,
            "year": year,
            "payment_status": status,
            "total_owed": float(total_owed),
            "total_paid": float(total_paid),
            "debt": float(debt),
        }


async def get_groups() -> list[dict]:
    return await _run(_sync_get_groups)


async def get_group_detail(group_id: int) -> dict:
    return await _run(_sync_get_group_detail, group_id)


async def get_student(student_id: int) -> dict:
    return await _run(_sync_get_student, student_id)


async def search_students(query: str, page_size: int = 20) -> list[dict]:
    """Guruhga bog'liq bo'lmagan holda, ism bo'yicha to'g'ridan-to'g'ri qidirish
    (guruhga hali qo'shilmagan o'quvchilarni ham topish uchun)."""
    return await _run(_sync_search_students, query, min(page_size, 100))


async def get_payment_summary(student_id: int, month: int | None = None, year: int | None = None) -> dict:
    return await _run(_sync_get_payment_summary, student_id, month, year)


async def get_students_by_telegram_id(telegram_id: int) -> list[dict]:
    return await _run(_sync_get_students_by_telegram_id, str(telegram_id))
