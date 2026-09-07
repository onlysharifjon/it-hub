"""Telefon raqamlari bilan ishlash — bitta manbadan (main.py va facebook_leads.py
ikkalasi ham shu yerdan foydalanadi, aks holda dedup mantiqi ikkiga bo'linib ketadi)."""

import re
from typing import Optional

# Facebook formasi telefon so'ramaganda CRM'da shu belgi bilan saqlanadi.
NO_PHONE_PREFIX = "no-phone-"


def normalize_phone(phone: Optional[str]) -> str:
    """Formatlash farqlaridan qat'i nazar solishtirish uchun kalit.

    +998, bo'shliq, tire, qavs olib tashlanadi va faqat oxirgi 9 ta raqam
    qoladi (O'zbekiston mobil raqamlari uzunligi). 9 tadan kam raqam bo'lsa
    bor raqamlar qaytariladi, umuman raqam bo'lmasa — bo'sh satr.
    """
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else digits


def is_placeholder_phone(phone: Optional[str]) -> bool:
    """`no-phone-123` kabi vaqtinchalik belgimi (haqiqiy raqam emas)."""
    return bool(phone) and phone.startswith(NO_PHONE_PREFIX)


def dedup_key(phone: Optional[str]) -> Optional[str]:
    """Dublikat izlash uchun kalit. Solishtirib bo'lmaydigan raqam uchun None."""
    if not phone or is_placeholder_phone(phone):
        return None
    key = normalize_phone(phone)
    return key or None


def format_phone(phone: Optional[str]) -> Optional[str]:
    """Ko'rsatish uchun bir xil ko'rinishga keltiradi: +998 XX XXX XX XX.

    O'zbekiston raqamiga o'xshamasa — asl matn o'zgarishsiz qaytariladi
    (chet el raqamlari va qo'lda kiritilgan izohlar yo'qolmasin).
    """
    if not phone or is_placeholder_phone(phone):
        return phone
    digits = re.sub(r"\D", "", phone)
    # Faqat O'zbekiston raqamiga o'xshasa formatlaymiz: 9 xonali, yoki 998 bilan
    # boshlanuvchi 12 xonali. Boshqa davlat raqamini +998 qilib yubormaymiz.
    is_uz = len(digits) == 9 or (len(digits) == 12 and digits.startswith("998"))
    if not is_uz:
        return phone
    d = digits[-9:]
    return f"+998 {d[0:2]} {d[2:5]} {d[5:7]} {d[7:9]}"
