"""Statik katalog — frontenddagi `lib/minar/data.js` ning server nusxasi.

Narxlar, buyum ID'lari va quiz javoblari serverda saqlanadi: client yuborgan
narx/javobga ishonilmaydi. `data.js` o'zgarsa, shu fayl ham yangilanadi.
"""
from __future__ import annotations

COURSES = ("HTML", "CSS", "JavaScript")
CHARACTERS = ("robo", "foxy", "drako")
CHARACTER_EMOJI = {"robo": "🤖", "foxy": "🦊", "drako": "🐲"}
SLOTS = ("hat", "accessory", "outfit", "background")

# id -> (nomi, kategoriya, slot, narx)
PRODUCTS = {
    "headphones": ("Kosmik quloqchin", "hero", "accessory", 120),
    "crown": ("Chempion toji", "hero", "hat", 250),
    "cap": ("Dasturchi kepkasi", "hero", "hat", 65),
    "glasses": ("Pixel ko‘zoynak", "hero", "accessory", 85),
    "hoodie": ("Minar xudisi", "hero", "outfit", 150),
    "space": ("Galaktika foni", "hero", "background", 100),
    "shirt": ("Yulduzli futbolka", "hero", "outfit", 75),
    "forest": ("Yashil sayyora", "hero", "background", 90),
    "stickers": ("Minar stikerlar to‘plami", "space", None, 80),
    "notebook": ("G‘oyalar daftari", "space", None, 180),
    "mouse": ("Gaming sichqoncha", "space", None, 650),
    "keyboard": ("Mexanik klaviatura", "space", None, 1200),
}

LESSONS_PER_COURSE = 3
LESSON_COIN = 5
LESSON_XP = 50
CHECKIN_COIN = 1
QUEST_COIN = 5
QUESTS = ("typing", "games", "lesson")

LEVEL_XP = 300
XP_WIN = 50
XP_TRY = 10

DAILY_REWARDED_GAMES = 3
GAME_BASE = {"typing": 10, "ztype": 15, "quiz": 10, "memory": 8, "bug": 10, "battle": 15}
GAME_TITLE = {
    "typing": "Minar Type", "ztype": "ZType Galaxy", "quiz": "Code Quiz",
    "memory": "Memory Match", "bug": "Bug Hunter", "battle": "Battle",
}

# Code Quiz (5 savol) — to'g'ri javob indekslari (battle quiz'i ham shundan foydalanadi)
QUIZ_ANSWERS = {
    "HTML": [0, 1, 2, 3, 0],
    "CSS": [1, 2, 3, 0, 2],
    "JavaScript": [0, 1, 2, 3, 0],
}
QUIZ_TOTAL = 5
BUG_TOTAL = 3
MEMORY_PAIRS = 6

# Typing battle matni (frontend `battle.jsx` dagi `battleText` bilan bir xil)
BATTLE_TEXT = (
    "hello minar code your dreams learn html style with css create with javascript "
    "every small step makes you a better developer"
)
BATTLE_SECONDS = 60

# CRM guruh bosqichi -> kurs (akkaunt yaratilganda standart; xodim o'zgartira oladi)
STAGE_DEFAULT_COURSE = {"foundation": "HTML"}
DEFAULT_COURSE_OTHER = "JavaScript"


def default_course_for_stage(stage: str | None) -> str:
    return STAGE_DEFAULT_COURSE.get((stage or "").lower(), DEFAULT_COURSE_OTHER)


def level_of(xp: int) -> int:
    return xp // LEVEL_XP + 1
