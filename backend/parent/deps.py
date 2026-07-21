"""Parent API bog'liqliklari (dependencies)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import decode_parent_access_token

_bearer = HTTPBearer(auto_error=False)

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"error": {"code": "unauthorized", "message": "Token yaroqsiz yoki muddati tugagan"}},
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_parent(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.Parent:
    if not creds or creds.scheme.lower() != "bearer":
        raise _UNAUTH
    parent_id = decode_parent_access_token(creds.credentials)
    if parent_id is None:
        raise _UNAUTH
    parent = db.query(models.Parent).filter(models.Parent.id == parent_id).first()
    if not parent or not parent.is_active:
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
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Bola topilmadi"}},
        )
    child = db.query(models.Student).filter(models.Student.id == child_id).first()
    if not child:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Bola topilmadi"}},
        )
    return child
