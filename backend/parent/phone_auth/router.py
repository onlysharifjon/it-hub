"""Telefon + Telegram OTP orqali ota-ona login/registratsiyasi (controller).

Tashqi manzillar (nginx /api prefiksi bilan):
  POST /api/auth/phone/request-code
  POST /api/auth/phone/resend-code
  POST /api/auth/phone/verify-code   → parent API token juftligi {access_token, refresh_token}
Gateway logikasi — gateway.py, biznes qoidalar — service.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from .. import schemas as parent_schemas
from ..router_parent import _client_ip, _issue_tokens
from .gateway import TelegramGatewayClient, get_gateway_client
from .service import OTP_TTL_SEC, PhoneVerificationService

router = APIRouter(prefix="/auth/phone", tags=["parent-phone-auth"])


class _Strict(BaseModel):
    class Config:
        extra = "forbid"


class RequestCodeIn(_Strict):
    phoneNumber: str = Field(..., min_length=7, max_length=32)


class ResendCodeIn(_Strict):
    verificationId: str = Field(..., min_length=16, max_length=64)
    phoneNumber: str = Field(..., min_length=7, max_length=32)


class VerifyCodeIn(_Strict):
    verificationId: str = Field(..., min_length=16, max_length=64)
    phoneNumber: str = Field(..., min_length=7, max_length=32)
    code: str = Field(..., regex=r"^\d{4,6}$")   # 6 — Gateway; 4–6 — faqat App Store review raqami


class CodeSentOut(BaseModel):
    success: bool = True
    verificationId: str
    expiresIn: int
    message: str


def get_service(db: Session = Depends(get_db),
                gateway: TelegramGatewayClient = Depends(get_gateway_client)) -> PhoneVerificationService:
    return PhoneVerificationService(db, gateway)


def _sent(row) -> CodeSentOut:
    # Javob foydalanuvchi mavjud-mavjud emasligidan qat'i nazar bir xil
    return CodeSentOut(verificationId=row.public_id, expiresIn=OTP_TTL_SEC,
                       message="Tasdiqlash kodi Telegram orqali yuborildi")


@router.post("/request-code", response_model=CodeSentOut)
def request_code(payload: RequestCodeIn, request: Request,
                 svc: PhoneVerificationService = Depends(get_service)):
    return _sent(svc.request_code(payload.phoneNumber, _client_ip(request)))


@router.post("/resend-code", response_model=CodeSentOut)
def resend_code(payload: ResendCodeIn, request: Request,
                svc: PhoneVerificationService = Depends(get_service)):
    return _sent(svc.resend(payload.verificationId, payload.phoneNumber, _client_ip(request)))


@router.post("/verify-code", response_model=parent_schemas.TokenPair)
def verify_code(payload: VerifyCodeIn, request: Request,
                svc: PhoneVerificationService = Depends(get_service)):
    parent = svc.verify(payload.verificationId, payload.phoneNumber, payload.code, _client_ip(request))
    # _issue_tokens commit qiladi — verification iste'moli, ota-ona va refresh token bitta tranzaksiyada
    return _issue_tokens(svc.db, parent)
