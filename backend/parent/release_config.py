"""Parent iOS release status: public snapshot and server-side legacy client gate."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from .. import models
from ..database import SessionLocal

log = logging.getLogger("ithub.parent.release")

DEFAULT_CONFIG = {
    "maintenance_enabled": False,
    "maintenance_title": "Texnik xizmat davom etmoqda",
    "maintenance_message": "Ilova ustida qisqa texnik ishlar olib borilmoqda. Birozdan so‘ng qayta urinib ko‘ring.",
    "min_supported_build": 1,
    "latest_build": 5,
    "app_store_url": "https://apps.apple.com/uz/app/minar-parents/id6820518218",
}
LEGACY_BUILD = 5  # App Store'dagi eski mijoz build header yubormaydi.


def public_config(db):
    row = db.query(models.ParentReleaseConfig).filter(models.ParentReleaseConfig.id == 1).first()
    if row is None:
        return dict(DEFAULT_CONFIG)
    return {key: getattr(row, key) for key in DEFAULT_CONFIG}


def admin_config(db):
    row = db.query(models.ParentReleaseConfig).filter(models.ParentReleaseConfig.id == 1).first()
    result = {key: getattr(row, key) for key in DEFAULT_CONFIG} if row else dict(DEFAULT_CONFIG)
    result["updated_at"] = row.updated_at if row else None
    result["updated_by_id"] = row.updated_by_id if row else None
    return result


def _snapshot():
    db = SessionLocal()
    try:
        return public_config(db)
    finally:
        db.close()


def _requested_build(scope):
    for key, value in scope.get("headers", ()):
        if key.lower() == b"x-minar-app-build":
            raw = value.decode("ascii", errors="ignore")
            return int(raw) if raw.isdecimal() and 1 <= len(raw) <= 9 and int(raw) > 0 else 1
    return LEGACY_BUILD


def _gate_error(scope, *, status, code, message, retry_after=None):
    rid = scope.get("state", {}).get("request_id") or uuid.uuid4().hex
    headers = {"Cache-Control": "no-store", "X-Request-ID": rid}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "errors": {}, "request_id": rid},
        headers=headers,
    )


class ParentReleaseGateMiddleware:
    """Stops published legacy clients too, while CRM and payment callbacks stay live."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        parent_path = path == "/parent" or path.startswith("/parent/")
        phone_path = path.startswith("/auth/phone/")
        if not (parent_path or phone_path) or method == "OPTIONS":
            return await self.app(scope, receive, send)
        normalized = path.rstrip("/")
        if (method in ("GET", "HEAD") and normalized in ("/parent/release-config", "/parent/privacy.html")) \
                or (method == "DELETE" and normalized == "/parent/account"):
            return await self.app(scope, receive, send)

        try:
            config = await run_in_threadpool(_snapshot)
        except SQLAlchemyError:
            log.exception("Parent release config could not be read")
            response = _gate_error(scope, status=503, code="service_unavailable",
                                   message="Xizmat vaqtincha ishlamayapti.", retry_after=30)
            return await response(scope, receive, send)

        if _requested_build(scope) < config["min_supported_build"]:
            response = _gate_error(scope, status=426, code="upgrade_required",
                                   message="Ilovadan foydalanish uchun uni yangilang.")
            return await response(scope, receive, send)
        if config["maintenance_enabled"]:
            response = _gate_error(scope, status=503, code="maintenance",
                                   message=config["maintenance_message"], retry_after=120)
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)
