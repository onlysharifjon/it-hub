"""Vaqt zonasi — yagona manba (Toshkent, UTC+5).

Kelishuv (o'zgarmaydi):
  * Bazadagi barcha `DateTime` ustunlar NAIVE UTC saqlanadi — `utcnow()`.
    JWT muddati, taqqoslashlar va mavjud yozuvlar shunga tayanadi.
  * Foydalanuvchi ko'radigan HAR QANDAY vaqt Toshkent (+05:00) bo'ladi:
      – API javoblari: `main.py` dagi global encoder `+05:00` offset qo'shadi;
      – "bugun" / "shu oy" hisoblari: shu moduldagi `today()` va `now()`;
      – sana filtrlari: `day_bounds()` / `month_bounds()` Toshkent kunini
        naive UTC oralig'iga o'giradi (aks holda filtr 5 soatga siljiydi).

Nega `date.today()` ishlatilmaydi: server UTC'da ishlaydi, shuning uchun
Toshkent vaqti bilan 00:00–05:00 orasida u KECHAGI sanani qaytaradi —
yo'qlama, hisobot va qarz hisoblari bir kunga xato bo'lardi.

Qo'shimcha himoya sifatida jarayonning TZ'si ham `Asia/Tashkent` qilinadi
(`_install_process_tz`), shunda kutubxonalar yoki kelajakda yozilgan kod
`datetime.now()` chaqirsa ham natija Toshkent vaqti bo'ladi. Bu `utcnow()`ga
ta'sir qilmaydi — u har doim UTC.
"""

import os
import time
from datetime import date, datetime, timedelta, timezone

TZ_NAME = "Asia/Tashkent"

# O'zbekiston 2005-yildan beri yozgi vaqtga o'tmaydi — offset doimiy +05:00.
OFFSET = timedelta(hours=5)
TASHKENT = timezone(OFFSET, "UTC+5")


def _install_process_tz() -> None:
    """Jarayonning mahalliy vaqtini Toshkentga o'rnatadi (import paytida)."""
    os.environ.setdefault("TZ", TZ_NAME)
    if hasattr(time, "tzset"):          # Windows'da yo'q — u yerda no-op
        time.tzset()


_install_process_tz()


# ── Hozirgi vaqt ──────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    """Bazaga yozish uchun naive UTC."""
    return datetime.utcnow()


def now() -> datetime:
    """Toshkent devor-soati, naive (`datetime.now()` o'rniga)."""
    return datetime.utcnow() + OFFSET


def today() -> date:
    """Toshkent taqvimidagi bugungi sana (`date.today()` o'rniga)."""
    return now().date()


# ── Konversiya ────────────────────────────────────────────────────────────────

def to_local(dt: datetime) -> datetime:
    """Naive UTC → naive Toshkent."""
    return dt + OFFSET


def to_utc(dt: datetime) -> datetime:
    """Naive Toshkent → naive UTC."""
    return dt - OFFSET


def isoformat(dt: datetime) -> str:
    """Naive UTC (yoki aware) → `+05:00` offsetli ISO qator."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TASHKENT).isoformat()


# ── Filtr chegaralari (Toshkent kuni/oyi → naive UTC oralig'i) ────────────────

def day_bounds(d: date) -> tuple:
    """Toshkent kunining [boshi, oxiri) naive UTC chegaralari."""
    start_local = datetime(d.year, d.month, d.day)
    return (start_local - OFFSET, start_local + timedelta(days=1) - OFFSET)


def range_bounds(d_from: date, d_to: date) -> tuple:
    """[d_from 00:00, d_to 24:00) Toshkent oralig'i → naive UTC."""
    return (day_bounds(d_from)[0], day_bounds(d_to)[1])


def month_bounds(year: int, month: int) -> tuple:
    """Toshkent oyining [boshi, oxiri) naive UTC chegaralari."""
    start_local = datetime(year, month, 1)
    end_local = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return (start_local - OFFSET, end_local - OFFSET)
