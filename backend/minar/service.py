"""Minar Space biznes-mantiqi.

Frontenddagi demo dvigatel (`lib/minar/engine.js`) qoidalarining serverdagi ishonchli nusxasi.
Barcha yozuvchi amallar bazadagi talaba va akkaunt satri qulfi ostida bajariladi,
takroriy amallar esa bazadagi UNIQUE cheklovlar bilan ham himoyalangan.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import case, func, and_, exists
from sqlalchemy.orm import aliased
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, tz
from ..wallet import account_transaction
from . import achievements, learning, notify, playground
from . import catalog as C
from . import games
from .errors import MinarError
from .models import (
    MinarStock, MinarAccount, MinarBattle, MinarLedger, MinarLesson, MinarPurchase, MinarQuest, MinarResult,
)

CT = models.CoinTransaction

BAD_RESULT = "Natija tekshiruvdan o‘tmadi."


def today_key() -> str:
    return tz.today().isoformat()


def _local_date(dt: datetime) -> str:
    return tz.to_local(dt).date().isoformat()


def _split_name(full_name: str | None) -> tuple[str, str]:
    parts = (full_name or "").split(None, 1)
    return (parts[0] if parts else "O‘quvchi"), (parts[1] if len(parts) > 1 else "")


def public_name(full_name: str | None) -> str:
    """Reytingda boshqa bolalarga faqat ism + familiya bosh harfi ko'rsatiladi."""
    first, last = _split_name(full_name)
    return f"{first} {last[0]}." if last else first


# ── Hisoblar ────────────────────────────────────────────────────────────────

def _positive(col):
    condition = col > 0
    if getattr(col, "class_", None) is CT:
        reversal = aliased(CT)
        condition = and_(condition, CT.reversal_of_id.is_(None),
            ~exists().where(reversal.reversal_of_id == CT.id).correlate(CT))
    elif getattr(col, "class_", None) is MinarLedger:
        condition = and_(condition, MinarLedger.kind != "refund")
    return func.coalesce(func.sum(case((condition, col), else_=0)), 0)


def balance_and_earned(db: Session, acc: MinarAccount) -> tuple[int, int]:
    """(balans, jami yig'ilgan). Balans = CRM (o'qituvchi) coinlari + ilova ledgeri."""
    ct, ce = db.query(func.coalesce(func.sum(CT.amount), 0), _positive(CT.amount)) \
        .filter(CT.student_id == acc.student_id).one()
    lt, le = db.query(func.coalesce(func.sum(MinarLedger.amount), 0), _positive(MinarLedger.amount)) \
        .filter(MinarLedger.account_id == acc.id).one()
    return int(ct) + int(lt), int(ce) + int(le)


def earned_today(db: Session, acc: MinarAccount) -> int:
    start, end = tz.day_bounds(tz.today())
    crm = db.query(_positive(CT.amount)).filter(CT.student_id == acc.student_id,
        CT.created_at >= start, CT.created_at < end).scalar()
    space = db.query(_positive(MinarLedger.amount)).filter(MinarLedger.account_id == acc.id,
        MinarLedger.local_date == today_key()).scalar()
    return int(crm) + int(space)


def effective_streak(acc: MinarAccount) -> int:
    """Kecha yoki bugun kirmagan bo'lsa ketma-ketlik uzilgan."""
    if not acc.last_login:
        return 0
    yesterday = (tz.today() - timedelta(days=1)).isoformat()
    return acc.streak if acc.last_login in (today_key(), yesterday) else 0


def get_equipment(acc: MinarAccount) -> dict:
    try:
        raw = json.loads(acc.equipment or "{}")
    except ValueError:
        raw = {}
    return {slot: (raw.get(slot) if isinstance(raw.get(slot), str) else None) for slot in C.SLOTS}


def owned_hero_items(db: Session, acc: MinarAccount) -> list[str]:
    ids = [r[0] for r in db.query(MinarPurchase.product_id).filter(MinarPurchase.account_id == acc.id)
           .order_by(MinarPurchase.created_at).all()]
    seen: list[str] = []
    for pid in ids:
        if C.PRODUCTS.get(pid, (None, None))[1] == "hero" and pid not in seen:
            seen.append(pid)
    return seen


def _group_label(db: Session, student_id: int) -> str:
    g = (
        db.query(models.Group)
        .join(models.GroupStudent, models.GroupStudent.group_id == models.Group.id)
        .filter(models.GroupStudent.student_id == student_id, models.Group.is_active.is_(True),
                models.GroupStudent.left_at.is_(None))
        .order_by(models.GroupStudent.joined_at.desc())
        .first()
    )
    return g.name if g else "Minar Academy"


# ── Holat (StudentState) ────────────────────────────────────────────────────

def _history(db: Session, acc: MinarAccount, limit: int = 30) -> list[dict]:
    items: list[tuple[datetime, dict]] = []
    for t in db.query(CT).filter(CT.student_id == acc.student_id).order_by(CT.created_at.desc()).limit(limit).all():
        reason = (t.reason or "").strip()
        title = reason or ("O‘qituvchi mukofoti" if t.amount > 0 else "Coin yechildi")
        items.append((t.created_at, {
            "id": f"crm-{t.id}", "title": title, "amount": int(t.amount),
            "date": _local_date(t.created_at), "time": tz.isoformat(t.created_at), "kind": "reward",
        }))
    for l in db.query(MinarLedger).filter(MinarLedger.account_id == acc.id) \
            .order_by(MinarLedger.created_at.desc()).limit(limit).all():
        items.append((l.created_at, {
            "id": f"led-{l.id}", "title": l.title, "amount": int(l.amount),
            "date": l.local_date, "time": tz.isoformat(l.created_at), "kind": l.kind,
        }))
    items.sort(key=lambda x: x[0], reverse=True)
    return [i[1] for i in items[:limit]]


def _attendance(db: Session, acc: MinarAccount) -> list[dict]:
    sid = acc.student_id
    entries = db.query(models.Attendance, models.Group.name).join(models.Group, models.Group.id == models.Attendance.group_id).filter(
        models.Attendance.student_id == sid, models.Attendance.is_present.isnot(None)).order_by(models.Attendance.lesson_date.desc()).limit(500).all()

    first_seen: dict[str, datetime] = {}
    for c in db.query(models.CameraAttendance).filter(
        models.CameraAttendance.student_id == sid,
        models.CameraAttendance.person_type == "student",
        models.CameraAttendance.event_type == "keldi",
        models.CameraAttendance.detected_at >= tz.day_bounds(min((a.lesson_date for a, _ in entries), default=tz.today()))[0],
    ).all():
        k = _local_date(c.detected_at)
        if k not in first_seen or c.detected_at < first_seen[k]:
            first_seen[k] = c.detected_at

    out = []
    for a, group_name in entries:
        k, here = a.lesson_date.isoformat(), bool(a.is_present)
        out.append({"id": a.id, "groupId": a.group_id, "group": group_name, "date": k,
            "status": "present" if here else "absent",
            "time": tz.to_local(first_seen[k]).strftime("%H:%M") if here and k in first_seen else None,
            "coins": 0})

    return out


def build_state(db: Session, acc: MinarAccount) -> dict:
    from .study import enrollments
    enrollment_rows = enrollments(db, acc)
    student = db.query(models.Student).filter(models.Student.id == acc.student_id).one()
    name, surname = _split_name(student.full_name)
    balance, earned = balance_and_earned(db, acc)

    results = []
    for r in db.query(MinarResult).filter(MinarResult.account_id == acc.id) \
            .order_by(MinarResult.created_at.desc()).limit(30).all():
        try:
            data = json.loads(r.payload)
        except ValueError:
            data = {}
        results.append({**data, "id": r.result_id, "game": r.game, "date": r.local_date, "award": r.award})

    purchases = [
        {"id": p.id, "productId": p.product_id, "name": p.name, "price": p.price,
         "date": p.local_date, "status": p.status}
        for p in db.query(MinarPurchase).filter(MinarPurchase.account_id == acc.id)
        .order_by(MinarPurchase.created_at.desc()).limit(100).all()
    ]
    lessons = [f"{l.course}-{l.lesson_index}" for l in db.query(MinarLesson)
               .filter(MinarLesson.account_id == acc.id).order_by(MinarLesson.completed_at).all()]
    quests = [f"{q.local_date}:{q.quest}" for q in db.query(MinarQuest)
              .filter(MinarQuest.account_id == acc.id, MinarQuest.local_date >= (tz.today()-timedelta(days=7)).isoformat()).order_by(MinarQuest.claimed_at).all()]
    checkins = [k[0].split(":", 1)[1] for k in db.query(MinarLedger.ref_key).filter(
        MinarLedger.account_id == acc.id, MinarLedger.kind == "checkin", MinarLedger.local_date >= (tz.today()-timedelta(days=90)).isoformat()).order_by(MinarLedger.local_date).all()]

    game_rewards = {g: int(n) for g, n in db.query(MinarResult.game, func.count(MinarResult.id)).filter(
        MinarResult.account_id == acc.id, MinarResult.local_date == today_key(), MinarResult.award > 0,
    ).group_by(MinarResult.game).all()}

    today = today_key()
    daily_games = [g for g, in db.query(MinarResult.game).filter(MinarResult.account_id==acc.id,MinarResult.local_date==today).distinct()]
    daily_lesson = db.query(MinarLedger.id).filter(MinarLedger.account_id==acc.id,MinarLedger.kind=="lesson",MinarLedger.local_date==today).first() is not None
    return {
        "dailyProgress": {"typing":"typing" in daily_games,"games":len(daily_games),"lesson":daily_lesson},
        "version": 1,
        "enrollments": enrollment_rows,
        "stock": {r.product_id:r.quantity for r in db.query(MinarStock).all()},
        "profile": {
            "id": acc.login_id, "name": name, "surname": surname, "course": acc.course,
            "group": _group_label(db, acc.student_id), "character": acc.character,
        },
        "balance": balance,
        "earned": earned,
        "earnedToday": earned_today(db, acc),
        "xp": acc.xp,
        "streak": effective_streak(acc),
        "lastLogin": acc.last_login,
        "owned": owned_hero_items(db, acc),
        "equipment": get_equipment(acc),
        "history": _history(db, acc),
        "attendance": _attendance(db, acc),
        "purchases": purchases,
        "results": results,
        "completedLessons": lessons,
        "claimedQuests": quests,
        "checkins": checkins,
        "gameRewards": game_rewards,
        "dailyRewardLimit": C.DAILY_REWARDED_GAMES,
        "level": C.level_of(acc.xp),
        "unlocks": C.UNLOCK_LEVEL,
        "productLevels": C.PRODUCT_MIN_LEVEL,
        "achievements": achievements.progress(db, acc),
        "unreadNotifications": notify.unread_count(db, acc),
        "homeworkPending": learning.pending_count(db, acc),
    }


# ── Amallar ─────────────────────────────────────────────────────────────────

def _credit(db: Session, acc: MinarAccount, amount: int, title: str, kind: str, ref_key: str) -> None:
    db.add(MinarLedger(
        account_id=acc.id, ref_key=ref_key, kind=kind, title=title, amount=amount,
        local_date=today_key(), created_at=datetime.utcnow(),
    ))


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise MinarError(409, "Bu amal allaqachon bajarilgan.")


def run(db: Session, acc: MinarAccount, fn: Callable[..., tuple[int, str]], *args: Any) -> dict:
    """Amalni qulf ostida bajarib, to'liq holat bilan javob tayyorlaydi."""
    with account_transaction(db, acc):
        db.refresh(acc)
        award, message = fn(db, acc, *args)
        db.refresh(acc)
        unlocked = achievements.evaluate(db, acc)
        if unlocked:
            _commit(db)
        return {"state": build_state(db, acc), "award": award, "message": message, "unlocked": unlocked}


def run_playground(db: Session, acc: MinarAccount, task_id: str, payload: Any) -> dict:
    """Kod maydoni tekshiruvi: tekshiruv natijalari + (yechilgan bo'lsa) yangilangan holat."""
    with account_transaction(db, acc):
        db.refresh(acc)
        results, ok, first = playground.check(db, acc, task_id, payload)
        if not ok:
            return {"checks": results, "solved": False, "award": 0, "unlocked": [],
                    "message": "Hali hammasi to‘g‘ri emas — qizil bandlarni tuzat."}
        _commit(db)
        unlocked = achievements.evaluate(db, acc)
        if unlocked:
            _commit(db)
        db.refresh(acc)
        award = playground.REWARD if first else 0
        message = f"Ajoyib! Topshiriq bajarildi: +{award} coin, +{playground.XP} XP." if first \
            else "To‘g‘ri! Bu topshiriq avval bajarilgan — kodingni yangiladik."
        return {"checks": results, "solved": True, "award": award, "message": message,
                "unlocked": unlocked, "state": build_state(db, acc)}


def act_checkin(db: Session, acc: MinarAccount) -> tuple[int, str]:
    today = today_key()
    already = db.query(MinarLedger.id).filter(
        MinarLedger.account_id == acc.id, MinarLedger.ref_key == f"checkin:{today}").first()
    if already or acc.last_login == today:
        return 0, ""
    yesterday = (tz.today() - timedelta(days=1)).isoformat()
    if acc.last_login == yesterday:
        acc.streak += 1
    elif acc.last_login:
        acc.streak = 1
    else:
        acc.streak += 1
    acc.last_login = today
    _credit(db, acc, C.CHECKIN_COIN, "Kunlik kirish", "checkin", f"checkin:{today}")
    _commit(db)
    return C.CHECKIN_COIN, "Xush kelibsan! Bugungi +1 coin seniki."


def act_purchase(db: Session, acc: MinarAccount, product_id: Any, request_id: Any) -> tuple[int, str]:
    if not isinstance(request_id, str) or not (8 <= len(request_id) <= 64):
        raise MinarError(400, "So‘rov noto‘g‘ri. Sahifani yangilab, qayta urinib ko‘r.")
    existing = db.query(MinarPurchase).filter(
        MinarPurchase.account_id == acc.id, MinarPurchase.request_id == request_id).first()
    if existing:
        if existing.product_id != product_id:
            raise MinarError(409, "Bu so‘rov boshqa buyum uchun ishlatilgan.")
        return 0, "Xarid allaqachon amalga oshirilgan."
    product = C.PRODUCTS.get(product_id) if isinstance(product_id, str) else None
    if not product:
        raise MinarError(404, "Bu mahsulot topilmadi.")
    name, category, _slot, price = product
    if category == "hero" and product_id in owned_hero_items(db, acc):
        raise MinarError(409, "Bu buyum senda bor.")
    need = C.PRODUCT_MIN_LEVEL.get(product_id, 1)
    if C.level_of(acc.xp) < need:
        raise MinarError(403, f"Bu buyum {need}-darajada ochiladi. XP yig‘ishda davom et!")
    balance, _ = balance_and_earned(db, acc)
    if balance < price:
        raise MinarError(400, "Coinlaring hali yetmaydi. Yana bir o‘yin o‘ynab ko‘r!")

    if category == "space":
        stock = db.query(MinarStock).filter_by(product_id=product_id).with_for_update().first()
        if not stock or stock.quantity <= 0:
            raise MinarError(409, "Bu sovg‘a hozir omborda qolmagan.")
        stock.quantity -= 1
        stock.updated_at = datetime.utcnow()
    now = datetime.utcnow()
    _credit(db, acc, -price, name, "purchase", f"purchase:{request_id}")
    db.add(MinarPurchase(
        id=str(uuid.uuid4()), account_id=acc.id, request_id=request_id, product_id=product_id,
        name=name, price=price, status="delivered" if category == "hero" else "pending",
        local_date=today_key(), created_at=now, updated_at=now,
    ))
    _commit(db)
    if category == "hero":
        return 0, "Xarid muborak! Qahramoningga kiydirib ko‘r."
    return 0, "Buyurtma qabul qilindi! Tayyor bo‘lganda “Olib ketish mumkin” holati chiqadi."


def act_equip(db: Session, acc: MinarAccount, product_id: Any) -> tuple[int, str]:
    product = C.PRODUCTS.get(product_id) if isinstance(product_id, str) else None
    if not product or product[1] != "hero" or not product[2] or product_id not in owned_hero_items(db, acc):
        raise MinarError(400, "Avval buyumni xarid qil.")
    slot = product[2]
    eq = get_equipment(acc)
    eq[slot] = None if eq.get(slot) == product_id else product_id
    acc.equipment = json.dumps(eq)
    _commit(db)
    return 0, "Qahramoning yangilandi!"


def act_character(db: Session, acc: MinarAccount, character: Any) -> tuple[int, str]:
    if character not in C.CHARACTERS:
        raise MinarError(400, "Qahramon topilmadi.")
    acc.character = character
    _commit(db)
    return 0, "Yangi sarguzashtdoshing tayyor!"


def act_lesson(db: Session, acc: MinarAccount, index: Any) -> tuple[int, str]:
    if isinstance(index, bool) or not isinstance(index, int) or not (0 <= index < C.LESSONS_PER_COURSE):
        raise MinarError(400, "Dars topilmadi.")
    done = db.query(MinarLesson.id).filter(
        MinarLesson.account_id == acc.id, MinarLesson.course == acc.course,
        MinarLesson.lesson_index == index).first()
    if done:
        return 0, "Bu dars avval yakunlangan."
    db.add(MinarLesson(account_id=acc.id, course=acc.course, lesson_index=index, completed_at=datetime.utcnow()))
    acc.xp += C.LESSON_XP
    _credit(db, acc, C.LESSON_COIN, "Dars yakunlandi", "lesson", f"lesson:{acc.course}-{index}")
    _commit(db)
    return C.LESSON_COIN, "Ajoyib! +5 coin va +50 XP."


def act_homework(db: Session, acc: MinarAccount, homework_id: int, payload: Any) -> tuple[int, str]:
    if not isinstance(payload, dict):
        raise MinarError(400, "Javobingni yoz.")
    learning.submit(db, acc, homework_id, payload)
    return 0, "Javobing ustozga yuborildi! Baholanganda xabar beramiz."


def act_quest(db: Session, acc: MinarAccount, quest: Any) -> tuple[int, str]:
    if quest not in C.QUESTS:
        raise MinarError(400, "Topshiriq topilmadi.")
    today = today_key()
    if db.query(MinarQuest.id).filter(
            MinarQuest.account_id == acc.id, MinarQuest.local_date == today, MinarQuest.quest == quest).first():
        raise MinarError(409, "Bu mukofot olingan.")
    games_today = [g[0] for g in db.query(MinarResult.game).filter(
        MinarResult.account_id == acc.id, MinarResult.local_date == today).all()]
    if quest == "typing":
        eligible = "typing" in games_today
    elif quest == "games":
        eligible = len(set(games_today)) >= 2
    else:
        eligible = db.query(MinarLedger.id).filter(
            MinarLedger.account_id == acc.id, MinarLedger.kind == "lesson", MinarLedger.local_date == today).first() is not None
    if not eligible:
        raise MinarError(400, "Avval topshiriqni yakunla.")
    db.add(MinarQuest(account_id=acc.id, local_date=today, quest=quest, claimed_at=datetime.utcnow()))
    _credit(db, acc, C.QUEST_COIN, "Kunlik topshiriq", "quest", f"quest:{today}:{quest}")
    _commit(db)
    return C.QUEST_COIN, "Topshiriq bajarildi! +5 coin."


# ── O'yin natijalari ────────────────────────────────────────────────────────

def _num(r: dict, key: str, lo: int, hi: int, default: int | None = None) -> int:
    v = r.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or not (lo <= v <= hi):
        raise MinarError(400, BAD_RESULT)
    return int(round(v))


def validate_battle(r: dict) -> tuple[dict, bool]:
    """Battle natijasi (g'alaba sharti alohida — server hisobi bilan, `battle_win_confirmed`)."""
    mode = r.get("mode")
    if mode not in ("typing", "quiz"):
        raise MinarError(400, BAD_RESULT)
    match_id = r.get("matchId")
    if not isinstance(match_id, str) or not (8 <= len(match_id) <= 64):
        raise MinarError(400, BAD_RESULT)
    return ({"game": "battle", "mode": mode, "won": r.get("won") is True, "draw": r.get("draw") is True,
             "score": _num(r, "score", 0, 1000, 0), "matchId": match_id, "practice": r.get("practice") is True},
            r.get("won") is True and r.get("practice") is not True)


def battle_win_confirmed(db: Session, acc: MinarAccount, match_id: str) -> bool:
    """G'alaba faqat server tomonida yakunlangan (WebSocket) bellashuvda tan olinadi."""
    b = db.query(MinarBattle).filter(MinarBattle.match_id == match_id).first()
    return bool(b and b.status == "finished" and not b.draw and b.winner_account_id == acc.id)


def act_game(db: Session, acc: MinarAccount, result: Any) -> tuple[int, str]:
    if not isinstance(result, dict):
        raise MinarError(400, "Natija topilmadi.")
    session = None
    if result.get("game") == "battle":
        if result.get("practice") is True:
            return 0, "Mashq yakunlandi. Mashq uchun XP va coin berilmaydi."
        match_id = result.get("matchId")
        if not isinstance(match_id, str) or not 8 <= len(match_id) <= 40:
            raise MinarError(400, BAD_RESULT)
        battle = db.query(MinarBattle).filter(MinarBattle.match_id == match_id).first()
        if not battle or battle.status != "finished" or acc.id not in (battle.host_account_id, battle.guest_account_id):
            raise MinarError(400, BAD_RESULT)
        rid = f"battle:{match_id}"
    else:
        session = games.load(db, acc, result.get("session") or result.get("id"))
        rid = session.id
    # Preserve idempotency for matches rewarded by older releases using client result IDs.
    if session is None:
        for old in db.query(MinarResult).filter(MinarResult.account_id==acc.id,MinarResult.game=="battle").all():
            try:
                if json.loads(old.payload).get("matchId")==battle.match_id:
                    return old.award, "Natija allaqachon saqlangan."
            except ValueError:
                continue
    prev = db.query(MinarResult).filter(MinarResult.account_id == acc.id, MinarResult.result_id == rid).first()
    if prev:
        return prev.award, "Natija allaqachon saqlangan."

    if session is None:
        eligible = not battle.draw and battle.winner_account_id == acc.id
        payload = {"game": "battle", "mode": battle.mode, "matchId": battle.match_id,
                   "won": eligible, "draw": bool(battle.draw), "practice": False,
                   "score": (battle.host_score if acc.id == battle.host_account_id else battle.guest_score) or 0}
    else:
        payload, eligible = games.finish(session, result)
        payload = {"game": session.game, **payload}
        session.finished_at = datetime.utcnow()
    game = payload["game"]
    payload["eligible"] = eligible

    today = today_key()
    played = db.query(func.count(MinarResult.id)).filter(
        MinarResult.account_id == acc.id, MinarResult.local_date == today,
        MinarResult.game == game, MinarResult.award > 0).scalar() or 0
    award = C.GAME_BASE[game] if eligible and played < C.DAILY_REWARDED_GAMES else 0
    attempts = db.query(func.count(MinarResult.id)).filter(MinarResult.account_id == acc.id,
        MinarResult.local_date == today, MinarResult.game == game).scalar() or 0
    xp = (C.XP_WIN if eligible else C.XP_TRY) if attempts < 10 else 0

    db.add(MinarResult(
        account_id=acc.id, result_id=rid, game=game, payload=json.dumps(payload),
        award=award, xp=xp, local_date=today, created_at=datetime.utcnow(),
    ))
    acc.xp += xp
    if award:
        _credit(db, acc, award, f"{C.GAME_TITLE[game]} yutug‘i", "game", f"game:{rid}")
    _commit(db)
    if award:
        return award, f"Zo‘r natija! +{award} coin seniki."
    if eligible:
        return 0, "Bugungi mukofotlar olindi. Mashqni davom ettir — ertaga yana coin olasan!"
    return 0, games.GOAL_HINT.get(game, "Yaxshi urinish! Yana mashq qilib ko‘r.")


# ── Reyting ─────────────────────────────────────────────────────────────────

def leaderboard(db: Session, me: MinarAccount, metric: str, period: str, course: str) -> list[dict]:
    if metric not in ("coins", "active", "xp"):
        raise MinarError(400, "Reyting turi noto‘g‘ri.")
    if period not in ("week", "all"):
        raise MinarError(400, "Reyting davri noto‘g‘ri.")
    if course != "all" and course not in C.COURSES:
        raise MinarError(400, "Kurs noto‘g‘ri.")

    week_start = tz.today() - timedelta(days=6)
    week_utc = tz.day_bounds(week_start)[0]
    crm_all = {sid: int(v) for sid, v in db.query(CT.student_id, _positive(CT.amount)).group_by(CT.student_id).all()}
    crm_week = {sid: int(v) for sid, v in db.query(CT.student_id, _positive(CT.amount))
                .filter(CT.created_at >= week_utc).group_by(CT.student_id).all()}
    led_all = {aid: int(v) for aid, v in db.query(MinarLedger.account_id, _positive(MinarLedger.amount))
               .group_by(MinarLedger.account_id).all()}
    led_week = {aid: int(v) for aid, v in db.query(MinarLedger.account_id, _positive(MinarLedger.amount))
                .filter(MinarLedger.local_date >= week_start.isoformat()).group_by(MinarLedger.account_id).all()}

    rows = []
    q = (
        db.query(MinarAccount, models.Student.full_name)
        .join(models.Student, models.Student.id == MinarAccount.student_id)
        .filter(MinarAccount.is_active.is_(True), MinarAccount.is_test.is_(False), models.Student.is_active.is_(True),
                models.Student.is_archived.is_(False))
    )
    for acc, full_name in q.all():
        if course != "all" and acc.course != course:
            continue
        rows.append({
            "id": acc.login_id,
            "name": public_name(full_name),
            "avatar": C.CHARACTER_EMOJI.get(acc.character, "🤖"),
            "coins": crm_all.get(acc.student_id, 0) + led_all.get(acc.id, 0),
            "week": crm_week.get(acc.student_id, 0) + led_week.get(acc.id, 0),
            "xp": acc.xp,
            "active": effective_streak(acc),
            "course": acc.course,
        })

    def value(r: dict) -> int:
        return r["week"] if metric == "coins" and period == "week" else r["coins"] if metric == "coins" \
            else r["active"] if metric == "active" else r["xp"]

    rows.sort(key=lambda r: (-value(r), r["id"]))
    for i, row in enumerate(rows, 1):
        row.update(rank=i, total=len(rows))
    top = rows[:50]
    if me.login_id not in {r["id"] for r in top}:
        top += [r for r in rows if r["id"] == me.login_id]
    return top
