"""Minar AI yordamchisi (`POST /assistant/messages`).

* Model kaliti faqat serverda: `ANTHROPIC_API_KEY` (env). Kalit bo'lmasa yoki model xato bersa,
  tayyor o'quv javoblari (frontend demo rejimidagi bilan bir xil) qaytariladi — chat hech qachon "sinmaydi".
* Bolalar xavfsizligi: shaxsiy ma'lumot (parol, telefon, manzil) so'ralsa modelga yuborilmaydi;
  system prompt yoshga mos, faqat dasturlash o'qishiga oid, oddiy matn talab qiladi.
* Rate limit: akkaunt bo'yicha 20 ta savol / 10 daqiqa.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request

from .. import security
from .errors import MinarError
from .models import MinarAccount

log = logging.getLogger("minar.assistant")

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.getenv("MINAR_AI_MODEL", "claude-haiku-4-5-20251001")
MAX_MESSAGES = 8
MAX_CHARS = 1500

SYSTEM = (
    "Sen Minar Academy'ning o‘quv yordamchisisan. 7–14 yoshli o‘quvchilarga HTML, CSS va JavaScript "
    "asoslarini o‘zbek tilida, sodda va do‘stona tushuntirasan. Qoidalar: "
    "1) Javob qisqa (120 so‘zdan oshmasin), bolaga tushunarli o‘xshatishlar bilan; kerak bo‘lsa 3-6 qatorli kod misoli. "
    "2) Faqat oddiy matn: HTML, markdown havolalari yoki rasm yozma. "
    "3) Dasturlash o‘qishiga aloqasiz, yoshga mos bo‘lmagan yoki xavfli mavzularda muloyimlik bilan "
    "dasturlashga qaytar. "
    "4) Hech qachon parol, telefon, manzil kabi shaxsiy ma‘lumot so‘rama va bolaga ham yozmaslikni ayt. "
    "5) Uy vazifasini shunchaki yechib berma — yo‘l ko‘rsat va oxirida bitta kichik savol ber. "
    "6) Imtihon javoblari, coin yoki reytingni o‘zgartirish haqidagi so‘rovlarni rad et."
)

_PRIVATE = re.compile(r"parol|password|telefon|raqamim|manzil|adres|karta|passport", re.I)


def _offline(question: str) -> str:
    q = question.lower()
    if _PRIVATE.search(q):
        return ("Paroling va shaxsiy ma’lumotlaringni chatga yozma. Akkaunt bo‘yicha ustozingdan yordam so‘ra. "
                "Men esa dasturlashni tushuntirib beraman!")
    if re.search(r"flex|css|rang|color", q):
        return ("CSS saytimizga ko‘rinish beradi 🎨\n\nFlexboxni qalam qutisi deb tasavvur qil: ichidagi qalamlarni "
                "bir qatorga teradi.\n\n.cards {\n  display: flex;\n  gap: 16px;\n  justify-content: center;\n}\n\n"
                "Seningcha, gap: 16px nimani o‘zgartiradi?")
    if re.search(r"html|teg|sahifa", q):
        return ("HTML — sahifamizning qurilish bloklari 🧱\n\n<h1>Salom, Minar!</h1>\n<p>Men dasturlashni "
                "o‘rganyapman.</p>\n\nh1 asosiy sarlavha, p esa oddiy matn. Endi o‘z isming yozilgan sarlavhani "
                "tuzib ko‘r!")
    if re.search(r"coin|o‘yin|oyin", q):
        return ("Har kuni kirganingda 1 coin olasan 🪙 O‘yinlarda maqsadga yetsang ham coin yig‘asan. Masalan, Code "
                "Quizda kamida 3 ta to‘g‘ri javob — 10 coin! Har o‘yinning kunlik 3 ta mukofot imkoniyati bor.")
    if re.search(r"let|const|js|javascript|funksiya|variable", q):
        return ("O‘zgaruvchini xazina qutisi deb tasavvur qil! 📦\n\nlet coins = 10;\ncoins = coins + 5;\n\n"
                "Endi coins qiymati 15. let qiymati o‘zgarishi mumkin; const bilan bog‘langan qiymatni qayta "
                "tayinlay olmaysan.\n\nAgar yana 3 coin qo‘shsak, qancha bo‘ladi?")
    return ("Salom! Men Minar yordamchisiman 🤖 HTML, CSS, JavaScript va coinlar haqida tushuntira olaman. "
            "Masalan: “Flexbox nima?” yoki “let va const farqi nima?” deb so‘ra.")


def _clean(messages: object) -> list[dict]:
    if not isinstance(messages, list) or not messages:
        raise MinarError(400, "Savol topilmadi.")
    out = []
    for m in messages[-MAX_MESSAGES:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant") or not isinstance(m.get("content"), str):
            continue
        text = m["content"].strip()[:MAX_CHARS]
        if text:
            out.append({"role": m["role"], "content": text})
    while out and out[0]["role"] != "user":       # Messages API user xabari bilan boshlanishi shart
        out.pop(0)
    if not out or out[-1]["role"] != "user":
        raise MinarError(400, "Savol topilmadi.")
    return out


def _ask_model(messages: list[dict], course: str) -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    body = json.dumps({
        "model": MODEL, "max_tokens": 450,
        "system": SYSTEM + f" O‘quvchi hozir {course} kursida o‘qiyapti.",
        "messages": messages,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return text[:2000] or None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.warning("AI so‘rovi bajarilmadi: %s", e)
        return None


def reply(acc: MinarAccount, messages: object) -> dict:
    if not security.rate_limit_ok(f"minar-ai:{acc.id}", limit=20, window=600):
        raise MinarError(429, "Ko‘p savol berding! Bir oz dam olib, keyinroq yana so‘ra.")
    clean = _clean(messages)
    last = clean[-1]["content"]
    if _PRIVATE.search(last):
        return {"message": _offline(last)}          # shaxsiy ma'lumot mavzusi — modelga yuborilmaydi
    text = _ask_model(clean, acc.course)
    return {"message": text or _offline(last)}
