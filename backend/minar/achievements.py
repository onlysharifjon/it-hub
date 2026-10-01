"""Yutuqlar (nishonlar): katalog, progress va ochish.

Har yutuq bitta ko'rsatkichga (metric) va maqsadga (target) bog'langan. `evaluate` har
holat o'zgartiruvchi amaldan keyin chaqiriladi (service.run): yangi ochilganlarini yozadi,
mukofot coinini ledgerga qo'shadi va bildirishnoma yuboradi. Ko'rsatkichlar faqat hali
ochilmagan yutuqlar uchun hisoblanadi.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, tz
from . import catalog as C
from . import notify, playground
from .models import (
    MinarAccount, MinarAchievement, MinarBattle, MinarLedger, MinarLesson, MinarPlaygroundSolve, MinarResult,
    MinarTournamentAward,
)


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    description: str
    icon: str            # frontend (lucide) ikon kaliti
    metric: str
    target: int
    reward: int          # coin


CATALOG: tuple[Achievement, ...] = (
    Achievement("first_win", "Birinchi qadam", "Istalgan o‘yinda birinchi marta yut.", "sparkles", "wins", 1, 5),
    Achievement("wins_25", "O‘yin ustasi", "O‘yinlarda 25 marta yut.", "gamepad", "wins", 25, 20),
    Achievement("wins_100", "Afsona", "O‘yinlarda 100 marta yut.", "crown", "wins", 100, 50),
    Achievement("streak_3", "Uch kun ketma-ket", "3 kun ketma-ket kir.", "flame", "streak", 3, 5),
    Achievement("streak_7", "Haftalik qahramon", "7 kun ketma-ket kir.", "flame", "streak", 7, 15),
    Achievement("streak_30", "Temir iroda", "30 kun ketma-ket kir.", "shield", "streak", 30, 50),
    Achievement("quiz_perfect", "A’lochi", "Code Quizda 5 tadan 5 ta to‘g‘ri javob ber.", "graduation", "quiz_perfect", 1, 10),
    Achievement("bug_perfect", "Bug ovchisi", "Bug Hunterda 3 ta xatoning hammasini top.", "bug", "bug_perfect", 1, 10),
    Achievement("memory_fast", "Fil xotira", "Memory Matchni 8 urinish ichida yakunla.", "puzzle", "memory_fast", 1, 10),
    Achievement("typing_fast", "Tez barmoqlar", "Minar Typeda 30 WPM tezlik va 90% aniqlik.", "keyboard", "typing_fast", 1, 15),
    Achievement("battle_1", "Arena debyuti", "Battle arenada birinchi g‘alabani qo‘lga kirit.", "swords", "battle_wins", 1, 10),
    Achievement("battle_10", "Arena chempioni", "Battle arenada 10 marta yut.", "trophy", "battle_wins", 10, 30),
    Achievement("lessons_3", "Bilimdon", "3 ta mini-darsni yakunla.", "book", "lessons", 3, 10),
    Achievement("level_5", "Yulduzli o‘quvchi", "5-darajaga chiq.", "star", "level", 5, 20),
    Achievement("earned_500", "Coin yig‘uvchi", "Jami 500 coin yig‘.", "coins", "earned", 500, 10),
    Achievement("homework_1", "Mas’uliyatli", "Birinchi uy vazifangni Space orqali topshir.", "homework", "homework_done", 1, 5),
    Achievement("homework_10", "Intizomli", "10 ta uy vazifasini topshir.", "homework", "homework_done", 10, 25),
    Achievement("homework_a", "A’lo baho", "Uy vazifasidan 90+ ball ol.", "graduation", "homework_excellent", 1, 15),
    Achievement("code_1", "Birinchi kod", "Kod maydonida birinchi topshiriqni bajar.", "code", "code_solved", 1, 5),
    Achievement("code_10", "Yosh dasturchi", "Kod maydonida 10 ta topshiriqni bajar.", "code", "code_solved", 10, 25),
    Achievement("tournament_podium", "Shohsupada", "Haftalik turnirda 1–3-o‘rinni egalla.", "trophy", "tournament_podium", 1, 10),
    Achievement("tournament_win", "Hafta chempioni", "Haftalik turnirda guruhingda 1-o‘rinni ol.", "crown", "tournament_wins", 1, 20),
    Achievement("code_all", "Kod ustasi", "Kod maydonidagi barcha topshiriqlarni bajar.", "crown", "code_solved", len(playground.TASKS), 60),
)
BY_CODE = {a.code: a for a in CATALOG}


# ── Ko'rsatkichlar ──────────────────────────────────────────────────────────

def _won_payloads(db: Session, acc: MinarAccount, game: str) -> list[dict]:
    rows = db.query(MinarResult.payload).filter(
        MinarResult.account_id == acc.id, MinarResult.game == game, MinarResult.xp == C.XP_WIN,
    ).order_by(MinarResult.id.desc()).limit(2000).all()
    out = []
    for (raw,) in rows:
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def _any(db: Session, acc: MinarAccount, game: str, pred: Callable[[dict], bool]) -> int:
    return int(any(pred(p) for p in _won_payloads(db, acc, game)))


def _earned(db: Session, acc: MinarAccount) -> int:
    from .service import balance_and_earned   # sikl importdan qochish
    return balance_and_earned(db, acc)[1]


METRICS: dict[str, Callable[[Session, MinarAccount], int]] = {
    "wins": lambda db, acc: db.query(func.count(MinarResult.id)).filter(
        MinarResult.account_id == acc.id, MinarResult.xp == C.XP_WIN).scalar() or 0,
    "streak": lambda db, acc: acc.streak or 0,
    "quiz_perfect": lambda db, acc: _any(db, acc, "quiz", lambda p: p.get("score") == p.get("total")),
    "bug_perfect": lambda db, acc: _any(db, acc, "bug", lambda p: p.get("score") == p.get("total")),
    "memory_fast": lambda db, acc: _any(db, acc, "memory", lambda p: (p.get("moves") or 99) <= 8),
    "typing_fast": lambda db, acc: _any(db, acc, "typing",
                                        lambda p: (p.get("wpm") or 0) >= 30 and (p.get("accuracy") or 0) >= 90),
    "battle_wins": lambda db, acc: db.query(func.count(MinarBattle.id)).filter(
        MinarBattle.winner_account_id == acc.id, MinarBattle.status == "finished").scalar() or 0,
    "lessons": lambda db, acc: db.query(func.count(MinarLesson.id)).filter(
        MinarLesson.account_id == acc.id).scalar() or 0,
    "level": lambda db, acc: C.level_of(acc.xp),
    "earned": _earned,
    "tournament_podium": lambda db, acc: db.query(func.count(MinarTournamentAward.id)).filter(
        MinarTournamentAward.account_id == acc.id).scalar() or 0,
    "tournament_wins": lambda db, acc: db.query(func.count(MinarTournamentAward.id)).filter(
        MinarTournamentAward.account_id == acc.id, MinarTournamentAward.place == 1).scalar() or 0,
    "code_solved": lambda db, acc: db.query(func.count(MinarPlaygroundSolve.id)).filter(
        MinarPlaygroundSolve.account_id == acc.id).scalar() or 0,
    "homework_done": lambda db, acc: db.query(func.count(models.HomeworkSubmission.id)).filter(
        models.HomeworkSubmission.student_id == acc.student_id,
        models.HomeworkSubmission.status.in_(("submitted", "graded")),
        models.HomeworkSubmission.answer.isnot(None)).scalar() or 0,
    "homework_excellent": lambda db, acc: db.query(func.count(models.HomeworkSubmission.id)).filter(
        models.HomeworkSubmission.student_id == acc.student_id,
        models.HomeworkSubmission.status == "graded", models.HomeworkSubmission.grade >= 90).scalar() or 0,
}


def _unlocked(db: Session, acc: MinarAccount) -> dict[str, datetime]:
    return dict(db.query(MinarAchievement.code, MinarAchievement.unlocked_at)
                .filter(MinarAchievement.account_id == acc.id).all())


def _values(db: Session, acc: MinarAccount, metrics: set[str]) -> dict[str, int]:
    return {m: int(METRICS[m](db, acc)) for m in metrics if m in METRICS}


def _public(a: Achievement, progress: int, unlocked_at: datetime | None) -> dict:
    return {"id": a.code, "title": a.title, "description": a.description, "icon": a.icon,
            "target": a.target, "progress": min(progress, a.target), "reward": a.reward,
            "unlockedAt": tz.isoformat(unlocked_at) if unlocked_at else None}


def evaluate(db: Session, acc: MinarAccount) -> list[dict]:
    """Shart bajarilgan, hali ochilmagan yutuqlarni ochadi (commit qilmaydi). Yangi ochilganlar ro'yxati."""
    done = _unlocked(db, acc)
    pending = [a for a in CATALOG if a.code not in done]
    if not pending:
        return []
    values = _values(db, acc, {a.metric for a in pending})
    now, today = datetime.utcnow(), tz.today().isoformat()
    new = []
    for a in pending:
        if values.get(a.metric, 0) < a.target:
            continue
        db.add(MinarAchievement(account_id=acc.id, code=a.code, unlocked_at=now))
        if a.reward:
            db.add(MinarLedger(account_id=acc.id, ref_key=f"achievement:{a.code}", kind="achievement",
                               title=f"Yutuq: {a.title}", amount=a.reward, local_date=today, created_at=now))
        notify.to_account(db, acc.id, "achievement", f"Yangi yutuq: {a.title} 🏅",
                          f"{a.description} +{a.reward} coin." if a.reward else a.description, "achievements")
        new.append(_public(a, values[a.metric], now))
    return new


def progress(db: Session, acc: MinarAccount) -> list[dict]:
    done = _unlocked(db, acc)
    values = _values(db, acc, {a.metric for a in CATALOG if a.code not in done})
    return [_public(a, a.target if a.code in done else values.get(a.metric, 0), done.get(a.code))
            for a in CATALOG]
