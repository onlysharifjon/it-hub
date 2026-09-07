"""IT Hub LMS backend.

`tz` eng birinchi import qilinadi — u jarayonning vaqt zonasini
`Asia/Tashkent` ga o'rnatadi, shunda paketning istalgan modulida
`datetime.now()` / `date.today()` Toshkent vaqtini beradi.
Batafsil: `backend/tz.py`.
"""
from . import tz  # noqa: F401  (import yon ta'siri uchun — TZ o'rnatiladi)
