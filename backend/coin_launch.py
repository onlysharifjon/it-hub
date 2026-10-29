"""Coin balances restart at an audited epoch; XP and purchase history survive."""
import json
from datetime import datetime
from sqlalchemy import text, func
from . import models

# Monday, 2 November 2026 at 00:00 Asia/Tashkent (UTC+05:00).
LAUNCH_AT = datetime(2026, 11, 1, 19)
TEST_LABEL = 'Test coinlari — dushanbagacha'


def utcnow():
    return datetime.utcnow()


def active_since(db, *, now=None):
    config = db.get(models.CoinLaunch, 1)
    if config is None:
        return None
    now = now or utcnow()
    if now >= config.launch_at and not config.keep_test_coins:
        return max(config.reset_at, config.launch_at)
    return config.reset_at


def scope(db, query, model, *, now=None):
    cutoff = active_since(db, now=now)
    return query.filter(model.created_at >= cutoff) if cutoff else query


def phase(db, *, now=None):
    now = now or utcnow()
    config = db.get(models.CoinLaunch, 1)
    test = config is not None and now < config.launch_at
    return {'configured': config is not None, 'testMode': test,
            'startsAt': (config.launch_at if config else LAUNCH_AT).isoformat() + 'Z',
            'serverTime': now.isoformat() + 'Z',
            'resetAt': config.reset_at.isoformat() + 'Z' if config else None,
            'keepsTestCoins': config.keep_test_coins if config else None,
            'label': TEST_LABEL if test else 'Coinlar'}


def reset_all(db, *, keep_test_coins):
    """CLI/deploy only. Caller commits. Single transaction, idempotent, never re-zero on retry."""
    if type(keep_test_coins) is not bool:
        raise ValueError('An explicit test-coin retention choice is required')
    if db.bind.dialect.name == 'postgresql':
        # Deploy stops old application writers first. These locks also protect
        # against an accidentally concurrent reset or another balance writer.
        db.execute(text('LOCK TABLE students, coin_transactions, minar_accounts, minar_ledger, coin_launch IN EXCLUSIVE MODE'))
    existing = db.get(models.CoinLaunch, 1)
    if existing:
        if existing.keep_test_coins != keep_test_coins or existing.launch_at != LAUNCH_AT:
            raise ValueError('A different coin restart is already recorded')
        return phase(db)
    if utcnow() >= LAUNCH_AT:
        raise ValueError('The requested launch time has passed. Review before resetting live coins.')
    from .minar.models import MinarAccount, MinarLedger
    students = db.query(models.Student.id).order_by(models.Student.id).all()
    crm = dict(db.query(models.CoinTransaction.student_id, func.sum(models.CoinTransaction.amount)).group_by(models.CoinTransaction.student_id).all())
    space = dict(db.query(MinarAccount.student_id, func.sum(MinarLedger.amount)).join(
        MinarLedger, MinarLedger.account_id == MinarAccount.id).group_by(MinarAccount.student_id).all())
    snapshot = {str(sid): int(crm.get(sid, 0)) + int(space.get(sid, 0)) for sid, in students}
    config = models.CoinLaunch(id=1, reset_at=utcnow(), launch_at=LAUNCH_AT,
                              keep_test_coins=keep_test_coins,
                              balance_snapshot=json.dumps(snapshot, sort_keys=True))
    db.add(config)
    db.flush()
    return {**phase(db), 'students': len(snapshot), 'previousTotal': sum(snapshot.values())}
