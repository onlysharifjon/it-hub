"""TelegramGatewayClient — https://core.telegram.org/gateway/api

Faqat HTTP qatlam: token env'dan (TELEGRAM_GATEWAY_TOKEN), hech qachon log qilinmaydi.
Javob `{"ok": true, "result": {...}}` yoki `{"ok": false, "error": "..."}`.

Retry siyosati: `sendVerificationMessage` HECH QACHON avtomatik qayta yuborilmaydi
(timeout'da kod allaqachon yetib borgan bo'lishi mumkin — ikkinchi kod va ikkinchi
to'lov bo'lardi). `checkVerificationStatus` faqat ulanish o'rnatilmagan (so'rov
serverga yetmagan) holatda bir marta qayta urinadi.
"""
from __future__ import annotations

import logging
import os
import json
import socket
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

log = logging.getLogger("ithub.telegram_gateway")


class GatewayError(Exception):
    """Gateway bilan bog'liq xato. kind: unavailable | not_reachable | rate_limited | config | rejected."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(kind)
        self.kind = kind
        self.detail = detail   # faqat server logi uchun (raw javob clientga berilmaydi)


def _classify(error: str) -> str:
    e = (error or "").upper()
    if "FLOOD" in e or "TOO_MANY" in e:
        return "rate_limited"
    if "TOKEN" in e or "BALANCE" in e or "UNAUTHORIZED" in e or "ACCESS" in e:
        return "config"
    if "PHONE" in e or "USER" in e or "RECIPIENT" in e or "NOT_FOUND" in e or "CANNOT" in e or "UNREACHABLE" in e:
        return "not_reachable"
    return "rejected"


class TelegramGatewayClient:
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: float = 10.0, transport: Optional[Any] = None):
        # transport: (url, payload, headers, timeout) -> (status, body) — testlar uchun
        self._token = (token if token is not None else os.getenv("TELEGRAM_GATEWAY_TOKEN", "")).strip()
        self._base = (base_url or os.getenv("TELEGRAM_GATEWAY_BASE_URL", "https://gatewayapi.telegram.org")).rstrip("/")
        self._timeout = timeout
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._token)

    def _post(self, url: str, payload: bytes, headers: dict) -> Tuple[int, bytes]:
        """Standart kutubxona (urllib) — qo'shimcha dependency yo'q. Testlarda `transport` bilan almashtiriladi."""
        if self._transport is not None:
            return self._transport(url, payload, headers, self._timeout)
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:      # 4xx/5xx — javob tanasi bor
            return e.code, e.read()

    def _call(self, method: str, body: dict, retry_connect: bool = False) -> dict:
        if not self._token:
            raise GatewayError("config", "TELEGRAM_GATEWAY_TOKEN not set")
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        payload = json.dumps(body).encode()
        attempts = 2 if retry_connect else 1
        for i in range(attempts):
            try:
                status, raw = self._post(f"{self._base}/{method}", payload, headers)
                break
            except (socket.timeout, TimeoutError):
                raise GatewayError("unavailable", f"{method}: timeout")
            except urllib.error.URLError as e:
                reason = getattr(e, "reason", None)
                if isinstance(reason, (socket.timeout, TimeoutError)):
                    raise GatewayError("unavailable", f"{method}: timeout")
                # Ulanish o'rnatilmadi (so'rov serverga yetmagan) — faqat shu holatda qayta urinish
                if i + 1 < attempts:
                    continue
                raise GatewayError("unavailable", f"{method}: connect error {type(reason).__name__}")
            except OSError as e:
                raise GatewayError("unavailable", f"{method}: {type(e).__name__}")
        if status >= 500:
            raise GatewayError("unavailable", f"{method}: HTTP {status}")
        try:
            data = json.loads(raw.decode() or "null")
        except (ValueError, UnicodeDecodeError):
            raise GatewayError("unavailable", f"{method}: non-JSON HTTP {status}")
        if not isinstance(data, dict) or not data.get("ok"):
            err = str(data.get("error") if isinstance(data, dict) else "") or f"HTTP {status}"
            if status == 429:
                raise GatewayError("rate_limited", f"{method}: {err}")
            raise GatewayError(_classify(err), f"{method}: {err}")
        result = data.get("result")
        return result if isinstance(result, dict) else {"value": result}

    def send_verification_message(self, phone_number: str, code_length: int, ttl: int) -> str:
        """`request_id` qaytaradi. Retry yo'q."""
        result = self._call("sendVerificationMessage",
                            {"phone_number": phone_number, "code_length": code_length, "ttl": ttl})
        request_id = result.get("request_id")
        if not request_id:
            raise GatewayError("unavailable", "sendVerificationMessage: no request_id")
        return str(request_id)

    def check_verification_status(self, request_id: str, code: str) -> Optional[str]:
        """verification_status.status (code_valid | code_invalid | code_max_attempts_exceeded | expired) yoki None."""
        result = self._call("checkVerificationStatus", {"request_id": request_id, "code": code},
                            retry_connect=True)
        vs = result.get("verification_status") or {}
        return vs.get("status") if isinstance(vs, dict) else None

    def revoke_verification_message(self, request_id: str) -> None:
        """Best-effort: xato bo'lsa faqat log (eski kod baribir bizda yaroqsiz qilingan)."""
        try:
            self._call("revokeVerificationMessage", {"request_id": request_id})
        except GatewayError as e:
            log.warning("telegram gateway revoke failed: %s", e.kind)


def get_gateway_client() -> TelegramGatewayClient:
    """FastAPI dependency — testlarda app.dependency_overrides orqali mock bilan almashtiriladi."""
    return TelegramGatewayClient()
