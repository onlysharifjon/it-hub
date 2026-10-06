"""Provayder → server callback'lari (mobil ilova chaqirmaydi).

nginx orqali tashqi manzillar (PUBLIC_BASE_URL + /api):
  POST /api/payment-callbacks/payme
  POST /api/payment-callbacks/click/prepare
  POST /api/payment-callbacks/click/complete
  POST /api/payment-callbacks/uzum/{check|create|confirm|reverse|status}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...database import get_db
from . import click, payme, uzum

router = APIRouter(prefix="/payment-callbacks", tags=["payment-callbacks"], include_in_schema=False)


@router.post("/payme")
async def payme_callback(request: Request, db: Session = Depends(get_db)):
    return await payme.handle(request, db)


@router.post("/click/prepare")
async def click_prepare(request: Request, db: Session = Depends(get_db)):
    return await click.handle(request, db, action=0)


@router.post("/click/complete")
async def click_complete(request: Request, db: Session = Depends(get_db)):
    return await click.handle(request, db, action=1)


@router.post("/uzum/{operation}")
async def uzum_callback(operation: str, request: Request, db: Session = Depends(get_db)):
    return await uzum.handle(request, db, operation)
