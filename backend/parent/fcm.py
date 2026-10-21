"""FCM HTTP v1 transport for parent Android devices.

The service-account JSON is read from a private server path. The app config
stays disabled until an operator explicitly enables Android push and mounts
the key; no credential is stored in Git, the database, or a mobile build.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone

from jose import jwt

TOKEN_URL = "https://oauth2.googleapis.com/token"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def activation_cutoff() -> datetime | None:
    raw = os.getenv("PARENT_ANDROID_PUSH_NOT_BEFORE_UTC", "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def enabled() -> bool:
    project = os.getenv("PARENT_FCM_PROJECT_ID", "")
    # Android has its own activation window; enabling it must not alter the
    # already active iOS APNs delivery cutoff.
    return (os.getenv("PARENT_PUSH_ENABLED", "false").lower() == "true"
            and os.getenv("PARENT_ANDROID_PUSH_ENABLED", "false").lower() == "true"
            and activation_cutoff() is not None
            and bool(re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project)))


def configured() -> bool:
    """Worker-side readiness. The private key is mounted only in the worker."""
    key_path = os.getenv("PARENT_FCM_SERVICE_ACCOUNT_PATH", "")
    return enabled() and bool(key_path) and Path(key_path).is_file()


def _service_account() -> dict:
    path = Path(os.environ["PARENT_FCM_SERVICE_ACCOUNT_PATH"])
    account = json.loads(path.read_text(encoding="utf-8"))
    if (account.get("type") != "service_account"
            or account.get("project_id") != os.environ["PARENT_FCM_PROJECT_ID"]
            or not str(account.get("client_email", "")).endswith(".gserviceaccount.com")
            or not account.get("private_key")):
        raise ValueError("FCM service account is not valid for this project")
    return account


def authorization_token(client) -> tuple[str, float]:
    """Exchange a short-lived signed assertion for a Google OAuth token."""
    account = _service_account()
    now = int(time.time())
    assertion = jwt.encode({
        "iss": account["client_email"],
        "scope": FCM_SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }, account["private_key"], algorithm="RS256")
    response = client.post(TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    })
    if response.status_code != 200:
        raise RuntimeError(f"FCM OAuth request failed ({response.status_code})")
    payload = response.json()
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("FCM OAuth response omitted access token")
    lifetime = max(60, min(int(payload.get("expires_in", 3600)), 3600))
    return token, time.time() + lifetime - 300


def send(client, bearer: str, *, token: str, screen: str, kind: str,
         child_id: int | None):
    """Data-only push lets the app enforce session/consent before displaying it."""
    data = {"screen": screen, "type": kind}
    if child_id is not None:
        data["child_id"] = str(child_id)
    project = os.environ["PARENT_FCM_PROJECT_ID"]
    return client.post(
        f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
        json={"message": {
            "token": token,
            "data": data,
            "android": {"priority": "HIGH"},
        }},
        headers={"authorization": f"Bearer {bearer}"},
    )


def error_status(response) -> str:
    try:
        return str(response.json().get("error", {}).get("status", ""))
    except (AttributeError, ValueError, TypeError):
        return ""
