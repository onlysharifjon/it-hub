"""Moliya bo'limi huquqlari.

Har bir imkoniyat alohida huquq. Admin — barcha huquqlarga ega. "finance"
rolidagi xodimga admin `User.permissions` orqali huquqlarni beradi/oladi;
NULL bo'lsa — `FINANCE_DEFAULT` to'plami. Boshqa rollarda moliya huquqi yo'q.

Finans xodimi rollar, tizim sozlamalari va o'z huquqlarini o'zgartira olmaydi:
foydalanuvchi endpoint'lari (`/users/*`) va moliya sozlamalari `require_admin`.
"""
import json
from typing import Iterable, List

from .. import models
from ..models import UserRole

PERMISSIONS = {
    "finance.dashboard":  "Moliyaviy dashboardni ko'rish",
    "finance.clients":    "Mijozlar, shartnomalar va to'lovlarni ko'rish",
    "finance.income":     "Kirim (to'lov) kiritish",
    "finance.expense":    "Xarajat kiritish",
    "finance.debts":      "Qarzdorlikni kuzatish",
    "finance.reports":    "Hisobotlarni ko'rish",
    "finance.export":     "Hisobotlarni eksport qilish (Excel/CSV)",
    "finance.audit":      "Operatsiyalar tarixini ko'rish",
    "finance.approve":    "Operatsiyalarni tasdiqlash va qoralamani bekor qilish",
    "finance.refund":     "Qaytarim va tuzatish rasmiylashtirish",
    "finance.transfer":   "Hisoblar orasida o'tkazma",
    "finance.categories": "Xarajat kategoriyalarini boshqarish",
}

# Yangi finans xodimining standart huquqlari. Tasdiqlash, qaytarim, o'tkazma va
# kategoriyalar — admin alohida ruxsat bergandagina.
FINANCE_DEFAULT = [
    "finance.dashboard", "finance.clients", "finance.income", "finance.expense",
    "finance.debts", "finance.reports", "finance.export", "finance.audit",
]


def normalize(perms: Iterable[str]) -> List[str]:
    """Faqat ma'lum huquqlar, takrorsiz, PERMISSIONS tartibida."""
    wanted = set(perms or [])
    return [p for p in PERMISSIONS if p in wanted]


def effective_permissions(user: models.User) -> List[str]:
    if user is None:
        return []
    if user.role == UserRole.admin.value:
        return list(PERMISSIONS)
    if user.role != UserRole.finance.value:
        return []
    if user.permissions is None:
        return list(FINANCE_DEFAULT)
    try:
        return normalize(json.loads(user.permissions))
    except (ValueError, TypeError):
        return []


def has(user: models.User, perm: str) -> bool:
    return perm in effective_permissions(user)
