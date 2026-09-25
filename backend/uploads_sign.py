"""/uploads fayllari uchun imzolangan (HMAC) va muddatli URL'lar.

/uploads endi ochiq statik papka emas: rasm faqat backend bergan imzoli havola
(`?exp=...&sig=...`) orqali ochiladi. Imzo SECRET_KEY + fayl yo'li + muddatdan
hisoblanadi, shuning uchun ID'larni ketma-ket terib boshqa rasmlarni ochib
bo'lmaydi va sizib chiqqan havola muddati tugagach ishlamay qoladi.

Imzo yo'lga query-string sifatida qo'shiladi (`avatars/ab12.jpg?exp=..&sig=..`),
shuning uchun frontend avvalgidek `${API_BASE}/uploads/${avatar}` qila oladi.
"""
import hashlib
import hmac
import time
from typing import Optional

from .security import SECRET_KEY

_KEY = SECRET_KEY.encode()
UPLOAD_URL_TTL_SECONDS = 12 * 3600

# Imzosiz ochiladigan papkalar: sertifikat PDF'lari ota-ona mobil ilovasiga
# doimiy link sifatida beriladi, nomlari tasodifiy uuid (taxmin qilib bo'lmaydi).
# Qolgan hamma narsa (avatarlar, talaba va yuz rasmlari) faqat imzo bilan.
# Kamera servisi yuz rasmlarini /camera/photo/... (kamera kaliti) orqali oladi.
PUBLIC_PREFIXES = ("certificates/",)


def _sig(rel: str, exp: int) -> str:
    return hmac.new(_KEY, f"{rel}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def sign(rel: Optional[str]) -> Optional[str]:
    """`avatars/x.jpg` -> `avatars/x.jpg?exp=...&sig=...` (bo'sh bo'lsa o'zi).
    `/uploads/avatars/x.jpg` ko'rinishidagi to'liq yo'l ham qabul qilinadi."""
    if not rel or "?" in rel or rel.startswith(("http://", "https://", "data:")):
        return rel
    if rel.startswith("/uploads/"):
        return "/uploads/" + sign(rel[len("/uploads/"):])
    # Muddatni soat boshiga yaxlitlaymiz — bir soat ichida URL o'zgarmaydi,
    # brauzer rasmni keshdan ola oladi.
    exp = (int(time.time()) // 3600 + 1) * 3600 + UPLOAD_URL_TTL_SECONDS
    return f"{rel}?exp={exp}&sig={_sig(rel, exp)}"


def verify(rel: str, exp: Optional[str], sig: Optional[str]) -> bool:
    if not exp or not sig:
        return False
    try:
        exp_i = int(exp)
    except ValueError:
        return False
    if exp_i < time.time():
        return False
    return hmac.compare_digest(sig, _sig(rel, exp_i))
