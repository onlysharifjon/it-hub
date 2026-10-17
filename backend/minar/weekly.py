"""Haftalik jarayonlar: turnir (guruh ichida XP poygasi) va ota-onaga haftalik hisobot.

Hafta — Toshkent vaqti bilan dushanba 00:00 dan yakshanba 24:00 gacha.
Ochko — hafta davomida olingan XP: o'yinlar (`minar_results.xp`), mini-darslar
(`minar_lessons`, LESSON_XP) va kod maydoni (`minar_playground_solves.xp`).

`run_due(db)` idempotent (minar_job_runs kaliti bo'yicha) — worker uni muntazam chaqiradi:
o'tgan hafta yakunlanmagan bo'lsa g'oliblarni mukofotlaydi va ota-onalarga hisobot yuboradi.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, tz
from ..parent.notifications import notify_parents_of_student
from . import catalog as C
from . import achievements, notify
from .models import (
    MinarProgress, MinarAccount, MinarJobRun, MinarLedger, MinarLesson, MinarPlaygroundSolve, MinarResult, MinarTournamentAward,
)
from .service import public_name

log = logging.getLogger("ithub.minar.weekly")

FIRST_WEEK = date(2026, 9, 28)   # turnir va hisobotlar shu haftadan boshlab (oldingi haftalar mukofotlanmaydi)
PRIZES = (50, 30, 20)         # guruhdagi 1-, 2-, 3-o'rin (coin)
MIN_POINTS = 50               # mukofot uchun haftalik minimal ochko
OVERALL_LIMIT = 20


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _bounds(start: date) -> tuple[datetime, datetime]:
    return tz.range_bounds(start, start + timedelta(days=6))


# ── Ochkolar ────────────────────────────────────────────────────────────────

def _eligible_accounts(db: Session) -> dict[int, tuple[MinarAccount, models.Student]]:
    rows = (
        db.query(MinarAccount, models.Student)
        .join(models.Student, models.Student.id == MinarAccount.student_id)
        .filter(MinarAccount.is_active.is_(True), MinarAccount.is_test.is_(False),
                models.Student.is_active.is_(True), models.Student.is_archived.is_(False))
        .all()
    )
    return {acc.id: (acc, st) for acc, st in rows}


def points(db: Session, start: date, account_ids: list[int]) -> dict[int, int]:
    """Hafta davomida olingan XP: {account_id: ochko}."""
    lo, hi = _bounds(start)
    ids = list(account_ids) or [0]
    queries = (
        db.query(MinarProgress.account_id,func.count(MinarProgress.id)*30).filter(MinarProgress.account_id.in_(ids),MinarProgress.completed_at>=lo,MinarProgress.completed_at<hi).group_by(MinarProgress.account_id),
        db.query(MinarResult.account_id, func.sum(MinarResult.xp))
        .filter(MinarResult.account_id.in_(ids), MinarResult.created_at >= lo, MinarResult.created_at < hi)
        .group_by(MinarResult.account_id),
        db.query(MinarLesson.account_id, func.count(MinarLesson.id) * C.LESSON_XP)
        .filter(MinarLesson.account_id.in_(ids), MinarLesson.completed_at >= lo, MinarLesson.completed_at < hi)
        .group_by(MinarLesson.account_id),
        db.query(MinarPlaygroundSolve.account_id, func.sum(MinarPlaygroundSolve.xp))
        .filter(MinarPlaygroundSolve.account_id.in_(ids), MinarPlaygroundSolve.solved_at >= lo,
                MinarPlaygroundSolve.solved_at < hi)
        .group_by(MinarPlaygroundSolve.account_id),
    )
    out: dict[int, int] = defaultdict(int)
    for q in queries:
        for aid, v in q.all():
            out[aid] += int(v or 0)
    return dict(out)


def _group_of(db: Session, student_ids: list[int]) -> dict[int, models.Group]:
    """Talaba -> hozirgi (eng oxirgi qo'shilgan) faol guruhi."""
    rows = (
        db.query(models.GroupStudent.student_id, models.Group)
        .join(models.Group, models.Group.id == models.GroupStudent.group_id)
        .filter(models.GroupStudent.student_id.in_(student_ids or [0]), models.GroupStudent.left_at.is_(None),
                models.Group.is_active.is_(True))
        .order_by(models.GroupStudent.joined_at)
        .all()
    )
    return {sid: g for sid, g in rows}


def _row(acc: MinarAccount, st: models.Student, pts: int, me: MinarAccount) -> dict:
    return {"id": acc.login_id, "name": public_name(st.full_name), "avatar": C.CHARACTER_EMOJI.get(acc.character, "🤖"),
            "points": pts, "me": acc.id == me.id, "accountOrder": acc.id}


def _rank(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda r: (-r["points"], r.get("accountOrder", r["id"])))
    for i, r in enumerate(rows):
        r["place"] = i + 1
    return rows


def standings(db: Session, me: MinarAccount) -> dict:
    today = tz.today()
    start = week_start(today)
    accounts = _eligible_accounts(db)
    pts = points(db, start, list(accounts))
    groups = _group_of(db, [st.id for _, st in accounts.values()])
    my_group = groups.get(me.student_id)

    group_rows = []
    if my_group:
        for aid, (acc, st) in accounts.items():
            if groups.get(st.id) and groups[st.id].id == my_group.id:
                group_rows.append(_row(acc, st, pts.get(aid, 0), me))
    overall = _rank([_row(acc, st, pts.get(aid, 0), me) for aid, (acc, st) in accounts.items() if pts.get(aid)])
    top = overall[:OVERALL_LIMIT]
    if not any(r["me"] for r in top):
        top += [r for r in overall if r["me"]]

    last = db.query(MinarTournamentAward).filter(MinarTournamentAward.account_id == me.id) \
        .order_by(MinarTournamentAward.week_start.desc()).first()
    end_local = datetime(start.year, start.month, start.day) + timedelta(days=7)
    return {
        "week": {"start": start.isoformat(), "end": (start + timedelta(days=6)).isoformat(),
                 "endsAt": tz.isoformat(end_local - tz.OFFSET)},
        "levelCohort": {"name":f"{C.level_of(me.xp)}-darajaga yaqin", "standings":_rank([_row(acc,st,pts.get(aid,0),me) for aid,(acc,st) in accounts.items() if abs(C.level_of(acc.xp)-C.level_of(me.xp))<=2])[:50]},
        "ageCohort": {"name":f"{me.age_band} yosh", "standings":_rank([_row(acc,st,pts.get(aid,0),me) for aid,(acc,st) in accounts.items() if acc.age_band==me.age_band])[:50]} if me.age_band else None,
        "prizes": list(PRIZES), "minPoints": MIN_POINTS,
        "myPoints": pts.get(me.id, 0),
        "group": {"name": my_group.name, "standings": _rank(group_rows)} if my_group else None,
        "overall": top,
        "lastAward": {"week": last.week_start, "place": last.place, "coins": last.coins, "group": last.group_name}
        if last else None,
    }


# ── Haftani yakunlash ───────────────────────────────────────────────────────

def _claim(db: Session, key: str) -> bool:
    """Ish bajarilmagan bo'lsa band qiladi (bir nechta worker/qayta ishga tushish xavfsiz)."""
    if db.query(MinarJobRun.key).filter(MinarJobRun.key == key).first():
        return False
    db.add(MinarJobRun(key=key, done_at=datetime.utcnow()))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True


def finalize_week(db: Session, start: date) -> int:
    """Guruhlar bo'yicha 1–3-o'rinlarni mukofotlaydi. Nechta mukofot berilganini qaytaradi."""
    if not _claim(db, f"tournament:{start.isoformat()}"):
        return 0
    accounts = _eligible_accounts(db)
    pts = points(db, start, list(accounts))
    groups = _group_of(db, [st.id for _, st in accounts.values()])
    by_group: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for aid, (acc, st) in accounts.items():
        g = groups.get(st.id)
        if g and pts.get(aid, 0) >= MIN_POINTS:
            by_group[g.id].append((pts[aid], aid))
    now, today = datetime.utcnow(), tz.today().isoformat()
    given = 0
    for gid, rows in by_group.items():
        rows.sort(key=lambda r: (-r[0], r[1]))
        for place, (p, aid) in enumerate(rows[:len(PRIZES)], start=1):
            acc, st = accounts[aid]
            coins = PRIZES[place - 1]
            gname = groups[st.id].name
            db.add(MinarTournamentAward(week_start=start.isoformat(), account_id=aid, group_id=gid,
                                        group_name=gname, place=place, points=p, coins=coins, created_at=now))
            db.add(MinarLedger(account_id=aid, ref_key=f"tournament:{start.isoformat()}", kind="tournament",
                               title=f"Haftalik turnir: {place}-o‘rin", amount=coins, local_date=today,
                               created_at=now))
            notify.to_account(db, aid, "tournament", f"Haftalik turnirda {place}-o‘rin! 🏆",
                              f"{gname} guruhida {p} ochko. +{coins} coin.", "tournament")
            db.flush()
            achievements.evaluate(db, acc)
            given += 1
    db.commit()
    log.info("Turnir %s yakunlandi: %d ta mukofot", start, given)
    return given


# ── Ota-onaga haftalik hisobot ──────────────────────────────────────────────

def _report_body(db: Session, acc: MinarAccount, st: models.Student, start: date, pts: int) -> str:
    lo, hi = _bounds(start)
    games = db.query(func.count(MinarResult.id)).filter(
        MinarResult.account_id == acc.id, MinarResult.created_at >= lo, MinarResult.created_at < hi).scalar() or 0
    code = db.query(func.count(MinarPlaygroundSolve.id)).filter(
        MinarPlaygroundSolve.account_id == acc.id, MinarPlaygroundSolve.solved_at >= lo,
        MinarPlaygroundSolve.solved_at < hi).scalar() or 0
    coins = (db.query(func.coalesce(func.sum(MinarLedger.amount), 0)).filter(
        MinarLedger.account_id == acc.id, MinarLedger.amount > 0,
        MinarLedger.local_date >= start.isoformat(),
        MinarLedger.local_date <= (start + timedelta(days=6)).isoformat()).scalar() or 0) + \
        (db.query(func.coalesce(func.sum(models.CoinTransaction.amount), 0)).filter(
            models.CoinTransaction.student_id == st.id, models.CoinTransaction.amount > 0,
            models.CoinTransaction.created_at >= lo, models.CoinTransaction.created_at < hi).scalar() or 0)
    homework = db.query(func.count(models.HomeworkSubmission.id)).filter(
        models.HomeworkSubmission.student_id == st.id, models.HomeworkSubmission.submitted_at >= lo,
        models.HomeworkSubmission.submitted_at < hi).scalar() or 0
    att = db.query(models.Attendance.is_present).filter(
        models.Attendance.student_id == st.id, models.Attendance.is_present.isnot(None),
        models.Attendance.lesson_date >= start, models.Attendance.lesson_date <= start + timedelta(days=6)).all()
    present = sum(1 for (p,) in att if p)
    lines = [
        f"📅 {start.strftime('%d.%m')}–{(start + timedelta(days=6)).strftime('%d.%m.%Y')}",
        f"🏫 Davomat: {present}/{len(att)} dars" if att else "🏫 Bu hafta dars qayd etilmagan",
        f"📝 Topshirilgan uy vazifalari: {homework}",
        f"🎮 O‘yinlar: {games} ta · 💻 Kod topshiriqlari: {code} ta",
        f"⭐ Haftalik ochko (XP): {pts} · 🪙 Yig‘ilgan coin: {int(coins)}",
    ]
    from .models import MinarProgress
    learned = db.query(func.count(MinarProgress.id)).filter(MinarProgress.account_id==acc.id,
        MinarProgress.completed_at>=lo, MinarProgress.completed_at<hi).scalar() or 0
    from ..wallet import balance
    lines += [f"📚 Yangi o‘zlashtirilgan mavzular: {learned}", f"🪙 Hozirgi yagona balans: {balance(db, st.id)}"]
    return "\n".join(lines)


def send_parent_reports(db: Session, start: date) -> int:
    if not _claim(db, f"parent_report:{start.isoformat()}"):
        return 0
    accounts = _eligible_accounts(db)
    pts = points(db, start, list(accounts))
    sent = 0
    for aid, (acc, st) in accounts.items():
        first = (st.full_name or "").split()[0] if st.full_name else "Farzandingiz"
        sent += notify_parents_of_student(db, student_id=st.id, ntype="report",
                                          title=f"Haftalik hisobot: {first}",
                                          body=_report_body(db, acc, st, start, pts.get(aid, 0)))
    db.commit()
    log.info("Ota-onalarga haftalik hisobot (%s): %d ta", start, sent)
    return sent


def run_due(db: Session) -> None:
    """O'tgan hafta uchun bajarilmagan ishlarni bajaradi (idempotent)."""
    prev = week_start(tz.today()) - timedelta(days=7)
    if prev < FIRST_WEEK:
        return
    finalize_week(db, prev)
    if tz.now().hour >= 9 or tz.today() > week_start(tz.today()):   # dushanba 09:00 dan keyin
        send_parent_reports(db, prev)


def _loop() -> None:
    from ..database import SessionLocal
    while True:
        db = SessionLocal()
        try:
            run_due(db)
        except Exception:
            log.exception("Haftalik jarayon xatosi")
            db.rollback()
        finally:
            db.close()
        time.sleep(600)


def start_scheduler() -> threading.Thread:
    t = threading.Thread(target=_loop, name="minar_weekly", daemon=True)
    t.start()
    return t
