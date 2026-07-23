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
# Bola shuncha soniya ko'rinmasa "ketdi" deb hisoblanadi (fallback).
ABSENCE_TIMEOUT = int(_get("ABSENCE_TIMEOUT", "180"))

# Bitta bola bo'yicha xabarlar orasidagi eng kam vaqt (takroriy spamning oldini oladi).
NOTIFY_COOLDOWN = int(_get("NOTIFY_COOLDOWN", "300"))

# ── Virtual chiziqlar (kadr balandligining ulushi sifatida 0.0–1.0) ────────────
# 1-chiziq: shaxs bu chiziqdan pastga o'tsa → ketdi
LINE_1_Y_FRAC = float(_get("LINE_1_Y_FRAC", "0.55"))
# 2-chiziq: shaxs bu chiziqdan tepaga o'tsa → keldi
LINE_2_Y_FRAC = float(_get("LINE_2_Y_FRAC", "0.65"))

# ── Telegram bildirishnomasi ──────────────────────────────────────────────────
TELEGRAM_TOKEN = _get("TELEGRAM_TOKEN")
# Ma'muriyat/qabulxona chat_id — barcha kelgan-ketganlar shu yerga tushadi.
NOTIFY_CHAT_ID = _get("NOTIFY_CHAT_ID")
# True bo'lsa, ota-onaning telegram_id siga shaxsiy xabar yuboriladi.
NOTIFY_PARENT = _get("NOTIFY_PARENT", "true").lower() == "true"

# ── CRM server ────────────────────────────────────────────────────────────────
# CRM API manzili (masalan: http://192.168.1.100:8000)
CRM_URL = _get("CRM_URL")
# Camera servis uchun alohida API kalit (backend .env dagi CAMERA_API_KEY bilan bir xil)
CAMERA_API_KEY = _get("CAMERA_API_KEY")
# CRM admin login (agar /camera/students route'i yo'q bo'lsa, fallback uchun)
CRM_ADMIN_USER = _get("CRM_ADMIN_USER")
CRM_ADMIN_PASS = _get("CRM_ADMIN_PASS")
# O'quvchilar ro'yxatini qancha vaqtda bir yangilash (soniya). Standart: 1 soat.
SYNC_INTERVAL = int(_get("SYNC_INTERVAL", "3600"))

# ── Ma'lumotlar bazasi (backend bilan bir xil) ────────────────────────────────
DATABASE_URL = _get("DATABASE_URL")  # bo'sh bo'lsa DB'siz (faqat log/telegram) ishlaydi

# ── Yuzlar bazasi ─────────────────────────────────────────────────────────────
# faces/<student_id>/*.jpg  ko'rinishida saqlanadi.
FACES_DIR = _get("FACES_DIR", os.path.join(os.path.dirname(__file__), "faces"))

# Encodinglar keshini saqlash fayli (qayta ishga tushirishda tezlashtiradi).
ENCODINGS_CACHE = _get("ENCODINGS_CACHE", os.path.join(os.path.dirname(__file__), "encodings.pkl"))

# Vaqtinchalik yuz rasmlari saqlanadigan papka (Telegramga yuborilgandan so'ng o'chiriladi).
TEMP_DIR = _get("TEMP_DIR", os.path.join(os.path.dirname(__file__), "temp"))

# ── Hisobot (XLSX) ────────────────────────────────────────────────────────────
EXCEL_LOG = _get("EXCEL_LOG", os.path.join(os.path.dirname(__file__), "davomat_log.xlsx"))

# ── AI (Claude) ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")

# ── Snapshot ──────────────────────────────────────────────────────────────────
# Telegramga qancha vaqtda bir kamera rasmi yuborilsin (soniya). 0 = o'chirilgan.
SNAPSHOT_INTERVAL = int(_get("SNAPSHOT_INTERVAL", "300"))
