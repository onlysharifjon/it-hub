"""Generic APNs alerts for parent notifications. Runs only in the single worker.

No student names, grades, debt or teacher messages are sent through APNs. The
authenticated app fetches details after a tap. Credentials live in env/files,
never in source or database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import threading
import time

from jose import jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from . import fcm

log = logging.getLogger("ithub.parent.apns")

PREFERENCE_BY_TYPE = {
    "attendance": "attendance", "schedule": "schedule", "payment": "payments",
    "homework": "homework", "announcement": "announcements",
    "weekly_summary": "weekly_summary", "teacher_message": "teacher_messages",
}
SCREEN_BY_TYPE = {
    "attendance": "attendance", "schedule": "schedule", "payment": "payments",
    "homework": "homework", "weekly_summary": "weekly_summary",
    "teacher_message": "messages", "announcement": "notifications",
}


def configured_for(environment: str) -> bool:
    prefix = f"PARENT_APNS_{environment.upper()}"
    key_path = os.getenv(f"{prefix}_KEY_PATH", "")
    return bool(os.getenv("PARENT_APNS_TEAM_ID") and os.getenv("PARENT_APNS_TOPIC") and
                os.getenv(f"{prefix}_KEY_ID") and key_path and Path(key_path).is_file())


def activation_cutoff() -> datetime | None:
    """UTC cutoff is required at activation to avoid replaying historical alerts."""
    raw = os.getenv("PARENT_PUSH_NOT_BEFORE_UTC", "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def configured() -> bool:
    # TestFlight/App Store use production APNs. Sandbox credentials are optional.
    return (os.getenv("PARENT_PUSH_ENABLED", "false").lower() == "true"
            and activation_cutoff() is not None and configured_for("production"))


def _auth_token(environment: str) -> str:
    prefix = f"PARENT_APNS_{environment.upper()}"
    path = Path(os.environ[f"{prefix}_KEY_PATH"])
    key = path.read_text(encoding="utf-8")
    return jwt.encode({"iss": os.environ["PARENT_APNS_TEAM_ID"], "iat": int(time.time())},
                      key, algorithm="ES256", headers={"kid": os.environ[f"{prefix}_KEY_ID"]})


def _enabled(db: Session, row: models.ParentNotification) -> bool:
    field = PREFERENCE_BY_TYPE.get(row.type, "announcements")
    prefs = db.query(models.ParentNotificationPreference).filter(
        models.ParentNotificationPreference.parent_id == row.parent_id).first()
    return prefs is None or bool(getattr(prefs, field))


def dispatch_batch(db: Session, client, bearers: dict[str, str], *, limit: int = 100,
                   fcm_bearer: str | None = None, fcm_enabled: bool = False) -> int:
    """Process committed notifications for APNs and FCM with bounded retries."""
    now = datetime.utcnow()
    not_before = activation_cutoff() or datetime.min
    db.query(models.ParentPushDevice).filter(
        models.ParentPushDevice.updated_at < now - timedelta(days=90),
    ).delete(synchronize_session=False)
    db.commit()
    rows = db.query(models.ParentNotification).join(
        models.Parent, models.Parent.id == models.ParentNotification.parent_id,
    ).filter(
        models.Parent.is_active.is_(True),
        models.ParentNotification.push_attempted_at.is_(None),
        or_(models.ParentNotification.push_next_attempt_at.is_(None),
            models.ParentNotification.push_next_attempt_at <= now),
        models.ParentNotification.created_at >= now - timedelta(days=7),
        models.ParentNotification.created_at >= not_before,
    ).order_by(models.ParentNotification.id.asc()).limit(limit).all()
    sent = 0
    for row in rows:
        error = None
        retry = False
        if _enabled(db, row):
            devices = db.query(models.ParentPushDevice).filter(
                models.ParentPushDevice.parent_id == row.parent_id,
                models.ParentPushDevice.updated_at >= now - timedelta(days=90),
            ).all()
            for device in devices:
                if device.platform == "android":
                    android_cutoff = fcm.activation_cutoff()
                    if android_cutoff is not None and row.created_at < android_cutoff:
                        continue
                    if not fcm_bearer:
                        if fcm_enabled:
                            error, retry = "fcm_auth_unavailable", True
                        continue
                    try:
                        response = fcm.send(
                            client, fcm_bearer, token=device.token,
                            screen=SCREEN_BY_TYPE.get(row.type, "notifications"),
                            kind=row.type, child_id=row.student_id,
                        )
                        if response.status_code == 200:
                            sent += 1
                        else:
                            error = f"fcm_{response.status_code}"
                            status = fcm.error_status(response)
                            if status == "UNREGISTERED":
                                db.delete(device)
                            elif response.status_code in (401, 403, 429) or response.status_code >= 500:
                                retry = True
                    except Exception as exc:
                        error = type(exc).__name__[:120]
                        retry = True
                    continue
                if device.platform != "ios":
                    continue
                bearer = bearers.get(device.environment)
                if not bearer:
                    # An optional sandbox device must not block production delivery.
                    continue
                host = "api.sandbox.push.apple.com" if device.environment == "sandbox" else "api.push.apple.com"
                payload = {
                    "aps": {"alert": {"title": "Minar Parents", "body": "Yangi bildirishnoma mavjud."},
                            "sound": "default"},
                    "screen": SCREEN_BY_TYPE.get(row.type, "notifications"),
                    "type": row.type,
                }
                if row.student_id is not None:
                    payload["child_id"] = row.student_id
                try:
                    response = client.post(
                        f"https://{host}/3/device/{device.token}", json=payload,
                        headers={"authorization": f"bearer {bearer}",
                                 "apns-topic": os.environ["PARENT_APNS_TOPIC"],
                                 "apns-push-type": "alert", "apns-priority": "10",
                                 "apns-collapse-id": f"minar-{row.id}"},
                    )
                    if response.status_code == 200:
                        sent += 1
                    else:
                        error = f"apns_{response.status_code}"
                        reason = ""
                        try:
                            reason = response.json().get("reason", "")
                        except (ValueError, AttributeError):
                            pass
                        if reason in ("BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered"):
                            db.delete(device)
                        elif response.status_code == 429 or response.status_code >= 500:
                            retry = True
                except Exception as exc:
                    error = type(exc).__name__[:120]
                    retry = True
        row.push_attempts = (row.push_attempts or 0) + 1
        if retry and row.push_attempts < 5:
            row.push_next_attempt_at = now + timedelta(minutes=min(60, 2 ** row.push_attempts))
        else:
            row.push_attempted_at = now
            row.push_next_attempt_at = None
        row.push_error = error
        db.commit()
    return sent


def start_scheduler() -> threading.Thread | None:
    if not configured() and not fcm.configured():
        log.info("Parent push disabled; configure APNs or FCM credentials to enable")
        return None

    def loop() -> None:
        import httpx
        with httpx.Client(http2=True, timeout=8) as client:
            bearers: dict[str, str] = {}
            issued: dict[str, float] = {}
            fcm_bearer: str | None = None
            fcm_expiry = 0.0
            while True:
                try:
                    for environment in ("production", "sandbox"):
                        if configured_for(environment) and (environment not in bearers or
                                                            time.time() - issued[environment] > 40 * 60):
                            bearers[environment] = _auth_token(environment)
                            issued[environment] = time.time()
                    android_enabled = fcm.configured()
                    if android_enabled and time.time() >= fcm_expiry:
                        try:
                            fcm_bearer, fcm_expiry = fcm.authorization_token(client)
                        except Exception:
                            fcm_bearer, fcm_expiry = None, time.time() + 30
                            log.exception("FCM OAuth refresh failed; retrying")
                    db = SessionLocal()
                    try:
                        dispatch_batch(db, client, bearers, fcm_bearer=fcm_bearer,
                                       fcm_enabled=android_enabled)
                    finally:
                        db.close()
                except Exception:
                    log.exception("Parent APNs dispatch failed; retrying")
                time.sleep(15)

    thread = threading.Thread(target=loop, name="parent-apns", daemon=True)
    thread.start()
    return thread
