"""Onlayn to'lov sozlamalari — faqat environment'dan (kodda hech qanday secret yo'q).

Provayder "sozlangan" hisoblanadi, agar uning barcha majburiy o'zgaruvchilari
berilgan bo'lsa. Checkout faqat PARENT_PAYMENTS_ENABLED=true bo'lganda ochiladi;
aks holda /parent/children/{id}/pay → 503 payment_provider_unavailable.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = ("payme", "click", "uzum")

# Checkout faqat shu hostlarga yo'naltiriladi (ochiq redirect'ning oldini olish).
_ALLOWED_CHECKOUT_HOSTS = {
    "payme": {"checkout.paycom.uz", "checkout.test.paycom.uz", "test.paycom.uz"},
    "click": {"my.click.uz"},
    "uzum": {"www.uzumbank.uz"},
}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def min_amount() -> int:
    return _int_env("PAYMENT_MIN_AMOUNT", 1000)


def max_amount() -> int:
    return _int_env("PAYMENT_MAX_AMOUNT", 20_000_000)


def invoice_ttl_minutes() -> int:
    return _int_env("PARENT_INVOICE_TTL_MIN", 720)   # 12 soat — Payme tranzaksiya timeout'i bilan bir xil


def allow_refund() -> bool:
    return _env("PAYMENT_ALLOW_REFUND", "true").lower() != "false"


def return_url() -> Optional[str]:
    """To'lovdan keyin brauzer qaytadigan sahifa (ixtiyoriy, faqat https)."""
    url = _env("PAYMENT_RETURN_URL")
    return url if url.startswith("https://") else None


# ── Payme ──
def payme_merchant_id() -> str: return _env("PAYME_MERCHANT_ID")
def payme_key() -> str: return _env("PAYME_KEY")
def payme_checkout_base() -> str: return _env("PAYME_CHECKOUT_URL", "https://checkout.paycom.uz").rstrip("/")
def payme_account_field() -> str: return _env("PAYME_ACCOUNT_FIELD", "invoice_id")


# ── Click ──
def click_service_id() -> str: return _env("CLICK_SERVICE_ID")
def click_merchant_id() -> str: return _env("CLICK_MERCHANT_ID")
def click_secret_key() -> str: return _env("CLICK_SECRET_KEY")
def click_checkout_base() -> str: return _env("CLICK_CHECKOUT_URL", "https://my.click.uz/services/pay")


# ── Uzum ──
def uzum_service_id() -> str: return _env("UZUM_SERVICE_ID")
def uzum_login() -> str: return _env("UZUM_LOGIN")
def uzum_password() -> str: return _env("UZUM_PASSWORD")
def uzum_checkout_base() -> str: return _env("UZUM_CHECKOUT_URL", "https://www.uzumbank.uz/open-service")
def uzum_account_field() -> str: return _env("UZUM_ACCOUNT_FIELD", "order_id")


def is_configured(provider: str) -> bool:
    if provider == "payme":
        return bool(payme_merchant_id() and payme_key())
    if provider == "click":
        return bool(click_service_id() and click_merchant_id() and click_secret_key())
    if provider == "uzum":
        return bool(uzum_service_id() and uzum_login() and uzum_password())
    return False


def payments_enabled() -> bool:
    """Qo'lda yoqiladigan umumiy kalit: merchant sertifikatsiyasi va real sinovdan keyin
    PARENT_PAYMENTS_ENABLED=true. Default — o'chiq (checkout 503, app-config false)."""
    return _env("PARENT_PAYMENTS_ENABLED").lower() == "true"


def review_providers() -> list[str]:
    """App Store review akkaunti uchun alohida yoqilgan provayderlar (PARENT_REVIEW_PAYMENT_PROVIDERS=payme)."""
    raw = _env("PARENT_REVIEW_PAYMENT_PROVIDERS").lower()
    return [p for p in PROVIDERS if p in {x.strip() for x in raw.split(",")}]


def active_providers(parent=None) -> list[str]:
    """Ilovaga ko'rsatiladigan va checkout ochiladigan provayderlar. Review akkaunti uchun —
    umumiy kalitdan qat'i nazar faqat review_providers() (sozlangan bo'lsa)."""
    if parent is not None:
        from ..phone_auth.service import is_review_phone
        from ..service import phone_e164
        if is_review_phone(phone_e164(parent.phone)):
            return [p for p in review_providers() if is_configured(p)]
    if not payments_enabled():
        return []
    return [p for p in PROVIDERS if is_configured(p)]


def checkout_url_allowed(provider: str, url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and p.hostname in _ALLOWED_CHECKOUT_HOSTS.get(provider, set())
