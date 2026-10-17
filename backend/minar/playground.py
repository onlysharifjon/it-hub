"""Kod maydoni: HTML/CSS/JS topshiriqlari va ularni serverda tekshirish.

Tekshiruv statik: HTML — `html.parser` bilan daraxt, CSS — qoidalar (`@media` ichidagilari ham),
JS — kalit tuzilmalar + brauzer sandbox'ida (iframe) olingan `console.log` natijasi.
JS natijasini mijoz yuboradi, shuning uchun har topshiriq mukofoti bir martalik va kichik.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from .. import tz
from .errors import MinarError
from .models import MinarAccount, MinarLedger, MinarPlaygroundSolve

CODE_MAX = 20_000
OUTPUT_LINES_MAX = 100
OUTPUT_LINE_MAX = 300
REWARD = 5
XP = 30


# ── HTML ────────────────────────────────────────────────────────────────────

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


@dataclass
class Node:
    tag: str
    attrs: dict
    parent: Optional["Node"] = None
    children: list = field(default_factory=list)
    text: str = ""

    def all_text(self) -> str:
        return (self.text + " ".join(c.all_text() for c in self.children)).strip()

    def walk(self):
        for c in self.children:
            yield c
            yield from c.walk()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, {k: (v or "") for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text += data


def parse_html(src: str) -> Node:
    b = _TreeBuilder()
    b.feed(src)
    b.close()
    return b.root


def find(root: Node, tag: str) -> list[Node]:
    return [n for n in root.walk() if n.tag == tag]


# ── CSS ─────────────────────────────────────────────────────────────────────

_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def parse_css(src: str) -> list[tuple[str, dict, Optional[str]]]:
    """[(selector, {prop: value}, media|None)] — har bir selector alohida, @media bir daraja."""
    src = _COMMENT.sub("", src)
    out: list[tuple[str, dict, Optional[str]]] = []

    def rules(block: str, media: Optional[str]) -> None:
        i = 0
        while i < len(block):
            open_ = block.find("{", i)
            if open_ < 0:
                return
            head = block[i:open_].strip()
            depth, j = 1, open_ + 1
            while j < len(block) and depth:
                depth += {"{": 1, "}": -1}.get(block[j], 0)
                j += 1
            body = block[open_ + 1:j - 1]
            if head.startswith("@media"):
                rules(body, head[6:].strip())
            elif not head.startswith("@"):
                decls = {}
                for part in body.split(";"):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        if k.strip():
                            decls[k.strip().lower()] = v.strip().lower()
                for sel in head.split(","):
                    out.append((" ".join(sel.split()).lower(), decls, media))
            i = j

    rules(src, None)
    return out


def css_value(rules, selector: str, prop: str, media: bool = False) -> Optional[str]:
    val = None
    for sel, decls, m in rules:
        if sel == selector and (m is not None) == media and prop in decls:
            val = decls[prop]
    return val


# ── Tekshiruvlar ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Check:
    label: str
    fn: Callable[[dict], bool]


def _has(tag: str, *, text: str | None = None, attrs: tuple[str, ...] = (), min_text: int = 0) -> Callable:
    def fn(ctx: dict) -> bool:
        for n in find(ctx["dom"], tag):
            t = n.all_text()
            if text and text.lower() not in t.lower():
                continue
            if len(t) < min_text:
                continue
            if all(n.attrs.get(a, "").strip() for a in attrs):
                return True
        return False
    return fn


def _children(parent: str, child: str, n: int) -> Callable:
    return lambda ctx: any(sum(1 for c in p.children if c.tag == child) >= n for p in find(ctx["dom"], parent))


def _attr(tag: str, name: str, pred: Callable[[str], bool]) -> Callable:
    return lambda ctx: any(pred(e.attrs.get(name, "").strip()) for e in find(ctx["dom"], tag))


def _css(selector: str, prop: str, pred: Callable[[str], bool] = bool, media: bool = False) -> Callable:
    def fn(ctx: dict) -> bool:
        v = css_value(ctx["css"], selector, prop, media)
        return v is not None and pred(v)
    return fn


def _css_any(selector: str, props: tuple[str, ...]) -> Callable:
    return lambda ctx: any(css_value(ctx["css"], selector, p) for p in props)


def _js(pattern: str) -> Callable:
    rx = re.compile(pattern)
    return lambda ctx: bool(rx.search(_COMMENT.sub("", re.sub(r"//[^\n]*", "", ctx["js"]))))


def _all(*fns: Callable) -> Callable:
    return lambda ctx: all(f(ctx) for f in fns)


def _output(*lines: str) -> Callable:
    return lambda ctx: ctx["output"] == list(lines)


def _px(v: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?(px|rem|em|%)", v))


@dataclass(frozen=True)
class Task:
    id: str
    course: str
    title: str
    prompt: str
    starter: dict
    checks: tuple[Check, ...]
    hint: str = ""

    @property
    def languages(self) -> list[str]:
        return [k for k in ("html", "css", "js") if k in self.starter]


CSS_PAGE = """<h1 class="title">Minar Academy</h1>
<div class="row">
  <div class="card"><p>HTML</p></div>
  <div class="card"><p>CSS</p></div>
  <div class="card"><p>JavaScript</p></div>
</div>
<button>Boshlash</button>"""

TASKS: tuple[Task, ...] = (
    # ── HTML ──
    Task("html-1", "HTML", "Birinchi sarlavha", "Ichida “Salom” so‘zi bor eng katta sarlavha (h1) yoz.",
         {"html": "<!-- Kodingni shu yerga yoz -->\n"},
         (Check("h1 sarlavha bor", _has("h1")), Check("Sarlavhada “Salom” so‘zi bor", _has("h1", text="salom"))),
         "<h1>Salom, Minar!</h1>"),
    Task("html-2", "HTML", "Men haqimda", "h1 sarlavha va o‘zing haqingda kamida 20 harfli abzas (p) yoz.",
         {"html": "<h1></h1>\n"},
         (Check("h1 sarlavha bor va bo‘sh emas", _has("h1", min_text=2)),
          Check("Kamida 20 harfli abzas (p) bor", _has("p", min_text=20))),
         "<p>Men 12 yoshman va dasturchi bo‘lmoqchiman.</p>"),
    Task("html-3", "HTML", "Rasm qo‘sh", "Rasm qo‘sh: src manzili va rasmni ta’riflovchi alt matni bo‘lsin.",
         {"html": "<h1>Mening robotim</h1>\n"},
         (Check("img tegi bor", _has("img")), Check("src manzili yozilgan", _has("img", attrs=("src",))),
          Check("alt matni yozilgan", _has("img", attrs=("alt",)))),
         '<img src="https://picsum.photos/200" alt="Robot rasmi">'),
    Task("html-4", "HTML", "Havola", "https:// bilan boshlanadigan manzilga havola (a) yasang, havola matni bo‘lsin.",
         {"html": ""},
         (Check("a tegi bor", _has("a")),
          Check("href https:// bilan boshlanadi", _attr("a", "href", lambda v: v.startswith("https://"))),
          Check("Havola matni bor", _has("a", min_text=2))),
         '<a href="https://minaracademy.uz">Minar Academy</a>'),
    Task("html-5", "HTML", "Sevimli o‘yinlar", "Kamida 3 ta elementli tartibsiz ro‘yxat (ul + li) yasang.",
         {"html": "<h2>Sevimli o‘yinlarim</h2>\n"},
         (Check("ul ro‘yxat bor", _has("ul")), Check("ul ichida kamida 3 ta li", _children("ul", "li", 3))),
         "<ul>\n  <li>Minecraft</li>\n  ...\n</ul>"),
    Task("html-6", "HTML", "Qadamma-qadam", "Choy damlash bosqichlarini raqamli ro‘yxatda (ol) kamida 3 qadam qilib yoz.",
         {"html": ""},
         (Check("ol ro‘yxat bor", _has("ol")), Check("ol ichida kamida 3 ta li", _children("ol", "li", 3))),
         "<ol>\n  <li>Suv qaynat</li>\n  ...\n</ol>"),
    Task("html-7", "HTML", "Ro‘yxatdan o‘tish formasi", "Forma yasang: label, matn maydoni (input) va yuborish tugmasi bo‘lsin.",
         {"html": "<form>\n  \n</form>\n"},
         (Check("form bor", _has("form")), Check("label bor", _has("label", min_text=1)),
          Check("input bor", _has("input")), Check("button bor", _has("button", min_text=1))),
         '<label for="ism">Ism</label>\n<input id="ism" type="text">\n<button>Yuborish</button>'),
    Task("html-8", "HTML", "Dars jadvali", "Jadval (table) yasang: sarlavha katakchalari (th) va kamida 2 ta qator (tr) bo‘lsin.",
         {"html": "<table>\n  \n</table>\n"},
         (Check("table bor", _has("table")), Check("th katakcha bor", _has("th", min_text=1)),
          Check("Kamida 2 ta tr qator", lambda ctx: len(find(ctx["dom"], "tr")) >= 2)),
         "<tr><th>Kun</th><th>Fan</th></tr>"),
    # ── CSS ──
    Task("css-1", "CSS", "Rangli sarlavha", ".title sarlavhasiga rang bering (color).",
         {"html": CSS_PAGE, "css": ".title {\n  \n}\n"},
         (Check(".title uchun color yozilgan", _css(".title", "color")),), ".title { color: teal; }"),
    Task("css-2", "CSS", "Sahifa foni", "body uchun fon rangi bering (background-color yoki background).",
         {"html": CSS_PAGE, "css": "body {\n  \n}\n"},
         (Check("body foni berilgan", _css_any("body", ("background-color", "background"))),),
         "body { background-color: #f4f8f5; }"),
    Task("css-3", "CSS", "Chiroyli karta", ".card ga ichki bo‘shliq (padding) va yumaloq burchak (border-radius) bering.",
         {"html": CSS_PAGE, "css": ".card {\n  \n}\n"},
         (Check(".card padding o‘lcham bilan", _css(".card", "padding", lambda v: bool(re.search(r"\d", v)))),
          Check(".card border-radius o‘lcham bilan", _css(".card", "border-radius", _px))),
         ".card { padding: 16px; border-radius: 12px; }"),
    Task("css-4", "CSS", "O‘rtaga", ".title matnini o‘rtaga tekislang.",
         {"html": CSS_PAGE, "css": ""},
         (Check(".title text-align: center", _css(".title", "text-align", lambda v: v == "center")),),
         ".title { text-align: center; }"),
    Task("css-5", "CSS", "Flexbox qatori", ".row ni flex konteyner qiling va kartalar orasiga gap bering.",
         {"html": CSS_PAGE, "css": ".row {\n  \n}\n"},
         (Check(".row display: flex", _css(".row", "display", lambda v: v == "flex")),
          Check(".row gap o‘lcham bilan", _css(".row", "gap", _px))),
         ".row { display: flex; gap: 12px; }"),
    Task("css-6", "CSS", "Hover effekti", "Sichqoncha ustiga kelganda tugma rangini o‘zgartiring (button:hover).",
         {"html": CSS_PAGE, "css": "button {\n  background-color: #20977a;\n  color: white;\n}\n"},
         (Check("button:hover qoidasi rang o‘zgartiradi",
                _css_any("button:hover", ("background-color", "background", "color"))),),
         "button:hover { background-color: #157a62; }"),
    Task("css-7", "CSS", "Shrift", "p uchun shrift o‘lchami (font-size) va qalinlik (font-weight: bold yoki 600+) bering.",
         {"html": CSS_PAGE, "css": "p {\n  \n}\n"},
         (Check("p font-size o‘lcham bilan", _css("p", "font-size", _px)),
          Check("p qalin (bold yoki 600+)", _css("p", "font-weight",
                                                 lambda v: v in ("bold", "bolder") or (v.isdigit() and int(v) >= 600)))),
         "p { font-size: 18px; font-weight: bold; }"),
    Task("css-8", "CSS", "Telefon uchun", "@media (max-width: 600px) ichida .row ni ustun qiling (flex-direction: column).",
         {"html": CSS_PAGE, "css": ".row {\n  display: flex;\n  gap: 12px;\n}\n"},
         (Check("@media ichida .row flex-direction: column",
                _css(".row", "flex-direction", lambda v: v == "column", media=True)),),
         "@media (max-width: 600px) {\n  .row { flex-direction: column; }\n}"),
    # ── JavaScript ──
    Task("js-1", "JavaScript", "Salom, dunyo!", "Konsolga aynan shu matnni chiqar: Salom, Minar!",
         {"js": "// console.log yordamida yoz\n"},
         (Check("console.log ishlatilgan", _js(r"console\.log\s*\(")),
          Check("Natija: Salom, Minar!", _output("Salom, Minar!"))),
         'console.log("Salom, Minar!");'),
    Task("js-2", "JavaScript", "Coin hisoblagich", "let coins = 10 yarating, unga 5 qo‘shing va natijani konsolga chiqaring (15).",
         {"js": "let coins = 10;\n"},
         (Check("let bilan o‘zgaruvchi", _js(r"\blet\s+coins\b")),
          Check("Qiymat o‘zgartirilgan (+= yoki =)", _js(r"coins\s*(\+=|=\s*coins\s*\+)")),
          Check("Natija: 15", _output("15"))),
         "coins += 5;\nconsole.log(coins);"),
    Task("js-3", "JavaScript", "Shart", "const age = 12. Agar age 10 dan katta yoki teng bo‘lsa “Katta”, aks holda “Kichik” chiqaring.",
         {"js": "const age = 12;\n"},
         (Check("if ishlatilgan", _js(r"\bif\s*\(")), Check("else ishlatilgan", _js(r"\belse\b")),
          Check("Natija: Katta", _output("Katta"))),
         'if (age >= 10) {\n  console.log("Katta");\n} else { ... }'),
    Task("js-4", "JavaScript", "1 dan 5 gacha", "for sikli bilan 1 dan 5 gacha sonlarni har birini alohida qatorga chiqaring.",
         {"js": ""},
         (Check("for sikli ishlatilgan", _js(r"\bfor\s*\(")), Check("Natija: 1 2 3 4 5", _output("1", "2", "3", "4", "5"))),
         "for (let i = 1; i <= 5; i++) {\n  console.log(i);\n}"),
    Task("js-5", "JavaScript", "Qo‘shuvchi funksiya", "add(a, b) funksiyasini yozing (yig‘indini return qilsin) va add(2, 3) natijasini chiqaring.",
         {"js": "function add(a, b) {\n  \n}\n"},
         (Check("add funksiyasi e’lon qilingan", _js(r"function\s+add\s*\(|(const|let)\s+add\s*=")),
          Check("return ishlatilgan", _js(r"\breturn\b")), Check("Natija: 5", _output("5"))),
         "return a + b;\n...\nconsole.log(add(2, 3));"),
    Task("js-6", "JavaScript", "Massiv uzunligi", "3 ta mevadan iborat massiv yarating va uning uzunligini chiqaring.",
         {"js": "const fruits = [];\n"},
         (Check("Massiv yaratilgan", _js(r"=\s*\[")), Check(".length ishlatilgan", _js(r"\.length\b")),
          Check("Natija: 3", _output("3"))),
         'const fruits = ["olma", "nok", "uzum"];\nconsole.log(fruits.length);'),
    Task("js-7", "JavaScript", "Kurslar ro‘yxati", "[\"HTML\", \"CSS\", \"JS\"] massivining har bir elementini sikl bilan alohida chiqaring.",
         {"js": 'const courses = ["HTML", "CSS", "JS"];\n'},
         (Check("Sikl (for / forEach) ishlatilgan", _js(r"\bfor\s*\(|\.forEach\s*\(")),
          Check("Natija: HTML CSS JS", _output("HTML", "CSS", "JS"))),
         "courses.forEach(c => console.log(c));"),
    Task("js-8", "JavaScript", "Qahramon obyekti", "name: \"Robo\" va level: 3 xossali hero obyektini yarating, hero.name ni chiqaring.",
         {"js": "const hero = {\n  \n};\n"},
         (Check("Obyektda name va level bor", _all(_js(r"name\s*:"), _js(r"level\s*:"))),
          Check("level: 3", _js(r"level\s*:\s*3\b")), Check("Natija: Robo", _output("Robo"))),
         'const hero = { name: "Robo", level: 3 };\nconsole.log(hero.name);'),
)
BY_ID = {t.id: t for t in TASKS}


# ── API ─────────────────────────────────────────────────────────────────────

def _solved(db: Session, acc: MinarAccount) -> dict[str, MinarPlaygroundSolve]:
    return {s.task_id: s for s in db.query(MinarPlaygroundSolve).filter(MinarPlaygroundSolve.account_id == acc.id)}


def task_list(db: Session, acc: MinarAccount) -> dict:
    solved = _solved(db, acc)
    tasks = []
    for t in TASKS:
        s = solved.get(t.id)
        code = None
        if s:
            try:
                code = json.loads(s.code)
            except ValueError:
                code = None
        tasks.append({"id": t.id, "course": t.course, "title": t.title, "prompt": t.prompt,
                      "starter": t.starter, "languages": t.languages, "hint": t.hint,
                      "checks": [c.label for c in t.checks], "reward": REWARD, "xp": XP,
                      "solved": s is not None, "solvedAt": tz.isoformat(s.solved_at) if s else None, "code": code})
    return {"tasks": tasks, "solved": len(solved), "total": len(TASKS)}


def _code(payload: dict, key: str) -> str:
    v = payload.get(key) or ""
    if not isinstance(v, str) or len(v) > CODE_MAX:
        raise MinarError(400, "Kod juda uzun yoki noto‘g‘ri.")
    return v


def _output_lines(payload: dict) -> list[str]:
    out = payload.get("output") or []
    if not isinstance(out, list) or len(out) > OUTPUT_LINES_MAX or not all(isinstance(x, str) for x in out):
        raise MinarError(400, "Konsol natijasi noto‘g‘ri.")
    return [x[:OUTPUT_LINE_MAX].strip() for x in out]


def evaluate(task: Task, payload: dict) -> list[dict]:
    html, css, js = _code(payload, "html"), _code(payload, "css"), _code(payload, "js")
    from .js_runner import execute
    _output_lines(payload)  # Validate legacy field size; its values never determine rewards.
    execution = execute(js, task.id) if "js" in task.languages else {"output": [], "semantic": True}
    ctx = {"dom": parse_html(html), "css": parse_css(css), "js": js, "output": execution["output"]}
    results = []
    for c in task.checks:
        try:
            ok = bool(c.fn(ctx))
        except Exception:     # foydalanuvchi kodi har qanday shaklda bo'lishi mumkin — tekshiruv yiqilmasin
            ok = False
        results.append({"label": c.label, "ok": ok})
    if "js" in task.languages:
        results.append({"label": execution.get("error") or "Serverda bajarish va qo‘shimcha tekshiruv", "ok": not execution.get("error") and execution.get("semantic", False)})
    return results


def check(db: Session, acc: MinarAccount, task_id: str, payload: Any) -> tuple[list[dict], bool, bool]:
    """(natijalar, hammasi to'g'rimi, birinchi marta yechildimi). Commit qilmaydi."""
    task = BY_ID.get(task_id)
    if not task:
        raise MinarError(404, "Topshiriq topilmadi.")
    if not isinstance(payload, dict):
        raise MinarError(400, "Kod topilmadi.")
    results = evaluate(task, payload)
    ok = all(r["ok"] for r in results)
    if not ok:
        return results, False, False
    existing = db.query(MinarPlaygroundSolve).filter(MinarPlaygroundSolve.account_id == acc.id,
                                                     MinarPlaygroundSolve.task_id == task.id).first()
    code = json.dumps({k: payload.get(k) or "" for k in task.languages}, ensure_ascii=False)
    now = datetime.utcnow()
    if existing:
        existing.code = code
        return results, True, False
    db.add(MinarPlaygroundSolve(account_id=acc.id, task_id=task.id, code=code, xp=XP, solved_at=now))
    # kind "lesson": kunlik "dars" topshirig'i kod maydonidagi yechim bilan ham bajariladi
    db.add(MinarLedger(account_id=acc.id, ref_key=f"playground:{task.id}", kind="lesson",
                       title=f"Kod maydoni: {task.title}", amount=REWARD,
                       local_date=tz.today().isoformat(), created_at=now))
    acc.xp += XP
    return results, True, True
