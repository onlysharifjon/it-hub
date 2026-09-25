"""Battle arena: xona yaratish/qo'shilish (REST) va jonli bellashuv (WebSocket).

Protokol — `minar-academy/API-CONTRACT.md` §7. Server hakam:
  * start vaqti, matchId, natija va g'olib serverda aniqlanadi (client `won` ga ishonilmaydi);
  * typing: `typed` matni serverdagi `BATTLE_TEXT` bilan solishtiriladi, yozish tezligi chegaralanadi;
  * quiz: javob indeksi serverdagi to'g'ri javoblar bilan solishtiriladi;
  * server yuborgan barcha xabarlarda `sender: "server"` (frontend o'z `sender`ini e'tiborsiz qoldiradi).

Xonalar xotirada saqlanadi => faqat bitta jarayon bilan ishlaydi (Docker: `space-api`, 1 replika;
deploy `/healthz` dagi `rooms` nolga tushishini kutadi — o'yin o'rtasida qayta ishga tushirilmaydi). G'alaba natijasi
bazaga (`minar_battles`) yoziladi va `/games/results` mukofoti shuni tekshiradi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import WebSocket
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models, security
from ..database import SessionLocal
from . import catalog as C
from .auth import origin_allowed
from .errors import MinarError
from .models import MinarAccount, MinarBattle

log = logging.getLogger("minar.battles")

TICKET_TTL = 120                     # soniya
ROOM_TTL = timedelta(minutes=30)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
WS_URL = os.getenv("MINAR_WS_URL", "wss://space.minaracademy.uz/api/space/battles")
GRACE = 6                            # soniya: taymerdan keyingi ortiqcha kutish
MAX_TYPE_CPS = 18                    # belgi/soniya (yuqori chegara)
IDLE_TIMEOUT = 45                    # klient har 3 soniyada ping yuboradi


# ── REST ────────────────────────────────────────────────────────────────────

def _ticket(acc: MinarAccount, battle: MinarBattle, role: str) -> str:
    # `sub` claim ataylab yo'q: bu token CRM xodim JWT'si sifatida ishlamaydi.
    return jwt.encode(
        {"typ": "minar-battle", "acc": acc.id, "room": battle.room_id, "role": role,
         "exp": datetime.utcnow() + timedelta(seconds=TICKET_TTL)},
        security.SECRET_KEY, algorithm=security.ALGORITHM,
    )


def _payload(acc: MinarAccount, battle: MinarBattle, role: str) -> dict:
    return {"code": battle.code, "roomId": battle.room_id, "ticket": _ticket(acc, battle, role), "wsUrl": WS_URL}


def create_room(db: Session, acc: MinarAccount, mode: object) -> dict:
    if mode not in ("typing", "quiz"):
        raise MinarError(400, "O‘yin turi noto‘g‘ri.")
    if not security.rate_limit_ok(f"minar-battle-create:{acc.id}", limit=10, window=60):
        raise MinarError(429, "Juda tez-tez xona yaratyapsan. Bir daqiqa kut.")
    now = datetime.utcnow()
    db.query(MinarBattle).filter(
        MinarBattle.status.in_(("waiting", "ready")),
        (MinarBattle.host_account_id == acc.id) | (MinarBattle.created_at < now - ROOM_TTL),
    ).update({"status": "abandoned"}, synchronize_session=False)
    for _ in range(8):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not db.query(MinarBattle.id).filter(MinarBattle.code == code).first():
            break
    else:
        raise MinarError(503, "Xona yaratib bo‘lmadi. Qayta urinib ko‘r.")
    battle = MinarBattle(
        code=code, room_id=str(uuid.uuid4()), mode=mode, course=acc.course,
        host_account_id=acc.id, status="waiting", created_at=now,
    )
    db.add(battle)
    db.commit()
    return _payload(acc, battle, "host")


def join_room(db: Session, acc: MinarAccount, code: str) -> dict:
    if not security.rate_limit_ok(f"minar-battle-join:{acc.id}", limit=20, window=60):
        raise MinarError(429, "Juda ko‘p urinish. Bir daqiqa kut.")
    code = re.sub(r"[^A-Z0-9]", "", (code or "").upper())[:12]
    battle = db.query(MinarBattle).filter(MinarBattle.code == code).first()
    if (not battle or battle.status not in ("waiting", "ready")
            or battle.created_at < datetime.utcnow() - ROOM_TTL):
        raise MinarError(404, "Xona topilmadi. Kodni tekshir.")
    if battle.host_account_id == acc.id:
        raise MinarError(400, "O‘z xonangga qo‘shila olmaysan. Kodni do‘stingga ber.")
    if battle.guest_account_id and battle.guest_account_id != acc.id:
        raise MinarError(409, "Bu xona to‘lgan. Boshqa kodni sinab ko‘r.")
    battle.guest_account_id = acc.id
    battle.status = "ready"
    db.commit()
    return _payload(acc, battle, "guest")


# ── WebSocket: xona holati ──────────────────────────────────────────────────

class Conn:
    def __init__(self, ws: WebSocket, sender: str, name: str, account_id: int, login_id: str, role: str):
        self.ws, self.sender, self.name = ws, sender, name
        self.account_id, self.login_id, self.role = account_id, login_id, role
        self.replaced = False
        self.window_start, self.window_count = time.monotonic(), 0


class Prog:
    def __init__(self):
        self.score, self.progress, self.done, self.done_at = 0, 0.0, False, 0
        self.answers: list[int] = []
        self.last_answer_ms = 0


class Room:
    def __init__(self, info: dict):
        self.id, self.code, self.mode, self.course = info["room_id"], info["code"], info["mode"], info["course"]
        self.host: Optional[Conn] = None
        self.guest: Optional[Conn] = None
        self.state = "waiting"            # waiting | ready | playing | done | closed
        self.paired = False
        self.match_id = ""
        self.start_ms = 0
        self.prog = {"host": Prog(), "guest": Prog()}
        self.finished: set[str] = set()
        self.timer: Optional[asyncio.Task] = None

    def conn(self, role: str) -> Optional[Conn]:
        return self.host if role == "host" else self.guest

    def peer(self, conn: Conn) -> Optional[Conn]:
        return self.guest if conn.role == "host" else self.host


ROOMS: dict[str, Room] = {}


async def _send(conn: Optional[Conn], payload: dict) -> None:
    if not conn:
        return
    try:
        await conn.ws.send_text(json.dumps(payload))
    except Exception:
        pass


async def _close(conn: Optional[Conn], code: int = 1000) -> None:
    if not conn:
        return
    try:
        await conn.ws.close(code)
    except Exception:
        pass


def _db_update(room_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        db.query(MinarBattle).filter(MinarBattle.room_id == room_id).update(fields)
        db.commit()
    finally:
        db.close()


def _load_participant(claims: dict) -> Optional[dict]:
    db = SessionLocal()
    try:
        b = db.query(MinarBattle).filter(MinarBattle.room_id == claims.get("room")).first()
        if not b or b.status not in ("waiting", "ready"):
            return None
        role, acc_id = claims.get("role"), claims.get("acc")
        expected = b.host_account_id if role == "host" else b.guest_account_id if role == "guest" else None
        if expected is None or expected != acc_id:
            return None
        acc = db.query(MinarAccount).filter(MinarAccount.id == acc_id, MinarAccount.is_active.is_(True)).first()
        student = acc and db.query(models.Student).filter(models.Student.id == acc.student_id).first()
        if not acc or not student or not student.is_active or student.is_archived:
            return None
        return {"room_id": b.room_id, "code": b.code, "mode": b.mode, "course": b.course,
                "name": (student.full_name or "O‘quvchi").split()[0], "account_id": acc.id, "login_id": acc.login_id,
                "role": role}
    finally:
        db.close()


def _decode_ticket(token: object) -> Optional[dict]:
    if not isinstance(token, str):
        return None
    try:
        claims = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    except JWTError:
        return None
    return claims if claims.get("typ") == "minar-battle" else None


# ── Oqim ────────────────────────────────────────────────────────────────────

async def _reject(ws: WebSocket) -> None:
    """Ulanishni rad etadi. Klient allaqachon uzilgan bo'lsa (`close` ikkinchi marta
    yuborilsa) Starlette RuntimeError beradi — bu kutilgan holat, log'ga traceback kerak emas."""
    try:
        await ws.close(1008)
    except Exception:
        pass


def active_rooms() -> int:
    """Hozir o'ynalayotgan yoki juftlangan xonalar soni (deploy oldidan kutish uchun)."""
    return sum(1 for r in ROOMS.values() if r.state in ("ready", "playing"))


async def handle(ws: WebSocket) -> None:
    await ws.accept()
    if not origin_allowed(ws.headers.get("origin")):
        await _reject(ws)
        return
    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10)
        msg = json.loads(first)
    except Exception:
        await _reject(ws)
        return
    claims = _decode_ticket(msg.get("ticket")) if isinstance(msg, dict) and msg.get("type") == "join" else None
    sender = str(msg.get("sender") or "")[:64] if isinstance(msg, dict) else ""
    if not claims or not sender or msg.get("roomId") != claims.get("room"):
        await _reject(ws)
        return
    info = await run_in_threadpool(_load_participant, claims)
    if not info:
        await _reject(ws)
        return

    room = ROOMS.setdefault(info["room_id"], Room(info))
    if room.state in ("playing", "done", "closed"):
        await _reject(ws)
        return
    conn = Conn(ws, sender, info["name"], info["account_id"], info["login_id"], info["role"])
    old = room.conn(conn.role)
    if old is not None:                       # xuddi shu akkaunt qayta ulandi — eskisini almashtiramiz
        old.replaced = True
        await _close(old, 1000)
    if conn.role == "host":
        room.host = conn
    else:
        room.guest = conn
    room.paired = False
    await _maybe_pair(room)

    try:
        while True:
            event = await asyncio.wait_for(ws.receive(), timeout=IDLE_TIMEOUT)
            if event["type"] == "websocket.disconnect":
                break
            raw = event.get("text")
            if not raw or len(raw) > 4000:
                continue
            now = time.monotonic()
            if now - conn.window_start > 1:
                conn.window_start, conn.window_count = now, 0
            conn.window_count += 1
            if conn.window_count > 40:        # soniyasiga 40 dan ko'p xabar — suiiste'mol
                break
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            if isinstance(m, dict) and await _on_message(room, conn, m):
                break
    except (asyncio.TimeoutError, RuntimeError):
        pass
    finally:
        # Tozalash alohida vazifada: handler bekor qilinsa ham (server to'xtashi, ulanish uzilishi)
        # holat bazaga yoziladi va raqibga `leave` yetkaziladi.
        _spawn(_on_disconnect(room, conn))


_BACKGROUND: set = set()


def _spawn(coro) -> None:
    task = asyncio.ensure_future(coro)
    _BACKGROUND.add(task)                    # havola saqlanadi — vazifa axlat yig'uvchi tomonidan o'chirilmasin
    task.add_done_callback(_BACKGROUND.discard)


async def _maybe_pair(room: Room) -> None:
    if room.paired or not room.host or not room.guest or room.state not in ("waiting", "ready"):
        return
    room.paired = True
    room.state = "ready"
    await _send(room.guest, {"type": "welcome", "sender": room.host.sender, "target": room.guest.sender,
                             "name": room.host.name, "mode": room.mode, "course": room.course})
    await _send(room.host, {"type": "join", "sender": room.guest.sender, "name": room.guest.name,
                            "roomId": room.id})
    await run_in_threadpool(_db_update, room.id, status="ready")


async def _on_message(room: Room, conn: Conn, m: dict) -> bool:
    """True qaytarsa — ulanish yopiladi."""
    t = m.get("type")
    if t == "ping":
        await _send(room.peer(conn), {"type": "ping", "sender": conn.sender})
    elif t == "start":
        await _start(room, conn)
    elif t == "progress":
        await _progress(room, conn, m)
    elif t == "finish":
        await _finish(room, conn)
    elif t == "leave":
        return True
    return False


async def _start(room: Room, conn: Conn) -> None:
    if conn.role != "host" or room.state != "ready" or not room.host or not room.guest:
        return
    room.state = "playing"
    room.match_id = str(uuid.uuid4())
    room.start_ms = int(time.time() * 1000) + 1000
    payload = {"type": "start", "sender": "server", "at": room.start_ms, "mode": room.mode,
               "course": room.course, "matchId": room.match_id}
    await _send(room.host, payload)
    await _send(room.guest, payload)
    await run_in_threadpool(_db_update, room.id, status="playing", match_id=room.match_id,
                            started_at=datetime.utcnow())
    room.timer = asyncio.create_task(_timeout(room))


async def _timeout(room: Room) -> None:
    try:
        await asyncio.sleep(C.BATTLE_SECONDS + GRACE + 1)
    except asyncio.CancelledError:
        return
    await _finalize(room)


def _elapsed(room: Room) -> float:
    return (time.time() * 1000 - room.start_ms) / 1000


async def _progress(room: Room, conn: Conn, m: dict) -> None:
    if room.state != "playing" or m.get("matchId") != room.match_id:
        return
    elapsed = _elapsed(room)
    p = room.prog[conn.role]
    if p.done or elapsed < -1 or elapsed > C.BATTLE_SECONDS + GRACE:
        return
    now_ms = int(time.time() * 1000)
    if room.mode == "typing":
        typed = m.get("typed")
        if not isinstance(typed, str) or len(typed) > len(C.BATTLE_TEXT) + 5:
            return
        if len(typed) > MAX_TYPE_CPS * max(elapsed, 0) + 12:
            return                                   # inson yoza olmaydigan tezlik
        correct = sum(1 for a, b in zip(typed, C.BATTLE_TEXT) if a == b)
        p.score, p.progress = correct, correct / len(C.BATTLE_TEXT) * 100
        p.done = typed == C.BATTLE_TEXT
    else:
        qi, ai = m.get("questionIndex"), m.get("answerIndex")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (qi, ai)):
            return
        if qi != len(p.answers) or not (0 <= qi < C.QUIZ_TOTAL) or not (0 <= ai <= 3):
            return
        if now_ms - max(p.last_answer_ms, room.start_ms) < 300:
            return                                   # savolni o'qishga ham ulgurmaydigan tezlik
        p.last_answer_ms = now_ms
        p.answers.append(ai)
        if ai == C.QUIZ_ANSWERS[room.course][qi]:
            p.score += 1
        p.progress = len(p.answers) / C.QUIZ_TOTAL * 100
        p.done = len(p.answers) == C.QUIZ_TOTAL
    if p.done:
        p.done_at = now_ms
    await _send(room.peer(conn), {"type": "progress", "sender": conn.sender, "progress": p.progress,
                                  "score": p.score, "done": p.done, "matchId": room.match_id})
    if p.done and (room.mode == "typing" or all(x.done for x in room.prog.values())):
        await _finalize(room)


async def _finish(room: Room, conn: Conn) -> None:
    if room.state != "playing":
        return
    p = room.prog[conn.role]
    if not p.done and _elapsed(room) < C.BATTLE_SECONDS - 3:
        return                                       # vaqtidan oldin tugatib bo'lmaydi
    room.finished.add(conn.role)
    if room.finished >= {"host", "guest"}:
        await _finalize(room)


async def _finalize(room: Room) -> None:
    if room.state != "playing":
        return
    room.state = "done"
    if room.timer and room.timer is not asyncio.current_task():
        room.timer.cancel()
    h, g = room.prog["host"], room.prog["guest"]
    if room.mode == "typing" and (h.done or g.done):
        if h.done and g.done and h.done_at != g.done_at:
            winner = "host" if h.done_at < g.done_at else "guest"
        elif h.done and g.done:
            winner = None
        else:
            winner = "host" if h.done else "guest"
    else:
        winner = "host" if h.score > g.score else "guest" if g.score > h.score else None
    win_conn = room.conn(winner) if winner else None
    draw = winner is None
    await run_in_threadpool(
        _db_update, room.id, status="finished", draw=draw, host_score=h.score, guest_score=g.score,
        winner_account_id=win_conn.account_id if win_conn else None, finished_at=datetime.utcnow(),
    )
    result = {"type": "result", "sender": "server", "winnerId": win_conn.login_id if win_conn else None,
              "draw": draw, "matchId": room.match_id, "scores": {"host": h.score, "guest": g.score}}
    await _send(room.host, result)
    await _send(room.guest, result)


async def _on_disconnect(room: Room, conn: Conn) -> None:
    if conn.replaced:
        return
    if room.conn(conn.role) is conn:
        if conn.role == "host":
            room.host = None
        else:
            room.guest = None
    peer = room.peer(conn)
    if room.state == "done":
        if not room.host and not room.guest:
            ROOMS.pop(room.id, None)
        return
    if room.state == "closed":
        return
    closing = room.state == "playing" or conn.role == "host"
    if closing:
        # o'yin o'rtasida yoki xona egasi chiqdi — bellashuv mukofotsiz yopiladi
        room.state = "closed"
        if room.timer and room.timer is not asyncio.current_task():
            room.timer.cancel()
        ROOMS.pop(room.id, None)
        fields = {"status": "abandoned"}
    else:
        # mehmon o'yin boshlanmasdan chiqdi — xona yana bo'sh
        room.paired = False
        room.state = "waiting"
        fields = {"status": "waiting", "guest_account_id": None}
    # Avval bazaga, keyin raqibga xabar.
    try:
        await run_in_threadpool(_db_update, room.id, **fields)
    except Exception:                       # baza xatosi raqibga xabar berishni to'sib qo'ymasin
        log.exception("battle %s: holatni saqlab bo'lmadi", room.id)
    await _send(peer, {"type": "leave", "sender": conn.sender})
    if closing:
        await _close(peer, 1000)
