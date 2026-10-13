"""Parent API bog'liqliklari (dependencies)."""
from __future__ import annotations

import hmac

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import decode_parent_access_claims, password_version
from .errors import api_error

_bearer = HTTPBearer(auto_error=False)

_UNAUTH = api_error("unauthorized", "Token yaroqsiz yoki muddati tugagan", 401,
                    headers={"WWW-Authenticate": "Bearer"})


def get_current_parent(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.Parent:
    if not creds or creds.scheme.lower() != "bearer":
        raise _UNAUTH
    claims = decode_parent_access_claims(creds.credentials)
    if claims is None:
        raise _UNAUTH
    parent = db.query(models.Parent).filter(models.Parent.id == claims["parent_id"]).first()
    if not parent or not parent.is_active:
        raise _UNAUTH
    # Parol almashtirilgan/tiklangan bo'lsa — undan oldingi access tokenlar ham darhol yaroqsiz.
    # `pwv`siz (eski) tokenlar TTL tugaguncha qabul qilinadi — deploy paytida hech kim chiqib ketmasin.
    pwv = claims.get("pwv")
    if pwv is not None and not hmac.compare_digest(pwv, password_version(parent.hashed_password)):
        raise _UNAUTH
    return parent


def get_owned_child(
    child_id: int,
    parent: models.Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
) -> models.Student:
    """Bola shu ota-onaga tegishliligini tekshiradi — aks holda 404 (enumeration'dan himoya)."""
    link = (
        db.query(models.ParentChild)
        .filter(
            models.ParentChild.parent_id == parent.id,
            models.ParentChild.student_id == child_id,
        )
        .first()
    )
    if not link:
        raise api_error("child_not_found", "Bola topilmadi", 404)
    child = db.query(models.Student).filter(models.Student.id == child_id).first()
    if not child:
        raise api_error("child_not_found", "Bola topilmadi", 404)
    return child
