"""O'yinlar olami: sessiya (kontent seed'dan), javob/karta tekshiruvi va natijani serverda hisoblash.

Mijoz endi "score: 5" deb yubora olmaydi:
* Quiz / Bug Hunter — har bir javob `answer` orqali birinchi urinishdayoq serverda yoziladi.
* Memory — kartalar joylashuvi faqat serverda; har bir karta `flip` orqali ochiladi.
* Typing — server o'z so'zlari bilan yozilgan matnni solishtiradi.
* ZType — urilgan asteroidlar ketma-ketlikdagi indekslar sifatida tekshiriladi.
"""
from __future__ import annotations

import json
import random
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from . import catalog as C
from . import game_bank as bank
from .errors import MinarError
from .models import MinarAccount, MinarGameSession

GAMES = ("typing", "ztype", "quiz", "memory", "bug")
QUIZ_COUNT = 5
BUG_COUNT = 3
MEMORY_PAIRS = 6
MEMORY_MAX_MOVES = 18
TYPING_DURATIONS = (10, 15, 20, 25, 30, 60)
TYPING_WORDS_SECONDS = 300  # "so'zlar" rejimi (10–100 so'z): vaqt cheklovi faqat yuqori chegara
TYPING_WORDS_COUNT = 300
TYPING_DIFFICULTIES = ("easy", "normal")
ZTYPE_DIFFICULTIES = ("easy", "normal", "hard")
ZTYPE_SECONDS = 60
SESSION_TTL = timedelta(minutes=30)
TIME_SLACK = 3  # soniya: tarmoq kechikishi uchun

GOAL_HINT = {
    "typing": "Mukofot uchun kamida 15 ta harfni 80% aniqlikda yoz.",
    "ztype": "Mukofot uchun kamida 5 ta asteroidni to‘xtat.",
    "quiz": "Mukofot uchun kamida 3 ta to‘g‘ri javob kerak.",
    "memory": f"Mukofot uchun barcha juftliklarni {MEMORY_MAX_MOVES} urinish ichida top.",
    "bug": "Mukofot uchun kamida 2 ta xatoni top.",
}
BAD_RESULT = "Natija tekshiruvdan o‘tmadi."


# ── Kontent (seed'dan deterministik) ────────────────────────────────────────

def _course(acc: MinarAccount) -> str:
    return acc.course if acc.course in C.COURSES else C.COURSES[0]


def questions(game: str, course: str, seed: int) -> list[dict]:
    rng = random.Random(seed)
    items = (bank.QUIZ if game == "quiz" else bank.BUG)[course]
    out = []
    for i in rng.sample(range(len(items)), QUIZ_COUNT if game == "quiz" else BUG_COUNT):
        if game == "quiz":
            (q, opts, explain), code = items[i], None
        else:
            code, q, opts, explain = items[i]
        perm = rng.sample(range(len(opts)), len(opts))
        out.append({"q": q, "code": code, "options": [opts[p] for p in perm],
                    "answer": perm.index(0), "explain": explain})
    return out


def _sequence(rng: random.Random, pool: list[str], n: int) -> list[str]:
    out: list[str] = []
    while len(out) < n:
        w = rng.choice(pool)
        if not out or out[-1] != w:
            out.append(w)
    return out


def typing_words(course: str, difficulty: str, seed: int) -> list[str]:
    return _sequence(random.Random(seed), bank.TYPING_WORDS[course][difficulty], TYPING_WORDS_COUNT)


def ztype_words(course: str, seed: int) -> list[str]:
    return _sequence(random.Random(seed), bank.ZTYPE_WORDS[course], 200)


def memory_cards(course: str, seed: int) -> list[str]:
    rng = random.Random(seed)
    cards = rng.sample(bank.MEMORY_CARDS[course], MEMORY_PAIRS) * 2
    rng.shuffle(cards)
    return cards


def typing_stats(words: list[str], typed: str) -> dict:
    """So'zma-so'z solishtirish (bitta harf tushib qolsa, keyingi so'zlar xato bo'lib ketmaydi).
    Frontend `typingStats` aynan shu qoidani takrorlaydi."""
    tokens = typed.split(" ")
    done, last = tokens[:-1], tokens[-1]
    correct = good = attempted = 0
    for i, t in enumerate(done[:len(words)]):
        attempted += 1
        if t == words[i]:
            good += 1
            correct += len(t) + 1
    if last and len(done) < len(words):
        target = words[len(done)]
        if last == target:
            attempted += 1
            good += 1
            correct += len(last)
        elif not target.startswith(last):
            attempted += 1
    accuracy = round(good / attempted * 100) if attempted else 0
    return {"correct": correct, "words": good, "accuracy": accuracy}


# ── Sessiya ─────────────────────────────────────────────────────────────────

def _state(s: MinarGameSession) -> dict:
    try:
        return json.loads(s.state or "{}")
    except ValueError:
        return {}


def _int(v: Any, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
        raise MinarError(400, BAD_RESULT)
    return v


def public_session(s: MinarGameSession) -> dict:
    out = {"id": s.id, "game": s.game, "course": s.course, "difficulty": s.difficulty, "duration": s.duration}
    if s.game in ("quiz", "bug"):
        out["questions"] = [{"q": q["q"], "code": q["code"], "options": q["options"]}
                            for q in questions(s.game, s.course, s.seed)]
    elif s.game == "typing":
        out["words"] = typing_words(s.course, s.difficulty, s.seed)
    elif s.game == "ztype":
        out["words"] = ztype_words(s.course, s.seed)
    else:
        out["cards"] = len(memory_cards(s.course, s.seed))
        out["maxMoves"] = MEMORY_MAX_MOVES
    return out


def start(db: Session, acc: MinarAccount, payload: dict) -> dict:
    game = payload.get("game")
    if game not in GAMES:
        raise MinarError(400, "O‘yin topilmadi.")
    difficulty = duration = None
    if game == "typing":
        difficulty = payload.get("difficulty") or "easy"
        duration = TYPING_WORDS_SECONDS if payload.get("mode") == "words" else payload.get("duration") or 30
        if difficulty not in TYPING_DIFFICULTIES or duration not in (*TYPING_DURATIONS, TYPING_WORDS_SECONDS):
            raise MinarError(400, "O‘yin sozlamasi noto‘g‘ri.")
    elif game == "ztype":
        difficulty = payload.get("difficulty") or "easy"
        duration = ZTYPE_SECONDS
        if difficulty not in ZTYPE_DIFFICULTIES:
            raise MinarError(400, "O‘yin sozlamasi noto‘g‘ri.")
    need = C.UNLOCK_LEVEL.get(f"{game}:{difficulty}", 1)
    if C.level_of(acc.xp) < need:
        raise MinarError(403, f"Bu qiyinlik {need}-darajada ochiladi.")
    now = datetime.utcnow()
    db.query(MinarGameSession).filter(MinarGameSession.account_id == acc.id,
                                      MinarGameSession.started_at < now - timedelta(days=1)).delete()
    s = MinarGameSession(id=uuid.uuid4().hex, account_id=acc.id, game=game, course=_course(acc),
                         difficulty=difficulty, duration=duration, seed=secrets.randbits(31),
                         state="{}", started_at=now)
    db.add(s)
    db.commit()
    return public_session(s)


def load(db: Session, acc: MinarAccount, sid: Any, games: tuple[str, ...] = GAMES) -> MinarGameSession:
    if not isinstance(sid, str) or not (8 <= len(sid) <= 64):
        raise MinarError(400, "O‘yin topilmadi. Qaytadan boshla.")
    s = db.query(MinarGameSession).filter(MinarGameSession.id == sid, MinarGameSession.account_id == acc.id) \
        .with_for_update().first()
    if not s or s.game not in games:
        raise MinarError(404, "O‘yin topilmadi. Qaytadan boshla.")
    return s


def _open(db: Session, acc: MinarAccount, sid: Any, games: tuple[str, ...]) -> MinarGameSession:
    s = load(db, acc, sid, games)
    if s.finished_at:
        raise MinarError(409, "Bu o‘yin yakunlangan.")
    if datetime.utcnow() - s.started_at > SESSION_TTL:
        raise MinarError(410, "O‘yin vaqti tugadi. Qaytadan boshla.")
    return s


def answer(db: Session, acc: MinarAccount, payload: dict) -> dict:
    s = _open(db, acc, payload.get("session"), ("quiz", "bug"))
    st = _state(s)
    answers = st.get("answers", [])
    qs = questions(s.game, s.course, s.seed)
    index = _int(payload.get("index"), 0, len(qs) - 1)
    if index != len(answers):
        raise MinarError(409, "Bu savolga javob berilgan.")
    q = qs[index]
    choice = _int(payload.get("choice"), 0, len(q["options"]) - 1)
    answers.append(choice)
    s.state = json.dumps({**st, "answers": answers})
    db.commit()
    return {"correct": choice == q["answer"], "answer": q["answer"], "explain": q["explain"]}


def flip(db: Session, acc: MinarAccount, payload: dict) -> dict:
    s = _open(db, acc, payload.get("session"), ("memory",))
    cards = memory_cards(s.course, s.seed)
    card = _int(payload.get("card"), 0, len(cards) - 1)
    st = _state(s)
    opened, matched, moves = st.get("open", []), st.get("matched", []), st.get("moves", 0)
    if moves >= MEMORY_MAX_MOVES:
        raise MinarError(409, "Urinishlar tugadi.")
    if card in opened or cards[card] in matched:
        raise MinarError(400, "Bu karta ochiq.")
    out: dict = {"card": card, "value": cards[card]}
    if not opened:
        opened = [card]
    else:
        first = opened[0]
        moves += 1
        out["pair"] = [first, card]
        out["match"] = cards[first] == cards[card]
        if out["match"]:
            matched.append(cards[card])
        opened = []
    s.state = json.dumps({"open": opened, "matched": matched, "moves": moves})
    db.commit()
    return {**out, "moves": moves, "matched": len(matched)}


def finish(s: MinarGameSession, result: dict) -> tuple[dict, bool]:
    """Sessiya va mijoz yuborgan xom ma'lumotdan natijani hisoblaydi: (saqlanadigan maydonlar, yutuq sharti)."""
    if datetime.utcnow() - s.started_at > SESSION_TTL:
        raise MinarError(410, "O‘yin vaqti tugadi. Qaytadan boshla.")
    elapsed = (datetime.utcnow() - s.started_at).total_seconds()
    st = _state(s)
    if s.game in ("quiz", "bug"):
        qs = questions(s.game, s.course, s.seed)
        answers = st.get("answers", [])
        if len(answers) != len(qs):
            raise MinarError(400, "Avval barcha savollarga javob ber.")
        score = sum(1 for q, a in zip(qs, answers) if q["answer"] == a)
        return {"score": score, "total": len(qs)}, score >= (3 if s.game == "quiz" else 2)
    if s.game == "memory":
        score, moves = len(st.get("matched", [])), st.get("moves", 0)
        return ({"score": score, "moves": moves, "maxMoves": MEMORY_MAX_MOVES},
                score == MEMORY_PAIRS and moves <= MEMORY_MAX_MOVES)
    duration = _int(result.get("duration"), 1, s.duration)
    if elapsed + TIME_SLACK < duration:
        raise MinarError(400, BAD_RESULT)
    if s.game == "typing":
        typed = result.get("typed")
        if not isinstance(typed, str) or len(typed) > 3000:
            raise MinarError(400, BAD_RESULT)
        stats = typing_stats(typing_words(s.course, s.difficulty, s.seed), typed)
        if stats["correct"] > duration * 15 + 15:                 # 15 belgi/soniyadan tez emas
            raise MinarError(400, BAD_RESULT)
        wpm = round(stats["correct"] / 5 / (duration / 60))
        return ({"correct": stats["correct"], "accuracy": stats["accuracy"], "wpm": wpm, "duration": duration,
                 "score": stats["correct"], "words": stats["words"]},
                stats["correct"] >= 15 and stats["accuracy"] >= 80)
    # ztype
    hits = result.get("hits")
    words = ztype_words(s.course, s.seed)
    if not isinstance(hits, list) or len(hits) > duration * 2 + 2:
        raise MinarError(400, BAD_RESULT)
    seen = {_int(h, 0, min(len(words) - 1, duration * 2 + 5)) for h in hits}
    if len(seen) != len(hits):
        raise MinarError(400, BAD_RESULT)
    return {"score": len(hits), "duration": duration}, len(hits) >= 5
