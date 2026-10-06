"""Ota-ona API uchun yagona xato formati va request_id.

Faqat `/parent/...` yo'llariga ta'sir qiladi — CRM endpointlari avvalgidek
FastAPI standart javoblarini qaytaradi:

    {"code": "validation_error", "message": "...", "errors": {"amount": ["..."]},
     "request_id": "..."}

Router ichida `api_error(...)` ko'tariladi (HTTPException, detail = {"error": {...}}).
Har bir javobga `X-Request-ID` header qo'shiladi; nginx yuborgan qiymat
(faqat xavfsiz belgilar) bo'lsa, o'shani ishlatamiz.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler as _default_http_handler,
    request_validation_exception_handler as _default_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.exc import OperationalError, DisconnectionError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("ithub.parent")

PARENT_PREFIX = "/parent"
_SAFE_RID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

_STATUS_CODES = {
    400: ("bad_request", "So'rov noto'g'ri."),
    401: ("unauthorized", "Avtorizatsiya talab qilinadi yoki token yaroqsiz."),
    403: ("forbidden", "Bu amal uchun ruxsat yo'q."),
    404: ("not_found", "Topilmadi."),
    405: ("method_not_allowed", "Bu metod qo'llab-quvvatlanmaydi."),
    409: ("conflict", "Joriy holat bilan ziddiyat."),
    422: ("validation_error", "So'rov ma'lumotlari noto'g'ri."),
    429: ("rate_limited", "Juda ko'p urinish. Birozdan so'ng qayta urinib ko'ring."),
    500: ("internal_error", "Kutilmagan server xatosi."),
    503: ("service_unavailable", "Xizmat vaqtincha ishlamayapti."),
}


def api_error(code: str, message: str, status_code: int = 400, *,
              errors: Optional[dict] = None, headers: Optional[dict] = None) -> HTTPException:
    err = {"code": code, "message": message}
    if errors:
        err["errors"] = errors
    return HTTPException(status_code=status_code, detail={"error": err}, headers=headers)


PHONE_AUTH_PREFIX = "/auth/phone/"


def _is_parent(request: Request) -> bool:
    path = request.url.path
    return path == PARENT_PREFIX or path.startswith(PARENT_PREFIX + "/") or path.startswith(PHONE_AUTH_PREFIX)


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid or uuid.uuid4().hex


def _envelope(request: Request, status_code: int, code: str, message: str,
              errors: Optional[dict] = None, headers: Optional[dict] = None) -> JSONResponse:
    rid = request_id(request)
    hdrs = dict(headers or {})
    hdrs["X-Request-ID"] = rid
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "errors": errors or {}, "request_id": rid},
        headers=hdrs,
    )


class RequestIdMiddleware:
    """Har so'rovga request_id beradi (scope.state) va javobga X-Request-ID qo'shadi."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = ""
        for k, v in scope.get("headers") or []:
            if k == b"x-request-id":
                incoming = v.decode("latin-1")
                break
        rid = incoming if _SAFE_RID.match(incoming or "") else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid

        async def _send(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"]
                headers.append((b"x-request-id", rid.encode()))
                message["headers"] = headers
            await send(message)

        return await self.app(scope, receive, _send)


def _field_path(loc) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "__root__"


async def _http_handler(request: Request, exc: StarletteHTTPException):
    if not _is_parent(request):
        return await _default_http_handler(request, exc)
    default_code, default_msg = _STATUS_CODES.get(exc.status_code, ("error", "Xatolik."))
    detail = exc.detail
    code, message, errors = default_code, default_msg, None
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        e = detail["error"]
        code = e.get("code") or code
        message = e.get("message") or message
        errors = e.get("errors")
    elif isinstance(detail, str) and detail and exc.status_code < 500:
        message = detail
    return _envelope(request, exc.status_code, code, message, errors, getattr(exc, "headers", None))


async def _validation_handler(request: Request, exc: RequestValidationError):
    if not _is_parent(request):
        return await _default_validation_handler(request, exc)
    errs = exc.errors()
    if any(e.get("type", "").startswith("value_error.jsondecode") or e.get("type") == "json_invalid"
           for e in errs):
        return _envelope(request, 400, "invalid_json", "So'rov tanasi yaroqli JSON emas.")
    fields: dict = {}
    for e in errs:
        fields.setdefault(_field_path(e.get("loc", ())), []).append(e.get("msg", "invalid"))
    # OTP endpointlari shartnomasi: validatsiya xatosi — 400 (parent API'da — 422)
    status = 400 if request.url.path.startswith(PHONE_AUTH_PREFIX) else 422
    return _envelope(request, status, "validation_error", "So'rov ma'lumotlari noto'g'ri.", fields)


async def _db_unavailable_handler(request: Request, exc: Exception):
    if not _is_parent(request):
        raise exc
    log.error("parent api: db unavailable request_id=%s err=%s", request_id(request), type(exc).__name__)
    return _envelope(request, 503, "service_unavailable", "Xizmat vaqtincha ishlamayapti. Keyinroq urinib ko'ring.",
                     headers={"Retry-After": "30"})


async def _unhandled_handler(request: Request, exc: Exception):
    # Starlette bu handlerni ServerErrorMiddleware ichida chaqiradi va keyin istisnoni
    # qayta ko'taradi (stack trace server logiga tushadi, javobga emas).
    if not _is_parent(request):
        return PlainTextResponse("Internal Server Error", status_code=500)
    log.error("parent api: unhandled error request_id=%s path=%s", request_id(request), request.url.path)
    return _envelope(request, 500, "internal_error", "Kutilmagan server xatosi.")


def install(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(OperationalError, _db_unavailable_handler)
    app.add_exception_handler(DisconnectionError, _db_unavailable_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
