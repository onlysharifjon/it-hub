"""Telegram orqali keldi/ketdi bildirishnomalarini yuboradi."""
import os
import time
import logging
from datetime import datetime

import requests

import config

_UZ_DAYS = {"Du": 0, "Se": 1, "Cho": 2, "Pa": 3, "Ju": 4, "Sha": 5, "Ya": 6}


def _has_class_today(schedule: str) -> tuple[bool, str]:
    if not schedule:
        return False, ""
    parts = schedule.strip().split()
    today_wd = datetime.today().weekday()
    days_str = parts[0]
    time_str = parts[1] if len(parts) > 1 else ""
    for d in days_str.split(","):
        if _UZ_DAYS.get(d.strip()) == today_wd:
            return True, time_str
    return False, time_str

log = logging.getLogger("camera.notify")

_TG = "https://api.telegram.org/bot{token}"


def _send_text(chat_id: str, text: str) -> None:
    if not config.TELEGRAM_TOKEN or not chat_id:
        log.info("[Telegram o'chirilgan] text -> %s: %s", chat_id, text)
        return
    try:
        resp = requests.post(
            f"{_TG.format(token=config.TELEGRAM_TOKEN)}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Telegram text xatosi %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        log.warning("Telegram text yuborilmadi: %s", exc)


def _send_photo(chat_id: str, photo_path: str, caption: str) -> None:
    """Foto + sarlavha yuboradi."""
    if not config.TELEGRAM_TOKEN or not chat_id:
        log.info("[Telegram o'chirilgan] photo -> %s: %s", chat_id, caption)
        return
    if not photo_path or not os.path.exists(photo_path):
        _send_text(chat_id, caption)
        return
    try:
        with open(photo_path, "rb") as photo_file:
            resp = requests.post(
                f"{_TG.format(token=config.TELEGRAM_TOKEN)}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": ("frame.jpg", photo_file, "image/jpeg")},
                timeout=30,
            )
        if resp.status_code != 200:
            log.warning("Telegram photo xatosi %s: %s", resp.status_code, resp.text[:200])
            _send_text(chat_id, caption)
    except Exception as exc:
        log.warning("Telegram photo yuborilmadi: %s", exc)
        _send_text(chat_id, caption)


def _cleanup(photo_path: str | None) -> None:
    """Vaqtinchalik rasm faylini o'chiradi."""
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except Exception as exc:
            log.warning("Faylni o'chirib bo'lmadi %s: %s", photo_path, exc)


def notify_arrival(student: dict, photo_path: str | None = None) -> None:
    """O'quvchi markazga keldi."""
    ts     = datetime.now().strftime("%H:%M")
    name   = student.get("full_name", f"ID {student.get('id')}")
    groups = student.get("groups", [])
    group_str = ", ".join(g["name"] for g in groups) if groups else "—"

    # Bugungi dars vaqtini aniqlash
    schedule_line = ""
    for g in groups:
        has_cls, t = _has_class_today(g.get("schedule", ""))
        if has_cls and t:
            schedule_line = f"\n📅 Bugun dars: <b>{g['name']}</b> — soat {t}"
            break

    # To'lov holati
    debt_line = ""
    if student.get("is_debtor"):
        debt_line = "\n💸 <b>Oylik to'lov amalga oshmagan!</b>"

    school_msg = (
        f"✅ <b>{name}</b> markazga <b>keldi</b>\n"
        f"🕒 {ts}\n"
        f"📚 Guruh: {group_str}"
        f"{schedule_line}"
        f"{debt_line}"
    )
    if config.NOTIFY_CHAT_ID:
        _send_photo(config.NOTIFY_CHAT_ID, photo_path, school_msg)
        photo_path = None

    # Ota-onaga shaxsiy xabar
    if config.NOTIFY_PARENT and student.get("telegram_id"):
        parent_msg = (
            f"✅ Farzandingiz <b>{name}</b> o'quv markazga <b>keldi</b>\n"
            f"🕒 Vaqt: {ts}"
            f"{schedule_line}"
        )
        if student.get("is_debtor"):
            parent_msg += "\n💸 Eslatma: bu oylik to'lov amalga oshmagan."
        _send_text(str(student["telegram_id"]), parent_msg)

    _cleanup(photo_path)


_last_unknown: float = 0.0


def notify_unknown(photo_path: str | None = None) -> None:
    """Noma'lum yuz — cooldown bilan Telegramga yuboradi."""
    global _last_unknown
    now = time.time()
    if now - _last_unknown < config.NOTIFY_COOLDOWN:
        _cleanup(photo_path)
        return
    _last_unknown = now
    ts  = datetime.now().strftime("%H:%M")
    msg = f"⚠️ <b>Noma'lum shaxs</b> aniqlandi!\n🕒 {ts}"
    if config.NOTIFY_CHAT_ID:
        _send_photo(config.NOTIFY_CHAT_ID, photo_path, msg)
    else:
        _cleanup(photo_path)


def notify_departure(student: dict, photo_path: str | None = None) -> None:
    """O'quvchi markazdan ketdi."""
    ts = datetime.now().strftime("%H:%M")
    name = student.get("full_name", f"ID {student.get('id')}")

    school_msg = f"🚪 <b>{name}</b> markazdan <b>ketdi</b>\n🕒 {ts}"

    if config.NOTIFY_CHAT_ID:
        _send_photo(config.NOTIFY_CHAT_ID, photo_path, school_msg)
        photo_path = None

    if config.NOTIFY_PARENT and student.get("telegram_id"):
        parent_msg = (
            f"🚪 Farzandingiz <b>{name}</b> o'quv markazdan <b>ketdi</b>\n"
            f"🕒 Vaqt: {ts}"
        )
        _send_text(str(student["telegram_id"]), parent_msg)

    _cleanup(photo_path)
