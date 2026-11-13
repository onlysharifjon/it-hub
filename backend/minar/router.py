"""O'quvchi ilovasi endpointlari (frontend shartnomasi — API-CONTRACT.md).

Ommaviy manzil: https://space.minaracademy.uz/api/...  (nginx `/api/` -> shu router, prefiks `/space`).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, Request, Response, WebSocket
from sqlalchemy.orm import Session

from ..database import get_db
from . import assistant, auth, battles, games, learning, notify, playground, service, weekly
from .errors import MinarError
from .models import MinarAccount

router = APIRouter()
Account = Depends(auth.current_account)


@router.get('/coins/status')
def coin_status(response: Response, db: Session = Depends(get_db)):
    from ..coin_launch import phase
    response.headers['Cache-Control'] = 'no-store'
    return phase(db)


# ── Auth ────────────────────────────────────────────────────────────────────

@router.post("/auth/login")
def login(request: Request, response: Response, payload: dict = Body(...), db: Session = Depends(get_db)):
    auth.check_origin(request)
    student_id = payload.get("studentId")
    password = payload.get("password")
    if not isinstance(student_id, (str, int)) or not isinstance(password, str):
        raise MinarError(400, "ID va parolni kiriting.")
    auth.login(db, request, response, str(student_id), password)
    return {"ok": True}


@router.post("/auth/qr")
def login_qr(request: Request, response: Response, payload: dict = Body(...), db: Session = Depends(get_db)):
    auth.check_origin(request)
    auth.qr_login(db, request, response, payload.get("token"))
    return {"ok": True, "canSetWithoutCurrent": True}


@router.get("/auth/password")
def password_status(request: Request, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return auth.password_status(db, request)


@router.post("/auth/password")
def change_password(request: Request, payload: dict = Body(...), acc: MinarAccount = Account,
                    db: Session = Depends(get_db)):
    auth.change_password(db, request, acc, payload.get("current"), payload.get("new"))
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth.check_origin(request)
    auth.logout(db, request, response)
    return {"ok": True}


@router.get("/students/me/bootstrap")
def bootstrap(acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.build_state(db, acc)


# ── Holatni o'zgartiruvchi amallar (javob: {state, award, message}) ─────────

@router.post("/rewards/check-in")
def check_in(acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_checkin)


@router.post("/shop/purchases")
def purchase(payload: dict = Body(...), idempotency_key: Optional[str] = Header(None),
             acc: MinarAccount = Account, db: Session = Depends(get_db)):
    request_id = payload.get("requestId") or idempotency_key
    return service.run(db, acc, service.act_purchase, payload.get("productId"), request_id)


@router.post("/avatar/equipment")
def equip(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_equip, payload.get("productId"))


@router.post("/avatar/character")
def character(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_character, payload.get("character"))


@router.post("/courses/complete")
def complete_lesson(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    raise MinarError(410, 'Eski kurs mashqlari yopildi. Kurslarim bo‘limida guruh mavzularini oching.')


@router.post("/games/results")
def game_result(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_game, payload.get("result"))


@router.post("/games/start")
def game_start(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return games.start(db, acc, payload)


@router.post("/games/answer")
def game_answer(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return games.answer(db, acc, payload)


@router.post("/games/flip")
def game_flip(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return games.flip(db, acc, payload)


@router.get("/curriculum")
def curriculum(acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return learning.curriculum(db, acc)


@router.get("/homework")
def homework(offset: int = 0, status: str = "all", acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return learning.homework_list(db, acc, offset, status)


@router.post("/homework/{homework_id}/submit")
def homework_submit(homework_id: int, payload: dict = Body(...), acc: MinarAccount = Account,
                    db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_homework, homework_id, payload)


@router.get("/playground")
def playground_tasks(acc: MinarAccount = Account, db: Session = Depends(get_db)):
    raise MinarError(410, 'Kod maydoni yopildi. Kurslarim bo‘limida guruh mavzularini oching.')


@router.post("/playground/{task_id}/check")
def playground_check(task_id: str, payload: dict = Body(...), acc: MinarAccount = Account,
                     db: Session = Depends(get_db)):
    raise MinarError(410, 'Kod maydoni yopildi. Kurslarim bo‘limida guruh mavzularini oching.')


@router.get("/tournament")
def tournament(acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return weekly.standings(db, acc)


@router.get("/notifications")
def notifications(before: int = 0, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return notify.list_for(db, acc, before)


@router.post("/notifications/read")
def notifications_read(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return notify.mark_read(db, acc, payload.get("ids"))


@router.post("/quests/claim")
def claim_quest(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_quest, payload.get("quest"))


# ── Reyting, AI ─────────────────────────────────────────────────────────────

@router.get("/leaderboard")
def leaderboard(metric: str = "coins", period: str = "week", course: str = "all",
                acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.leaderboard(db, acc, metric, period, course)


@router.post("/assistant/messages")
def assistant_messages(payload: dict = Body(...), acc: MinarAccount = Account):
    return assistant.reply(acc, payload.get("messages"))


# ── Battle ──────────────────────────────────────────────────────────────────

@router.post("/battles")
def create_battle(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return battles.create_room(db, acc, payload.get("mode"))


@router.post("/battles/{code}/join")
def join_battle(code: str, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return battles.join_room(db, acc, code)


@router.websocket("/battles")
async def battle_socket(ws: WebSocket):
    await battles.handle(ws)


@router.post("/games/hit")
def game_hit(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return games.hit(db, acc, payload)


@router.get('/history')
def coin_history(offset: int = 0, month: Optional[str] = None, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    from .history import listing
    return listing(db, acc, offset, month)


@router.post('/playground/run')
def playground_run(payload: dict = Body(...), acc: MinarAccount = Account):
    raise MinarError(410, 'Kod maydoni yopildi. Kurslarim bo‘limida guruh mavzularini oching.')

@router.get('/game-history')
def game_history(offset:int=0,month:Optional[str]=None,acc:MinarAccount=Account,db:Session=Depends(get_db)):
    from .history import game_listing
    return game_listing(db,acc,offset,month)

@router.get('/attendance-history')
def attendance_history(offset:int=0,month:Optional[str]=None,acc:MinarAccount=Account,db:Session=Depends(get_db)):
    from .history import attendance_listing
    return attendance_listing(db,acc,month,offset)

@router.get('/profiles/{login_id}')
def student_public_profile(login_id: str, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.public_profile(db, acc, login_id)


# Durable student game rooms (CSRF checked by current_account for all POSTs).
from . import tables

@router.get('/tables')
def table_list(game: str, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return tables.listing(db, acc, game)

@router.post('/tables')
def table_create(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return tables.create(db, acc, payload)

@router.get('/tables/servers')
def table_servers(game: Optional[str] = None, offset: int = 0, limit: int = 30,
                  acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return tables.servers(db, acc, game, offset, limit)

@router.post('/tables/{code}/join')
def table_join(code: str, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return tables.join(db, acc, code)

@router.get('/tables/{code}')
def table_get(code: str, acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return tables.get(db, acc, code)

@router.post('/tables/{code}/actions')
def table_action(code: str, payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return tables.act(db, acc, code, payload)
