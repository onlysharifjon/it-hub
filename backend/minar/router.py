"""O'quvchi ilovasi endpointlari (frontend shartnomasi — API-CONTRACT.md).

Ommaviy manzil: https://space.minaracademy.uz/api/...  (nginx `/api/` -> shu router, prefiks `/space`).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, Request, Response, WebSocket
from sqlalchemy.orm import Session

from ..database import get_db
from . import assistant, auth, battles, service
from .errors import MinarError
from .models import MinarAccount

router = APIRouter()
Account = Depends(auth.current_account)


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
    return service.run(db, acc, service.act_lesson, payload.get("index"))


@router.post("/games/results")
def game_result(payload: dict = Body(...), acc: MinarAccount = Account, db: Session = Depends(get_db)):
    return service.run(db, acc, service.act_game, payload.get("result"))


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
