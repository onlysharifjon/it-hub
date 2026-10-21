"""Paycom certification callback, isolated from the live CRM database.

Run only against a dedicated PostgreSQL database named ``paycom_sandbox``.
The public reverse proxy must expose only ``POST /payme`` to Paycom; this app
contains no CRM, parent login, checkout, or background worker endpoints.
"""

from __future__ import annotations

import os
import base64
import binascii
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit


def require_sandbox_database() -> None:
    """Fail before connecting if a deployment accidentally points at live CRM."""
    url = urlsplit(os.getenv("DATABASE_URL", ""))
    if (os.getenv("PAYCOM_SANDBOX_MODE") != "enabled"
            or url.scheme not in {"postgresql", "postgresql+psycopg2"}
            or url.path != "/paycom_sandbox"):
        raise RuntimeError("Paycom sandbox requires its dedicated paycom_sandbox database")
    if os.getenv("PAYME_ACCOUNT_FIELD") != "order_id":
        raise RuntimeError("Paycom sandbox cashbox account field must be order_id")


require_sandbox_database()

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from sqlalchemy import Column, Integer, String, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from .database import Base, SessionLocal, engine, get_db  # noqa: E402
from .parent.payments import payme  # noqa: E402

log = logging.getLogger("ithub.payments.paycom_sandbox")


class PaycomSandboxCredential(Base):
    """Only exists in the sandbox DB; never imported by production migrations."""

    __tablename__ = "paycom_sandbox_credential"
    id = Column(Integer, primary_key=True)
    password_sha256 = Column(String(64), nullable=False)


def _digest(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _request_auth_ok(request: Request, password_sha256: str) -> bool:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return False
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    login, separator, password = raw.partition(":")
    return (login == "Paycom" and bool(separator)
            and hmac.compare_digest(_digest(password), password_sha256))


def ensure_auth_table() -> None:
    PaycomSandboxCredential.__table__.create(bind=engine, checkfirst=True)
    with SessionLocal.begin() as db:
        if db.get(PaycomSandboxCredential, 1) is None:
            key = payme.config.payme_key()
            if not key or not payme.config.payme_merchant_id():
                raise RuntimeError("Paycom sandbox TEST_KEY and merchant ID are required")
            db.add(PaycomSandboxCredential(id=1, password_sha256=_digest(key)))


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    ensure_auth_table()
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)


@app.post("/payme", include_in_schema=False)
async def payme_callback(request: Request, db: Session = Depends(get_db)):
    # Keep ChangePassword entirely outside the production Payme dispatcher.
    # The singleton row lock serializes credential rotation with callbacks.
    try:
        body = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return payme._err(None, payme.E_PARSE)
    req_id = body.get("id") if isinstance(body, dict) else None
    credential = (db.query(PaycomSandboxCredential)
                  .filter_by(id=1).with_for_update().one_or_none())
    if credential is None or not _request_auth_ok(request, credential.password_sha256):
        db.rollback()
        return payme._err(req_id, payme.E_AUTH)
    if not isinstance(body, dict) or not isinstance(body.get("params"), dict):
        db.rollback()
        return payme._err(req_id, payme.E_RPC)

    if body.get("method") == "ChangePassword":
        new_password = body["params"].get("password")
        if not isinstance(new_password, str) or not new_password:
            db.rollback()
            return payme._err(req_id, payme.E_RPC)
        new_digest = _digest(new_password)
        if hmac.compare_digest(new_digest, credential.password_sha256):
            db.rollback()
            return payme._err(req_id, payme.E_SYSTEM, "password")
        credential.password_sha256 = new_digest
        db.commit()
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"success": True}})

    fn = payme._METHODS.get(body.get("method"))
    if fn is None:
        db.rollback()
        return payme._err(req_id, payme.E_METHOD, str(body.get("method")))
    try:
        result = fn(db, body["params"])
        db.commit()
    except payme.PaymeError as exc:
        db.rollback()
        return payme._err(req_id, exc.code, exc.data)
    except IntegrityError:
        db.rollback()
        return payme._err(req_id, payme.E_CANNOT_PERFORM)
    except Exception:
        db.rollback()
        log.exception("sandbox payme %s failed", body.get("method"))
        return payme._err(req_id, payme.E_SYSTEM)
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


@app.get("/readyz", include_in_schema=False)
def readyz(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
