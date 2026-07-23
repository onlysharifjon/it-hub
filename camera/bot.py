"""Telegram bot — klaviatura savollarga javob + periodic snapshot."""
import io
import json
import os
import time
import logging
from datetime import datetime

import requests

import config
import shared

log = logging.getLogger("camera.bot")

_UZ_DAYS = {"Du": 0, "Se": 1, "Cho": 2, "Pa": 3, "Ju": 4, "Sha": 5, "Ya": 6}
_UZ_DAY_NAMES = [
    "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"
]
_MONTHS_UZ = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]

_BASE   = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"
_offset = 0


# ── Cache helpers ──────────────────────────────────────────────────────────────
def _load_students() -> list:
    try:
        cache = os.path.join(os.path.dirname(__file__), "cache", "students.json")
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _has_class_today(schedule: str) -> tuple:
    if not schedule:
        return False, ""
    parts    = schedule.strip().split()
    today_wd = datetime.today().weekday()
    days_str = parts[0]
    time_str = parts[1] if len(parts) > 1 else ""
    for d in days_str.split(","):
        if _UZ_DAYS.get(d.strip()) == today_wd:
            return True, time_str
    return False, time_str


# ── Context for Claude ─────────────────────────────────────────────────────────
def _build_context() -> str:
    now        = datetime.now()
    today      = now.strftime("%Y-%m-%d")
    wd         = _UZ_DAY_NAMES[now.weekday()]
    month_name = _MONTHS_UZ[now.month]
    students   = _load_students()

    lines = []
    for s in students:
        groups = s.get("groups", [])
        is_deb = s.get("is_debtor", False)
        gparts = []
        for g in groups:
            has_cls, t = _has_class_today(g.get("schedule", ""))
            mark = f"(bugun {t})" if has_cls else ""
            gparts.append(f"{g['name']} {g.get('schedule','?')} {mark}".strip())
        g_str   = "; ".join(gparts) or "guruhsiz"
        d_str   = "QARZDOR" if is_deb else "to'langan"
        lines.append(f"  {s['full_name']}: {g_str} | {month_name} {d_str}")

    events = shared.get_events()
    ev_lines = [f"  {e['time']} {e['name']} — {e['event_type']}" for e in events]

    s_txt = "\n".join(lines)   if lines    else "  (bo'sh)"
    e_txt = "\n".join(ev_lines) if ev_lines else "  (hali hech kim kelmadi)"

    return (
        f"Bugun: {today} ({wd})\n\n"
        f"O'quvchilar ({len(students)} ta):\n{s_txt}\n\n"
        f"Bugungi hodisalar:\n{e_txt}"
    )


# ── Smart keyword answers (Claudesiz) ─────────────────────────────────────────
def _keyword_answer(text: str) -> str | None:
    t = text.lower()

    if any(w in t for w in ["kim keldi", "keldi", "hozir kim", "bugun kim"]):
        events   = shared.get_events()
        arrivals = [e for e in events if e["event_type"] == "keldi"]
        if not arrivals:
            return "Hali hech kim kelmadi."
        lines = "\n".join(f"🕒 {e['time']} — {e['name']}" for e in arrivals)
        return f"✅ Bugun kelganlar ({len(arrivals)} ta):\n{lines}"

    if any(w in t for w in ["ketdi", "kim ketdi"]):
        events    = shared.get_events()
        departures = [e for e in events if e["event_type"] == "ketdi"]
        if not departures:
            return "Hali hech kim ketmadi."
        lines = "\n".join(f"🕒 {e['time']} — {e['name']}" for e in departures)
        return f"🚪 Bugun ketganlar ({len(departures)} ta):\n{lines}"

    if any(w in t for w in ["to'lov", "tolov", "qarzdor", "qarz"]):
        students = _load_students()
        debtors  = [s for s in students if s.get("is_debtor")]
        if not debtors:
            return "✅ Hamma o'quvchi to'lov qilgan!"
        lines = "\n".join(f"  • {s['full_name']}" for s in debtors)
        mn    = _MONTHS_UZ[datetime.now().month]
        return f"💸 {mn} oyida to'lamagan o'quvchilar ({len(debtors)} ta):\n{lines}"

    if any(w in t for w in ["dars", "jadval", "bugun dars", "qaysi dars"]):
        students = _load_students()
        today_cls = []
        for s in students:
            for g in s.get("groups", []):
                has_cls, t_str = _has_class_today(g.get("schedule", ""))
                if has_cls:
                    today_cls.append(f"  • {s['full_name']} → {g['name']} {t_str}")
        if not today_cls:
            return "Bugun hech kimda dars yo'q."
        wd = _UZ_DAY_NAMES[datetime.today().weekday()]
        lines = "\n".join(today_cls)
        return f"📅 {wd} — bugungi darslar:\n{lines}"

    if any(w in t for w in ["o'quvchi", "talaba", "hammasi", "ro'yxat", "royxat"]):
        students = _load_students()
        if not students:
            return "O'quvchilar ro'yxati bo'sh."
        lines = "\n".join(f"  {i+1}. {s['full_name']}" for i, s in enumerate(students))
        return f"👥 O'quvchilar ({len(students)} ta):\n{lines}"

    return None


# ── Claude API ─────────────────────────────────────────────────────────────────
def _ask_claude(question: str, context: str) -> str:
    system = (
        "Siz Minar Academy o'quv markazining aqlli kamera yordamchisisiz.\n"
        "Vazifangiz: o'quvchilar keldi/ketdi, dars jadvali va to'lov holati haqida "
        "qisqa, do'stona, o'zbek tilida javob berish. Javob 3-5 jumladan oshmasin.\n\n"
        f"Hozirgi ma'lumotlar:\n{context}"
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":    "claude-haiku-4-5-20251001",
                "max_tokens": 512,
                "system":   system,
                "messages": [{"role": "user", "content": question}],
            },
            timeout=30,
        )
        return resp.json()["content"][0]["text"]
    except Exception as exc:
        log.warning("Claude xatosi: %s", exc)
        return f"❌ Claude javob bermadi: {exc}"


def _answer(text: str) -> str:
    quick = _keyword_answer(text)
    if quick:
        return quick
    if config.ANTHROPIC_API_KEY:
        return _ask_claude(text, _build_context())
    return (
        "❓ Tushunmadim. Quyidagi so'zlarni ishlating:\n"
        "• <b>kim keldi</b> — bugun kelganlar\n"
        "• <b>kim ketdi</b> — ketganlar\n"
        "• <b>to'lov</b>   — qarzdorlar\n"
        "• <b>dars</b>     — bugungi jadval\n"
        "• <b>o'quvchi</b> — to'liq ro'yxat"
    )


# ── Telegram helpers ───────────────────────────────────────────────────────────
def _send_text(chat_id: int, text: str) -> None:
    try:
        requests.post(
            f"{_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as exc:
        log.debug("sendMessage xatosi: %s", exc)


def _send_photo_bytes(chat_id: int, data: bytes, caption: str = "") -> None:
    try:
        requests.post(
            f"{_BASE}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("snap.jpg", io.BytesIO(data), "image/jpeg")},
            timeout=30,
        )
    except Exception as exc:
        log.debug("sendPhoto xatosi: %s", exc)


def _get_updates() -> list:
    global _offset
    try:
        resp = requests.get(
            f"{_BASE}/getUpdates",
            params={"offset": _offset, "timeout": 20, "allowed_updates": ["message"]},
            timeout=25,
        )
        data = resp.json()
        if not data.get("ok"):
            return []
        updates = data.get("result", [])
        if updates:
            _offset = updates[-1]["update_id"] + 1
        return updates
    except Exception as exc:
        log.debug("getUpdates xatosi: %s", exc)
        return []


# ── Snapshot sender ────────────────────────────────────────────────────────────
def _snapshot_loop() -> None:
    if not config.SNAPSHOT_INTERVAL or config.SNAPSHOT_INTERVAL <= 0:
        return
    if not config.NOTIFY_CHAT_ID:
        return
    log.info("Snapshot: har %d soniyada rasm yuboriladi", config.SNAPSHOT_INTERVAL)
    while True:
        time.sleep(config.SNAPSHOT_INTERVAL)
        try:
            resp = requests.get("http://localhost:8765/snap", timeout=5)
            if resp.status_code == 200:
                now  = datetime.now().strftime("%H:%M")
                wd   = _UZ_DAY_NAMES[datetime.today().weekday()]
                events  = shared.get_events()
                present = [e["name"] for e in events if e["event_type"] == "keldi"]
                if present:
                    who = ", ".join(present[-5:])
                    caption = f"📷 {wd} {now} | Hozir: {who}"
                else:
                    caption = f"📷 {wd} {now} | Hozir hech kim yo'q"
                _send_photo_bytes(int(config.NOTIFY_CHAT_ID), resp.content, caption)
        except Exception as exc:
            log.debug("Snapshot xatosi: %s", exc)


# ── Main polling loop ──────────────────────────────────────────────────────────
def run() -> None:
    import threading
    if not config.TELEGRAM_TOKEN:
        log.warning("TELEGRAM_TOKEN yo'q — bot ishlamaydi")
        return

    threading.Thread(target=_snapshot_loop, daemon=True).start()
    log.info("Telegram bot ishga tushdi (polling + snapshot)")

    while True:
        try:
            for update in _get_updates():
                msg    = update.get("message", {})
                text   = msg.get("text", "").strip()
                chat_id = msg.get("chat", {}).get("id")
                if not text or not chat_id:
                    continue
                if text.startswith("/"):
                    if text.startswith("/start") or text.startswith("/help"):
                        _send_text(chat_id, (
                            "👋 Salom! Men Minar Academy AI yordamchisiman.\n\n"
                            "So'rang:\n"
                            "• <b>kim keldi</b>\n"
                            "• <b>kim ketdi</b>\n"
                            "• <b>to'lov</b> — qarzdorlar\n"
                            "• <b>dars</b> — bugungi jadval\n"
                            "• <b>o'quvchi</b> — ro'yxat"
                        ))
                    continue
                reply = _answer(text)
                _send_text(chat_id, reply)
        except Exception as exc:
            log.warning("Bot loop xatosi: %s", exc)
            time.sleep(5)
