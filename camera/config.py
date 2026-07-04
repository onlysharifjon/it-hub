"""Konfiguratsiya — barcha sozlamalar .env orqali beriladi."""
import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── Kamera (RTSP) ─────────────────────────────────────────────────────────────
RTSP_URL = _get("RTSP_URL")  # masalan: rtsp://user:pass@192.168.1.10:554/stream1

# Har nechinchi kadrni tahlil qilish (tezlik uchun). 1 = har bir kadr.
FRAME_SKIP = int(_get("FRAME_SKIP", "5"))

# Yuzni topish modeli: "hog" (tez, CPU) yoki "cnn" (aniqroq, GPU tavsiya etiladi)
DETECTION_MODEL = _get("DETECTION_MODEL", "hog")

# Tanib olish qat'iyligi. Kichikroq = qat'iyroq (0.6 standart).
RECOGNITION_TOLERANCE = float(_get("RECOGNITION_TOLERANCE", "0.5"))

# ── Keldi/Ketdi mantiq ────────────────────────────────────────────────────────
# Bola shuncha soniya ko'rinmasa "ketdi" deb hisoblanadi.
ABSENCE_TIMEOUT = int(_get("ABSENCE_TIMEOUT", "180"))

# Bitta bola bo'yicha xabarlar orasidagi eng kam vaqt (takroriy spamning oldini oladi).
NOTIFY_COOLDOWN = int(_get("NOTIFY_COOLDOWN", "300"))

# ── Telegram bildirishnomasi ──────────────────────────────────────────────────
TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN")
# Ma'muriyat/qabulxona chat_id — barcha kelgan-ketganlar shu yerga tushadi.
NOTIFY_CHAT_ID = _get("NOTIFY_CHAT_ID")
# True bo'lsa, bolaning o'z telegram_id siga ham xabar yuboriladi.
NOTIFY_STUDENT = _get("NOTIFY_STUDENT", "false").lower() == "true"

# ── Ma'lumotlar bazasi (backend bilan bir xil) ────────────────────────────────
DATABASE_URL = _get("DATABASE_URL")  # .env da beriladi; bo'sh bo'lsa DB'siz (faqat log/telegram) ishlaydi

# ── Yuzlar bazasi ─────────────────────────────────────────────────────────────
# faces/<student_id>/*.jpg  ko'rinishida saqlanadi.
FACES_DIR = _get("FACES_DIR", os.path.join(os.path.dirname(__file__), "faces"))

# Encodinglar keshini saqlash fayli (qayta ishga tushirishda tezlashtiradi).
ENCODINGS_CACHE = _get("ENCODINGS_CACHE", os.path.join(os.path.dirname(__file__), "encodings.pkl"))
