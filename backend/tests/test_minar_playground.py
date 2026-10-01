"""Kod maydoni: topshiriqlar tekshiruvi (har biriga namunaviy yechim) va mukofot."""
import pytest

from backend.minar import achievements, playground as P
from backend.minar.models import MinarLedger, MinarPlaygroundSolve
from backend.tests.test_minar import _minar_env, acct, post  # noqa: F401

SOLUTIONS = {
    "html-1": {"html": "<h1>Salom, Minar!</h1>"},
    "html-2": {"html": "<h1>Ali</h1><p>Men 12 yoshman va dasturchi bo‘lmoqchiman.</p>"},
    "html-3": {"html": '<img src="robo.png" alt="Robot">'},
    "html-4": {"html": '<a href="https://minaracademy.uz">Minar</a>'},
    "html-5": {"html": "<ul><li>a</li><li>b</li><li>c</li></ul>"},
    "html-6": {"html": "<ol>\n<li>1</li>\n<li>2</li>\n<li>3</li>\n</ol>"},
    "html-7": {"html": '<form><label for="i">Ism</label><input id="i"><button>Yuborish</button></form>'},
    "html-8": {"html": "<table><tr><th>Kun</th></tr><tr><td>Dushanba</td></tr></table>"},
    "css-1": {"css": ".title { color: teal; }"},
    "css-2": {"css": "body{background:#fff}"},
    "css-3": {"css": "/* karta */ .card { padding: 16px; border-radius: 12px }"},
    "css-4": {"css": "h1, .title { text-align: center; }"},
    "css-5": {"css": ".row { display: flex; gap: 1rem; }"},
    "css-6": {"css": "button:hover { background-color: red; }"},
    "css-7": {"css": "p { font-size: 18px; font-weight: 700; }"},
    "css-8": {"css": ".row{display:flex}\n@media (max-width: 600px) {\n  .row { flex-direction: column; }\n}"},
    "js-1": {"js": 'console.log("Salom, Minar!");', "output": ["Salom, Minar!"]},
    "js-2": {"js": "let coins = 10;\ncoins += 5;\nconsole.log(coins);", "output": ["15"]},
    "js-3": {"js": 'const age = 12;\nif (age >= 10) { console.log("Katta"); } else { console.log("Kichik"); }',
             "output": ["Katta"]},
    "js-4": {"js": "for (let i = 1; i <= 5; i++) console.log(i);", "output": ["1", "2", "3", "4", "5"]},
    "js-5": {"js": "const add = (a, b) => { return a + b };\nconsole.log(add(2, 3));", "output": ["5"]},
    "js-6": {"js": 'const f = ["a", "b", "c"];\nconsole.log(f.length);', "output": ["3"]},
    "js-7": {"js": 'const courses = ["HTML", "CSS", "JS"];\ncourses.forEach(c => console.log(c));',
             "output": ["HTML", "CSS", "JS"]},
    "js-8": {"js": 'const hero = { name: "Robo", level: 3 };\nconsole.log(hero.name);', "output": ["Robo"]},
}


def test_every_task_has_a_solution():
    assert set(SOLUTIONS) == set(P.BY_ID)


@pytest.mark.parametrize("task_id", sorted(SOLUTIONS))
def test_reference_solution_passes_and_starter_fails(task_id):
    task = P.BY_ID[task_id]
    sol = {**task.starter, **SOLUTIONS[task_id]}
    assert all(r["ok"] for r in P.evaluate(task, sol)), P.evaluate(task, sol)
    assert not all(r["ok"] for r in P.evaluate(task, task.starter))


@pytest.mark.parametrize("task_id,payload", [
    ("html-1", {"html": "<h2>Salom</h2>"}),
    ("html-3", {"html": '<img src="" alt="x">'}),
    ("html-5", {"html": "<ul><li>a</li><li>b</li></ul><ol><li>c</li></ol>"}),
    ("css-4", {"css": ".title { text-align: left }"}),
    ("css-8", {"css": ".row { flex-direction: column }"}),                       # @media'siz
    ("js-1", {"js": "// console.log('Salom, Minar!')", "output": ["Salom, Minar!"]}),   # izohdagi kod hisoblanmaydi
    ("js-2", {"js": "let coins = 10; coins += 5; console.log(coins)", "output": ["16"]}),
    ("js-8", {"js": 'const hero = { name: "Robo" }; console.log(hero.name)', "output": ["Robo"]}),
])
def test_wrong_solutions_fail(task_id, payload):
    assert not all(r["ok"] for r in P.evaluate(P.BY_ID[task_id], payload))


def test_parsers_tolerate_broken_code():
    assert P.parse_css("a { color: red  .b { } }} @media {") is not None
    root = P.parse_html("<div><p>yopilmagan <b>teg</div></span><img src=x>")
    assert [n.tag for n in root.walk()] == ["div", "p", "b", "img"]
    assert not all(r["ok"] for r in P.evaluate(P.BY_ID["css-1"], {"css": "}}}{{{"}))


def test_check_endpoint_rewards_once_and_unlocks(client, db, acct):
    r = post(client, "/playground/html-1/check", {"html": "<h1>Xayr</h1>"}).json()
    assert r["solved"] is False and [c["ok"] for c in r["checks"]] == [True, False] and "state" not in r
    r = post(client, "/playground/html-1/check", {"html": "<h1>Salom!</h1>"}).json()
    first = achievements.BY_CODE["code_1"].reward
    assert r["solved"] and r["award"] == P.REWARD and [a["id"] for a in r["unlocked"]] == ["code_1"]
    assert r["state"]["balance"] == P.REWARD + first and r["state"]["xp"] == P.XP
    again = post(client, "/playground/html-1/check", {"html": "<h1>Salom, yana</h1>"}).json()
    assert again["solved"] and again["award"] == 0 and again["state"]["xp"] == P.XP
    assert db.query(MinarPlaygroundSolve).one().code == '{"html": "<h1>Salom, yana</h1>"}'
    assert db.query(MinarLedger).filter(MinarLedger.ref_key == "playground:html-1").count() == 1
    data = client.get("/space/playground").json()
    t = next(t for t in data["tasks"] if t["id"] == "html-1")
    assert data["solved"] == 1 and data["total"] == len(P.TASKS) and t["solved"] and t["code"]["html"]
    assert "fn" not in str(t) and t["checks"] == ["h1 sarlavha bor", "Sarlavhada “Salom” so‘zi bor"]


def test_playground_solve_counts_for_daily_lesson_quest(client, acct):
    post(client, "/playground/css-4/check", {"css": ".title{text-align:center}"})
    assert post(client, "/quests/claim", {"type": "quest", "quest": "lesson"}).status_code == 200


@pytest.mark.parametrize("task_id,payload,code", [
    ("nope", {"html": ""}, 404),
    ("html-1", {"html": "x" * (P.CODE_MAX + 1)}, 400),
    ("js-1", {"js": "", "output": ["x"] * 101}, 400),
    ("js-1", {"js": "", "output": "Salom"}, 400),
    ("html-1", {"html": 5}, 400),
])
def test_check_validation(client, acct, task_id, payload, code):
    assert post(client, f"/playground/{task_id}/check", payload).status_code == code
