"""Calendar-month academic coin allowances, shared by CRM and Space.

Positive grants consume the allowance; spending and reversals never refill it.
Writers lock actor, group, then students in ID order to serialize all grants.
"""
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from fastapi import HTTPException
from . import models, tz

MONTHLY_COINS = 70


def coin_title(reason, amount):
    if reason and reason.startswith('Davomat:'):
        day = reason.rsplit(':', 1)[-1]
        return f"Davomat uchun coin · {day}" if amount > 0 else f"Davomat coini qaytarildi · {day}"
    return reason or ('O‘qituvchi mukofoti' if amount > 0 else 'Coin yechildi')


def positive(column):
    return func.coalesce(func.sum(case((column > 0, column), else_=0)), 0)


def month_query(db):
    now = tz.now()
    start, end = tz.month_bounds(now.year, now.month)
    return db.query(models.CoinTransaction).filter(
        models.CoinTransaction.created_at >= start, models.CoinTransaction.created_at < end)


def student_usage(db, student_ids):
    """Read all wallets in two aggregate queries, including previous Space grants."""
    from .minar.models import MinarAccount, MinarLedger
    if not student_ids:
        return {}
    now = tz.now()
    start, end = tz.month_bounds(now.year, now.month)
    crm = dict(month_query(db).filter(models.CoinTransaction.student_id.in_(student_ids))
               .with_entities(models.CoinTransaction.student_id, positive(models.CoinTransaction.amount))
               .group_by(models.CoinTransaction.student_id).all())
    legacy = dict(db.query(MinarAccount.student_id, positive(MinarLedger.amount)).join(MinarLedger)
                  .filter(MinarAccount.student_id.in_(student_ids), MinarLedger.created_at >= start,
                          MinarLedger.created_at < end, MinarLedger.kind != 'refund')
                  .group_by(MinarAccount.student_id).all())
    return {sid: int(crm.get(sid, 0)) + int(legacy.get(sid, 0)) for sid in student_ids}


def student_used(db, student_id):
    return student_usage(db, [student_id])[student_id]


def group_students(db, group_id):
    return db.query(models.GroupStudent.student_id).join(models.Student).filter(
        models.GroupStudent.group_id == group_id, models.GroupStudent.left_at.is_(None),
        models.Student.is_active.is_(True), models.Student.is_archived.is_(False)).distinct()


def teacher_budget(db, teacher_id):
    count = db.query(models.GroupStudent.student_id).join(models.Group).join(models.Student).filter(
        models.Group.teacher_id == teacher_id, models.Group.is_active.is_(True),
        models.GroupStudent.left_at.is_(None), models.Student.is_active.is_(True),
        models.Student.is_archived.is_(False)).distinct().count()
    return count * MONTHLY_COINS


def teacher_used(db, teacher_id):
    return int(month_query(db).filter(models.CoinTransaction.teacher_id == teacher_id)
               .with_entities(positive(models.CoinTransaction.amount)).scalar() or 0)


def lock_grant_scope(db, actor, group_id, *, active=True):
    db.query(models.User).filter_by(id=actor.id).with_for_update().one()
    if not group_id:
        raise HTTPException(400, 'Coin uchun guruh tanlang.')
    group = db.query(models.Group).filter_by(id=group_id).populate_existing().with_for_update().first()
    if not group or (active and not group.is_active):
        raise HTTPException(400, 'Faol guruh topilmadi.')
    if actor.role == 'teacher' and group.teacher_id != actor.id:
        raise HTTPException(403, 'Bu guruh sizga tegishli emas.')
    return group


def lock_students(db, student_ids):
    return db.query(models.Student).filter(models.Student.id.in_(student_ids)).order_by(
        models.Student.id).populate_existing().with_for_update().all()


def validate_grant(db, actor, student_id, group_id, amount):
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
        raise HTTPException(400, 'Coin musbat butun son bo‘lishi kerak.')
    lock_grant_scope(db, actor, group_id)
    lock_students(db, [student_id])
    if not group_students(db, group_id).filter(models.GroupStudent.student_id == student_id).first():
        raise HTTPException(400, 'O‘quvchi faol guruh a’zosi emas.')
    remaining = MONTHLY_COINS - student_used(db, student_id)
    if amount > remaining:
        raise HTTPException(400, f'O‘quvchining oylik limiti 70 coin. Qoldiq: {max(0, remaining)}.')
    budget = group_students(db, group_id).count() * MONTHLY_COINS
    used = month_query(db).filter(models.CoinTransaction.group_id == group_id).with_entities(
        positive(models.CoinTransaction.amount)).scalar()
    if amount > budget - int(used or 0):
        raise HTTPException(400, 'Guruhning oylik coin limiti tugagan.')
    if actor.role == 'teacher':
        remaining = teacher_budget(db, actor.id) - teacher_used(db, actor.id)
        if amount > remaining:
            raise HTTPException(400, f'O‘qituvchining oylik coin limiti tugagan. Qoldiq: {max(0, remaining)}.')


def attendance_grant(db, actor, group_id, student_id, day, present):
    """One coin per present lesson; repeated saves cannot mint extra currency."""
    key = f'Davomat:{group_id}:{student_id}:{day.isoformat()}'
    lock_grant_scope(db, actor, group_id, active=present is True)
    lock_students(db, [student_id])
    rows = db.query(models.CoinTransaction).filter_by(student_id=student_id, reason=key).all()
    net = sum(r.amount for r in rows)
    if present is True and not net:
        today = tz.today()
        if day > today or (day.year, day.month) != (today.year, today.month):
            return
        # Attendance remains editable when any monetary allowance is exhausted.
        if student_used(db, student_id) >= MONTHLY_COINS:
            return
        if actor.role == 'teacher' and teacher_used(db, actor.id) >= teacher_budget(db, actor.id):
            return
        group_used = int(month_query(db).filter_by(group_id=group_id)
                         .with_entities(positive(models.CoinTransaction.amount)).scalar() or 0)
        if group_used >= group_students(db, group_id).count() * MONTHLY_COINS:
            return
        validate_grant(db, actor, student_id, group_id, 1)
        db.add(models.CoinTransaction(student_id=student_id, teacher_id=actor.id,
                                     group_id=group_id, amount=1, reason=key))
    elif present is not True and net > 0:
        from .wallet import balance
        if balance(db, student_id) < net:
            raise HTTPException(409, 'Davomat coini sarflangan. Avval balansni tuzating.')
        db.add(models.CoinTransaction(student_id=student_id, teacher_id=actor.id,
                                     group_id=group_id, amount=-net, reason=key))
    db.flush()


def budgets(db, actor):
    """Scoped, batched overview. Group allocations share the student's single cap."""
    q = db.query(models.Group).options(joinedload(models.Group.teacher)).filter(models.Group.is_active.is_(True))
    if actor.role == 'teacher':
        q = q.filter(models.Group.teacher_id == actor.id)
    groups = q.order_by(models.Group.teacher_id, models.Group.name, models.Group.id).all()
    if not groups:
        return []
    members = db.query(models.GroupStudent.group_id, models.Student.id, models.Student.full_name).join(
        models.Student).filter(models.GroupStudent.group_id.in_([g.id for g in groups]),
                               models.GroupStudent.left_at.is_(None), models.Student.is_active.is_(True),
                               models.Student.is_archived.is_(False)).distinct().order_by(models.Student.full_name).all()
    usage = student_usage(db, list({sid for _, sid, _ in members}))
    group_used = dict(month_query(db).with_entities(models.CoinTransaction.group_id, positive(models.CoinTransaction.amount))
                      .group_by(models.CoinTransaction.group_id).all())
    teacher_spent = dict(month_query(db).with_entities(models.CoinTransaction.teacher_id, positive(models.CoinTransaction.amount))
                         .group_by(models.CoinTransaction.teacher_id).all())
    by_group = {g.id: [] for g in groups}
    by_teacher = {}
    group_owners = {g.id: g.teacher_id for g in groups}
    for gid, sid, name in members:
        by_group[gid].append({'id': sid, 'name': name, 'limit': MONTHLY_COINS,
                             'used': usage[sid], 'remaining': max(0, MONTHLY_COINS - usage[sid])})
        by_teacher.setdefault(group_owners[gid], set()).add(sid)
    now = tz.now()
    result = []
    for group in groups:
        students = by_group[group.id]
        budget = len(students) * MONTHLY_COINS
        used = int(group_used.get(group.id, 0))
        remaining = max(0, budget - used)
        ids = by_teacher.get(group.teacher_id, set())
        teacher_limit = len(ids) * MONTHLY_COINS
        spent = int(teacher_spent.get(group.teacher_id, 0))
        teacher_remaining = max(0, teacher_limit - spent)
        available = min(remaining, sum(s['remaining'] for s in students))
        if actor.role == 'teacher':
            available = min(available, teacher_remaining)
        result.append({'id': group.id, 'name': group.name, 'budget': budget, 'used': used,
                       'remaining': remaining, 'available': available, 'students': students,
                       'month': now.month, 'year': now.year, 'per_student': MONTHLY_COINS,
                       'teacher_id': group.teacher_id,
                       'teacher_name': (group.teacher.full_name or group.teacher.username) if group.teacher else 'O‘qituvchi biriktirilmagan',
                       'teacher_budget': teacher_limit, 'teacher_used': spent,
                       'teacher_remaining': teacher_remaining, 'teacher_students': len(ids),
                       'teacher_available': min(teacher_remaining, sum(max(0, MONTHLY_COINS - usage[s]) for s in ids))})
    return result
