"""Telegram orqali keldi/ketdi bildirishnomalarini yuboradi."""
import logging
from datetime import datetime

import requests

import config

log = logging.getLogger("camera.notify")

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(chat_id: str, text: str) -> None:
    if not config.TELEGRAM_TOKEN or not chat_id:
        log.info("[Telegram o'chirilgan] -> %s: %s", chat_id, text)
        return
    try:
        resp = requests.post(
            _API.format(token=config.TELEGRAM_TOKEN),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Telegram xatosi %s: %s", resp.status_code, resp.text)
    except Exception as exc:
        log.warning("Telegram yuborilmadi: %s", exc)


def notify_arrival(student: dict) -> None:
    """Bola keldi."""
    ts = datetime.now().strftime("%H:%M")
    name = student.get("full_name", f"ID {student.get('id')}")
    msg = f"✅ <b>{name}</b> markazga <b>keldi</b>\n🕒 {ts}"
    _dispatch(student, msg)


def notify_departure(student: dict) -> None:
    """Bola ketdi."""
    ts = datetime.now().strftime("%H:%M")
    name = student.get("full_name", f"ID {student.get('id')}")
    msg = f"🚪 <b>{name}</b> markazdan <b>ketdi</b>\n🕒 {ts}"
    _dispatch(student, msg)


def _dispatch(student: dict, msg: str) -> None:
    # Ma'muriyat chatiga
    if config.NOTIFY_CHAT_ID:
        _send(config.NOTIFY_CHAT_ID, msg)
    # Bolaning/ota-onaning shaxsiy chatiga
    if config.NOTIFY_STUDENT and student.get("telegram_id"):
        _send(str(student["telegram_id"]), msg)
