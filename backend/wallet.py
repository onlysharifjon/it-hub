"""Single balance and transaction lock shared by CRM, SPACE and parent API."""
from contextlib import contextmanager
from sqlalchemy import func
from . import models


def lock(db, student_id):
    # All spend/reversal paths take this row first; works across API processes.
    return db.query(models.Student).filter(models.Student.id == student_id).with_for_update().first()


def balance(db, student_id):
    from .minar.models import MinarAccount, MinarLedger
    crm = db.query(func.coalesce(func.sum(models.CoinTransaction.amount), 0)).filter(
        models.CoinTransaction.student_id == student_id).scalar()
    space = db.query(func.coalesce(func.sum(MinarLedger.amount), 0)).join(
        MinarAccount, MinarAccount.id == MinarLedger.account_id).filter(
        MinarAccount.student_id == student_id).scalar()
    return int(crm) + int(space)


@contextmanager
def account_transaction(db, acc):
    from .minar.models import MinarAccount
    lock(db, acc.student_id)
    db.query(MinarAccount).filter(MinarAccount.id == acc.id).populate_existing().with_for_update().one()
    try:
        yield
    except Exception:
        db.rollback()
        raise
