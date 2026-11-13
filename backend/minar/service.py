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
from sqlalchemy.orm import aliased, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, tz
from ..coin_launch import scope as coin_scope, phase as coin_phase, active_since
from ..wallet import account_transaction
from . import achievements, learning, notify, playground
from . import catalog as C
from . import games
from .errors import MinarError
from .models import (
    MinarStock, MinarAccount, MinarBattle, MinarLedger, MinarLesson, MinarPurchase, MinarQuest, MinarResult, MinarProgress,
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
    ct, ce = coin_scope(db, db.query(func.coalesce(func.sum(CT.amount), 0), _positive(CT.amount))
        .filter(CT.student_id == acc.student_id), CT).one()
    lt, le = coin_scope(db, db.query(func.coalesce(func.sum(MinarLedger.amount), 0), _positive(MinarLedger.amount))
        .filter(MinarLedger.account_id == acc.id), MinarLedger).one()
    return int(ct) + int(lt), int(ce) + int(le)


def earned_today(db: Session, acc: MinarAccount) -> int:
    start, end = tz.day_bounds(tz.today())
    crm = coin_scope(db, db.query(_positive(CT.amount)).filter(CT.student_id == acc.student_id,
        CT.created_at >= start, CT.created_at < end), CT).scalar()
    space = coin_scope(db, db.query(_positive(MinarLedger.amount)).filter(MinarLedger.account_id == acc.id,
        MinarLedger.local_date == today_key()), MinarLedger).scalar()
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
    if not isinstance(raw, dict):
        raw = {}
    eq = {slot: (raw.get(slot) if isinstance(raw.get(slot), str) else None) for slot in C.SLOTS}
    if eq["planet"] not in C.PLANETS:
        eq["planet"] = None
    return eq


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
    for t in coin_scope(db, db.query(CT).filter(CT.student_id == acc.student_id), CT).order_by(CT.created_at.desc()).limit(limit).all():
        reason = (t.reason or "").strip()
        from ..reward_policy import coin_title
        title = coin_title(reason, t.amount)
        items.append((t.created_at, {
            "id": f"crm-{t.id}", "title": title, "amount": int(t.amount),
            "date": _local_date(t.created_at), "time": tz.isoformat(t.created_at), "kind": "reward",
        }))
    for l in coin_scope(db, db.query(MinarLedger).filter(MinarLedger.account_id == acc.id), MinarLedger) \
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
            "coins": int(db.query(func.coalesce(func.sum(CT.amount),0)).filter_by(student_id=sid,reason=f"Davomat:{a.group_id}:{sid}:{k}").scalar() or 0)})

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
        results.append({**data, "id": r.result_id, "game": r.game, "date": r.local_date, "award": r.award,"xp":r.xp})

    purchases = [
        {"id": p.id, "productId": p.product_id, "name": p.name, "price": p.price,
         "date": p.local_date, "status": p.status}
        for p in db.query(MinarPurchase).filter(MinarPurchase.account_id == acc.id)
        .order_by(MinarPurchase.created_at.desc()).limit(100).all()
    ]
    lessons = [f"{l.course}-{l.lesson_index}" for l in db.query(MinarLesson)
               .filter(MinarLesson.account_id == acc.id).order_by(MinarLesson.completed_at).all()]
    lessons += [f"study-{p.content_id}" for p in db.query(MinarProgress).filter(
        MinarProgress.account_id == acc.id, MinarProgress.completed_at.isnot(None)).order_by(MinarProgress.completed_at).all()]
    quests = [f"{q.local_date}:{q.quest}" for q in db.query(MinarQuest)
              .filter(MinarQuest.account_id == acc.id, MinarQuest.local_date >= (tz.today()-timedelta(days=7)).isoformat()).order_by(MinarQuest.claimed_at).all()]
    checkins = [k[0].split(":", 1)[1] for k in db.query(MinarLedger.ref_key).filter(
        MinarLedger.account_id == acc.id, MinarLedger.kind == "checkin", MinarLedger.local_date >= (tz.today()-timedelta(days=90)).isoformat()).order_by(MinarLedger.local_date).all()]

    game_rewards = {}
    for row in db.query(MinarResult).filter_by(account_id=acc.id,local_date=today_key()).all():
        if json.loads(row.payload).get('lightning',0)>0:
            game_rewards[row.game]=game_rewards.get(row.game,0)+1

    today = today_key()
    daily_games = _daily_competitive_games(db, acc, today)
    daily_lesson = db.query(MinarLedger.id).filter(MinarLedger.account_id==acc.id,MinarLedger.kind=="lesson",MinarLedger.local_date==today).first() is not None
    return {
        "coinPhase": coin_phase(db),
        "dailyProgress": {"typing":"typing" in daily_games,"games":len(daily_games),"lesson":daily_lesson},
        "version": 1,
        "enrollments": enrollment_rows,
        "stock": {r.product_id:r.quantity for r in db.query(MinarStock).all()},
        "profile": {
            "id": acc.login_id, "name": name, "surname": surname, "course": next((g['course'] for g in enrollment_rows if g['selected']), 'Guruh dasturi'),
            "group": next((g["name"] for g in enrollment_rows if g["selected"]), "Minar Academy"), "character": acc.character,
        },
        "balance": balance,
        "earned": earned,
        "earnedToday": earned_today(db, acc),
        "xp": acc.xp,
        "lightning": lightning_total(db, acc.id),
        "lightningBadges": lightning_total(db, acc.id) // 10,
        "characterLevels": C.CHARACTER_LEVEL,
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
    # SPACE never grants spendable coins. Only CRM academic grants may do so.
    if amount > 0:
        raise MinarError(400, "Coin faqat ustoz va davomat orqali beriladi.")
    if amount > 0 and coin_phase(db)["testMode"]:
        title = "Test coinlari — dushanbagacha: " + title
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
    first_visit = not acc.last_login and not db.query(MinarLedger.id).filter_by(account_id=acc.id, ref_key="welcome-xp").first()
    if first_visit:
        acc.xp += C.WELCOME_XP
        _credit(db, acc, 0, "Birinchi tashrif XP", "welcome", "welcome-xp")
    acc.last_login = today
    _credit(db, acc, C.CHECKIN_COIN, "Kunlik kirish", "checkin", f"checkin:{today}")
    _commit(db)
    return 0, "+20 XP — birinchi tashrif!" if first_visit else "Xush kelibsan!"


def act_purchase(db: Session, acc: MinarAccount, product_id: Any, request_id: Any) -> tuple[int, str]:
    if not isinstance(request_id, str) or not (8 <= len(request_id) <= 64):
        raise MinarError(400, "So‘rov noto‘g‘ri. Sahifani yangilab, qayta urinib ko‘r.")
    existing = db.query(MinarPurchase).filter(
        MinarPurchase.account_id == acc.id, MinarPurchase.request_id == request_id).first()
    if existing:
        if existing.product_id != product_id:
            raise MinarError(409, "Bu so‘rov boshqa buyum uchun ishlatilgan.")
        return 0, "Xarid allaqachon amalga oshirilgan."
    if coin_phase(db)['testMode']:
        raise MinarError(409, "Test coinlari bilan xarid qilinmaydi. Do‘kon 2-noyabr dushanba 00:00 da ochiladi (Toshkent).")
    product = C.PRODUCTS.get(product_id) if isinstance(product_id, str) else None
    if not product:
        raise MinarError(404, "Bu mahsulot topilmadi.")
    if product_id in C.RETIRED_HERO_PRODUCTS:
        raise MinarError(410, "Bu buyum sotuvdan olindi. Hero shopdan sayyora tanlang.")
    name, category, _slot, price = product
    if category == "hero" and product_id in owned_hero_items(db, acc):
        raise MinarError(409, "Bu buyum senda bor.")
    need = C.PRODUCT_MIN_LEVEL.get(product_id, 1)
    if C.level_of(acc.xp) < need:
        raise MinarError(403, f"Bu buyum {need}-darajada ochiladi. XP yig‘ishda davom et!")
    balance, _ = balance_and_earned(db, acc)
    if balance < price:
        raise MinarError(400, "Coinlaring hali yetmaydi. Darslarda qatnashib, vazifalarni bajarib coin yig‘.")

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
    if _slot == "planet":
        eq = get_equipment(acc)
        eq["planet"] = product_id
        acc.equipment = json.dumps(eq)
    _commit(db)
    if category == "hero":
        return 0, "Sayyora seniki! Profilingda yangi olam ochildi."
    return 0, "Buyurtma qabul qilindi! Tayyor bo‘lganda “Olib ketish mumkin” holati chiqadi."


def act_equip(db: Session, acc: MinarAccount, product_id: Any) -> tuple[int, str]:
    product = C.PRODUCTS.get(product_id) if isinstance(product_id, str) else None
    if not product or product[1] != "hero" or not product[2] or product_id not in owned_hero_items(db, acc):
        raise MinarError(400, "Avval buyumni xarid qil.")
    slot = product[2]
    eq = get_equipment(acc)
    eq[slot] = product_id if slot == "planet" else None if eq.get(slot) == product_id else product_id
    acc.equipment = json.dumps(eq)
    _commit(db)
    return 0, "Qahramoning yangilandi!"


def act_character(db: Session, acc: MinarAccount, character: Any) -> tuple[int, str]:
    if character not in C.CHARACTERS:
        raise MinarError(400, "Qahramon topilmadi.")
    if C.level_of(acc.xp) < C.CHARACTER_LEVEL[character]:
        raise MinarError(403, "Bu qahramon uchun darajangiz yetarli emas.")
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
    return C.LESSON_COIN, "Dars yakunlandi. Coinni ustoz baholashdan keyin beradi."


def act_homework(db: Session, acc: MinarAccount, homework_id: int, payload: Any) -> tuple[int, str]:
    if not isinstance(payload, dict):
        raise MinarError(400, "Javobingni yoz.")
    learning.submit(db, acc, homework_id, payload)
    return 0, "Javobing ustozga yuborildi! Baholanganda xabar beramiz."


def _daily_competitive_games(db, acc, today):
    # Practice must not unlock coin-bearing daily quests indirectly.
    return list({game for game, payload in db.query(MinarResult.game, MinarResult.payload).filter(
        MinarResult.account_id == acc.id, MinarResult.local_date == today).all()
        if json.loads(payload).get('practice') is not True})


def act_quest(db: Session, acc: MinarAccount, quest: Any) -> tuple[int, str]:
    if quest not in C.QUESTS:
        raise MinarError(400, "Topshiriq topilmadi.")
    today = today_key()
    if db.query(MinarQuest.id).filter(
            MinarQuest.account_id == acc.id, MinarQuest.local_date == today, MinarQuest.quest == quest).first():
        raise MinarError(409, "Bu mukofot olingan.")
    games_today = _daily_competitive_games(db, acc, today)
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
    return C.QUEST_COIN, "Topshiriq bajarildi!"


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
    table_result = None
    if result.get("roomId"):
        from . import tables
        table_result = tables.result(db, acc, result["roomId"])
        rid = "table:" + result["roomId"]
    elif result.get("game") == "battle":
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
    if session is None and table_result is None:
        for old in db.query(MinarResult).filter(MinarResult.account_id==acc.id,MinarResult.game=="battle").all():
            try:
                if json.loads(old.payload).get("matchId")==battle.match_id:
                    return old.award, "Natija allaqachon saqlangan."
            except ValueError:
                continue
    prev = db.query(MinarResult).filter(MinarResult.account_id == acc.id, MinarResult.result_id == rid).first()
    if prev:
        return prev.award, "Natija allaqachon saqlangan."

    if table_result is not None:
        payload, eligible = table_result
    elif session is None:
        eligible = not battle.draw and battle.winner_account_id == acc.id
        payload = {"game": "battle", "mode": battle.mode, "matchId": battle.match_id,
                   "won": eligible, "draw": bool(battle.draw), "practice": False,
                   "score": (battle.host_score if acc.id == battle.host_account_id else battle.guest_score) or 0}
    else:
        payload, eligible = games.finish(session, result)
        payload = {"game": session.game, **payload, "practice": games._state(session).get('practice') is True}
        session.finished_at = datetime.utcnow()
    game = payload["game"]
    # Only immutable room/session state decides practice. Client claims cannot
    # turn a computer opponent into a rewarded multiplayer result.
    practice = payload.get('practice') is True
    eligible = eligible and not practice
    payload["eligible"] = eligible

    today = today_key()
    played = coin_scope(db, db.query(func.count(MinarResult.id)).filter(
        MinarResult.account_id == acc.id, MinarResult.local_date == today,
        MinarResult.game == game, MinarResult.award > 0), MinarResult).scalar() or 0
    award = 0
    # Reward counters use verified result payloads, never client-supplied values.
    today_rows = db.query(MinarResult).filter_by(account_id=acc.id,local_date=today,game=game).all()
    rewarded = sum(bool(json.loads(row.payload).get("lightning",0)) for row in today_rows)
    lightning = C.LIGHTNING_WIN if eligible and rewarded < C.DAILY_REWARDED_GAMES else 0
    payload["lightning"] = lightning
    attempts = coin_scope(db, db.query(func.count(MinarResult.id)).filter(MinarResult.account_id == acc.id,
        MinarResult.local_date == today, MinarResult.game == game), MinarResult).scalar() or 0
    xp = C.XP_WIN if lightning else 0

    db.add(MinarResult(
        account_id=acc.id, result_id=rid, game=game, payload=json.dumps(payload),
        award=award, xp=xp, local_date=today, created_at=datetime.utcnow(),
    ))
    acc.xp += xp
    if award:
        _credit(db, acc, award, f"{C.GAME_TITLE[game]} yutug‘i", "game", f"game:{rid}")
    _commit(db)
    if practice:
        return 0, "Mashq yakunlandi. Mashq uchun XP, chaqmoq va coin berilmaydi."
    if lightning:
        return 0, f"Zo‘r natija! +{lightning}⚡ va +{xp} XP."
    if eligible:
        return 0, "Bugungi mukofotlar olindi. Mashqni davom ettir — ertaga yana ⚡ va XP olasan!"
    return 0, games.GOAL_HINT.get(game, "Yaxshi urinish! Yana mashq qilib ko‘r.")


# ── Reyting ─────────────────────────────────────────────────────────────────

def leaderboard(db: Session, me: MinarAccount, metric: str, period: str, course: str) -> list[dict]:
    if metric not in ("lightning", "xp", "coins", "active"):
        raise MinarError(400, "Reyting turi noto‘g‘ri.")
    if period not in ("week", "all"):
        raise MinarError(400, "Reyting davri noto‘g‘ri.")
    if course != "all" and course not in C.COURSES:
        raise MinarError(400, "Kurs noto‘g‘ri.")

    week_start = tz.today() - timedelta(days=6)
    week_utc = tz.day_bounds(week_start)[0]
    crm_all = {sid: int(v) for sid, v in coin_scope(db, db.query(CT.student_id, func.coalesce(func.sum(CT.amount),0)), CT).group_by(CT.student_id).all()}
    crm_week = {sid: int(v) for sid, v in coin_scope(db, db.query(CT.student_id, _positive(CT.amount))
                .filter(CT.created_at >= week_utc), CT).group_by(CT.student_id).all()}
    led_all = {aid: int(v) for aid, v in coin_scope(db, db.query(MinarLedger.account_id, func.coalesce(func.sum(MinarLedger.amount),0)), MinarLedger)
               .group_by(MinarLedger.account_id).all()}
    led_week = {aid: int(v) for aid, v in coin_scope(db, db.query(MinarLedger.account_id, _positive(MinarLedger.amount))
                .filter(MinarLedger.local_date >= week_start.isoformat()), MinarLedger).group_by(MinarLedger.account_id).all()}

    lightning_by_account = {}
    reward_query=db.query(MinarResult.account_id,MinarResult.payload)
    if period=='week': reward_query=reward_query.filter(MinarResult.local_date>=week_start.isoformat())
    for aid,payload in reward_query.all():
        lightning_by_account[aid]=lightning_by_account.get(aid,0)+int(json.loads(payload).get('lightning',0))
    rows = []
    q = (
        db.query(MinarAccount, models.Student.full_name)
        .join(models.Student, models.Student.id == MinarAccount.student_id)
        .filter(MinarAccount.is_active.is_(True), MinarAccount.is_test.is_(False), models.Student.is_active.is_(True),
                models.Student.is_archived.is_(False))
    )
    from .study import course_name
    group_by_student = {}
    memberships = db.query(models.GroupStudent.student_id, models.Group).join(
        models.Group, models.Group.id == models.GroupStudent.group_id).options(joinedload(models.Group.course)).filter(
        models.GroupStudent.left_at.is_(None), models.Group.is_active.is_(True)).order_by(models.GroupStudent.joined_at.desc()).all()
    for sid, group in memberships:
        group_by_student.setdefault(sid, []).append(group)
    for acc, full_name in q.all():
        if course != "all" and acc.course != course:
            continue
        groups = group_by_student.get(acc.student_id, [])
        selected = next((g for g in groups if g.id == acc.active_group_id), groups[0] if groups else None)
        rows.append({
            "id": acc.login_id,
            "name": public_name(full_name),
            "avatar": C.CHARACTER_EMOJI.get(acc.character, "🤖"),
            "character": acc.character,
            "equipment": get_equipment(acc),
            "coins": crm_all.get(acc.student_id, 0) + led_all.get(acc.id, 0),
            "week": crm_week.get(acc.student_id, 0) + led_week.get(acc.id, 0),
            "xp": acc.xp,
            "level": C.level_of(acc.xp),
            "lightning": lightning_by_account.get(acc.id,0),
            "active": effective_streak(acc),
            "course": course_name(selected) if selected else "Guruh dasturi",
        })

    rows.sort(key=lambda r: (-r["xp"],-r["lightning"],r["id"]) if metric=="xp" else (-r["lightning"],-r["xp"],r["id"]))
    for i, row in enumerate(rows, 1):
        row.update(rank=i, total=len(rows))
    top = rows[:50]
    if me.login_id not in {r["id"] for r in top}:
        top += [r for r in rows if r["id"] == me.login_id]
    return top


def lightning_total(db, account_id, since=None):
    q=db.query(MinarResult.payload).filter_by(account_id=account_id)
    if since: q=q.filter(MinarResult.local_date>=since)
    return sum(int(json.loads(payload).get('lightning',0)) for (payload,) in q.all())


def public_profile(db, me, login_id):
    # All active students have a world; private fields remain outside this whitelist.
    acc = db.query(MinarAccount).filter_by(login_id=login_id, is_active=True).first()
    if not acc:
        raise MinarError(404, 'Profil topilmadi.')
    st = db.query(models.Student).filter_by(id=acc.student_id).one()
    eq = get_equipment(acc)
    if eq['planet'] not in owned_hero_items(db, acc):
        eq['planet'] = None
    if login_id != me.login_id:
        if acc.is_test or not st.is_active or st.is_archived:
            raise MinarError(404, 'Ommaviy profil topilmadi.')
    from .study import course_name
    groups = learning.active_groups(db, acc.student_id)
    group = next((g for g in groups if g.id == acc.active_group_id), groups[0] if groups else None)
    coins, _ = balance_and_earned(db, acc)
    lightning = lightning_total(db, acc.id)
    return {'id': acc.login_id, 'name': st.full_name if login_id == me.login_id else public_name(st.full_name),
            'course': course_name(group) if group else 'Guruh dasturi', 'character': acc.character, 'level': C.level_of(acc.xp),
            'xp': acc.xp, 'lightning': lightning, 'coins': coins, 'badges': lightning // 10, 'equipment': eq}
