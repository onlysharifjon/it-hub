"""Minar Space API testlari: akkaunt, sessiya, coin qoidalari, xarid, o'yin tekshiruvi, reyting, battle."""
import time
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import models, tz
from backend.main import app
from backend.minar import auth as minar_auth
from backend.minar import battles, catalog as C, service
from backend.minar.models import MinarAccount, MinarBattle
from backend.tests.conftest import TestSessionLocal


@pytest.fixture(autouse=True)
def _minar_env(monkeypatch):
    monkeypatch.setattr(minar_auth, "COOKIE_SECURE", False)          # TestClient http://
    monkeypatch.setattr(battles, "SessionLocal", TestSessionLocal)   # WS uchun test bazasi
    battles.ROOMS.clear()


@pytest.fixture
def ws_client(monkeypatch):
    """Ikkala o'yinchining WS ulanishi bitta event loop'da (real serverdagidek).
    CRM startup hook'lari (asosiy bazaga yozadi) bu yerda kerak emas."""
    monkeypatch.setattr(app.router, "on_startup", [])
    monkeypatch.setattr(app.router, "on_shutdown", [])
    with TestClient(app) as tc:
        yield tc


def H(token):
    return {"Authorization": f"Bearer {token}"}


def make_student(db, name="Azizbek Komilov", group=None, stage="foundation"):
    st = models.Student(full_name=name, phone1="+998901234567", is_active=True)
    db.add(st)
    db.flush()
    if group is None:
        group = models.Group(name="S-100", stage=stage, is_active=True)
        db.add(group)
        db.flush()
    db.add(models.GroupStudent(group_id=group.id, student_id=st.id))
    db.commit()
    return st, group


def new_account(client, db, metodist_token, name="Azizbek Komilov", **kw):
    st, group = make_student(db, name, **kw)
    r = client.post("/minar-admin/accounts", json={"student_id": st.id}, headers=H(metodist_token))
    assert r.status_code == 201, r.text
    return st, r.json()


def login(client, creds):
    r = client.post("/minar/auth/login", json={"studentId": creds["login_id"], "password": creds["password"]})
    assert r.status_code == 200, r.text
    return r


@pytest.fixture
def acct(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    login(client, creds)
    return st, creds


def post(client, path, body=None, key=None):
    return client.post("/minar" + path, json=body or {}, headers={"Idempotency-Key": key} if key else {})


def give_coins(db, student, amount, teacher_id, reason="Faol qatnashdi", when=None):
    db.add(models.CoinTransaction(student_id=student.id, teacher_id=teacher_id, amount=amount, reason=reason,
                                  created_at=when or datetime.utcnow()))
    db.commit()


# ── Akkaunt va sessiya ──────────────────────────────────────────────────────

def test_admin_creates_account_and_default_course(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    assert creds["login_id"] == f"MA{st.id:04d}" and len(creds["password"]) == 8
    assert creds["course"] == "HTML"                      # foundation -> HTML
    st2, c2 = new_account(client, db, metodist_token, "Ali Valiyev", stage="fullstack")
    assert c2["course"] == "JavaScript"
    dup = client.post("/minar-admin/accounts", json={"student_id": st.id}, headers=H(metodist_token))
    assert dup.status_code == 409


def test_admin_requires_staff_role_and_token(client, db, metodist_token, teacher_token):
    st, _ = make_student(db)
    assert client.post("/minar-admin/accounts", json={"student_id": st.id}).status_code == 401
    assert client.post("/minar-admin/accounts", json={"student_id": st.id},
                       headers=H(teacher_token)).status_code == 403


def test_login_and_bootstrap_shape(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    assert client.get("/minar/students/me/bootstrap").status_code == 401
    r = login(client, creds)
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    s = client.get("/minar/students/me/bootstrap").json()
    assert s["version"] == 1
    assert s["profile"] == {"id": creds["login_id"], "name": "Azizbek", "surname": "Komilov", "course": "HTML",
                            "group": "S-100", "character": "robo"}
    assert (s["balance"], s["earned"], s["xp"], s["streak"]) == (0, 0, 0, 0)
    assert s["equipment"] == {"hat": None, "accessory": None, "outfit": None, "background": None}
    for k in ("history", "attendance", "purchases", "results", "completedLessons", "claimedQuests", "checkins", "owned"):
        assert s[k] == []


def test_login_errors_use_message_format_and_lockout(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    r = client.post("/minar/auth/login", json={"studentId": creds["login_id"], "password": "wrong-pass"})
    assert r.status_code == 401 and r.json() == {"message": "ID yoki parol noto‘g‘ri."}
    r = client.post("/minar/auth/login", json={"studentId": "MA9999", "password": "whatever1"})
    assert r.status_code == 401 and r.json()["message"] == "ID yoki parol noto‘g‘ri."   # ID mavjudligi sezilmaydi
    from backend import security
    for _ in range(minar_auth.LOCK_AFTER):
        security._hits.clear()
        client.post("/minar/auth/login", json={"studentId": creds["login_id"], "password": "bad-password"})
    security._hits.clear()
    r = client.post("/minar/auth/login", json={"studentId": creds["login_id"], "password": creds["password"]})
    assert r.status_code == 429                               # to'g'ri parol bilan ham bloklangan


def test_login_rate_limit(client, db, metodist_token):
    for _ in range(6):
        client.post("/minar/auth/login", json={"studentId": "MA0001", "password": "x" * 8})
    r = client.post("/minar/auth/login", json={"studentId": "MA0001", "password": "x" * 8})
    assert r.status_code == 429 and "message" in r.json()


def test_login_is_case_insensitive_and_logout_revokes(client, db, metodist_token):
    st, creds = new_account(client, db, metodist_token)
    r = client.post("/minar/auth/login", json={"studentId": creds["login_id"].lower(), "password": creds["password"]})
    assert r.status_code == 200
    assert client.get("/minar/students/me/bootstrap").status_code == 200
    assert client.post("/minar/auth/logout").status_code == 200
    assert client.get("/minar/students/me/bootstrap").status_code == 401


def test_csrf_foreign_origin_rejected(client, acct):
    r = client.post("/minar/rewards/check-in", json={}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/minar/rewards/check-in", json={}, headers={"Origin": "https://space.minaracademy.uz"})
    assert r.status_code == 200


def test_reset_password_revokes_sessions_and_disable(client, db, metodist_token, acct):
    st, creds = acct
    r = client.post(f"/minar-admin/accounts/{st.id}/reset-password", headers=H(metodist_token))
    assert r.status_code == 200 and r.json()["password"] != creds["password"]
    assert client.get("/minar/students/me/bootstrap").status_code == 401          # eski sessiya tugadi
    new = r.json()
    assert client.post("/minar/auth/login", json={"studentId": new["login_id"], "password": new["password"]}).status_code == 200
    client.patch(f"/minar-admin/accounts/{st.id}", json={"is_active": False}, headers=H(metodist_token))
    assert client.get("/minar/students/me/bootstrap").status_code == 401
    assert client.post("/minar/auth/login", json={"studentId": new["login_id"], "password": new["password"]}).status_code == 403


def test_bulk_create_for_group(client, db, metodist_token):
    st1, group = make_student(db, "Bir Ikki")
    st2, _ = make_student(db, "Uch To‘rt", group=group)
    r = client.post("/minar-admin/accounts/bulk", json={"group_id": group.id}, headers=H(metodist_token))
    assert r.status_code == 201 and r.json()["count"] == 2
    again = client.post("/minar-admin/accounts/bulk", json={"group_id": group.id}, headers=H(metodist_token))
    assert again.json()["count"] == 0                                              # takror yaratilmaydi
    listing = client.get("/minar-admin/accounts", headers=H(metodist_token)).json()
    assert len(listing) == 2 and all("password" not in a for a in listing)


# ── Check-in, dars, missiya ─────────────────────────────────────────────────

def test_checkin_once_per_day_and_streak(client, db, acct):
    r = post(client, "/rewards/check-in").json()
    assert r["award"] == 1 and r["state"]["balance"] == 1 and r["state"]["streak"] == 1
    assert r["state"]["checkins"] == [tz.today().isoformat()]
    again = post(client, "/rewards/check-in").json()
    assert again["award"] == 0 and again["message"] == "" and again["state"]["balance"] == 1
    # kecha kirgan bo'lsa ketma-ketlik davom etadi
    acc = db.query(MinarAccount).one()
    acc.last_login, acc.streak = (tz.today() - timedelta(days=1)).isoformat(), 3
    db.query(service.MinarLedger).delete()
    db.commit()
    assert post(client, "/rewards/check-in").json()["state"]["streak"] == 4
    # 2+ kun uzilish — 1 dan boshlanadi
    acc = db.query(MinarAccount).one()
    db.refresh(acc)
    acc.last_login, acc.streak = (tz.today() - timedelta(days=5)).isoformat(), 9
    db.query(service.MinarLedger).delete()
    db.commit()
    assert post(client, "/rewards/check-in").json()["state"]["streak"] == 1


def test_lesson_and_quest_flow(client, acct):
    r = post(client, "/courses/complete", {"type": "lesson", "index": 0}).json()
    assert r["award"] == 5 and r["state"]["xp"] == 50 and r["state"]["completedLessons"] == ["HTML-0"]
    again = post(client, "/courses/complete", {"type": "lesson", "index": 0}).json()
    assert again["award"] == 0 and again["state"]["balance"] == 5 and again["message"] == "Bu dars avval yakunlangan."
    for bad in (3, -1, "0", None, True):
        assert post(client, "/courses/complete", {"type": "lesson", "index": bad}).status_code == 400
    assert post(client, "/quests/claim", {"type": "quest", "quest": "typing"}).status_code == 400   # shart bajarilmagan
    q = post(client, "/quests/claim", {"type": "quest", "quest": "lesson"}).json()
    assert q["award"] == 5 and q["state"]["claimedQuests"] == [f"{tz.today().isoformat()}:lesson"]
    assert post(client, "/quests/claim", {"type": "quest", "quest": "lesson"}).status_code == 409
    assert post(client, "/quests/claim", {"type": "quest", "quest": "hack"}).status_code == 400


# ── O'yin natijalari ────────────────────────────────────────────────────────

def typing_result(**kw):
    r = {"id": str(uuid.uuid4()), "game": "typing", "correct": 60, "accuracy": 95, "wpm": 12, "duration": 60, "score": 60}
    r.update(kw)
    return r


def test_game_reward_xp_and_idempotency(client, acct):
    res = typing_result()
    r = post(client, "/games/results", {"type": "game", "result": res}, key=res["id"]).json()
    assert r["award"] == 10 and r["state"]["balance"] == 10 and r["state"]["xp"] == 50
    assert r["state"]["results"][0]["id"] == res["id"] and r["state"]["results"][0]["award"] == 10
    dup = post(client, "/games/results", {"type": "game", "result": res}, key=res["id"]).json()
    assert dup["state"]["balance"] == 10 and dup["state"]["xp"] == 50           # ikkinchi marta coin yo'q
    weak = typing_result(correct=10, wpm=2)
    r = post(client, "/games/results", {"type": "game", "result": weak}).json()
    assert r["award"] == 0 and r["state"]["xp"] == 60                            # urinish +10 XP


def test_daily_cap_three_rewards_per_game(client, acct):
    awards = [post(client, "/games/results", {"type": "game", "result": typing_result()}).json()["award"]
              for _ in range(5)]
    assert awards == [10, 10, 10, 0, 0]
    quiz = {"id": str(uuid.uuid4()), "game": "quiz", "score": 4, "total": 5}
    assert post(client, "/games/results", {"type": "game", "result": quiz}).json()["award"] == 10   # boshqa o'yin — alohida chegara


@pytest.mark.parametrize("result", [
    {"game": "typing", "correct": 9999, "accuracy": 99, "wpm": 200, "duration": 30, "score": 9999},   # imkonsiz tezlik
    {"game": "typing", "correct": 100, "accuracy": 100, "wpm": 400, "duration": 60, "score": 100},    # wpm mos emas
    {"game": "typing", "correct": 60, "accuracy": 140, "wpm": 12, "duration": 60, "score": 60},
    {"game": "ztype", "score": 100, "duration": 10},
    {"game": "quiz", "score": 9, "total": 5},
    {"game": "quiz", "score": -1, "total": 5},
    {"game": "memory", "score": 6, "moves": 2},
    {"game": "bug", "score": 3, "total": 99},
    {"game": "nonsense", "score": 1},
    {"game": "typing", "correct": "60", "accuracy": 95, "wpm": 12, "duration": 60},
])
def test_implausible_results_rejected(client, acct, result):
    r = post(client, "/games/results", {"type": "game", "result": {"id": str(uuid.uuid4()), **result}})
    assert r.status_code == 400 and "message" in r.json()
    assert client.get("/minar/students/me/bootstrap").json()["balance"] == 0


def test_all_game_rules(client, acct):
    cases = [
        ({"game": "ztype", "score": 5, "duration": 60}, 15),
        ({"game": "ztype", "score": 4, "duration": 60}, 0),
        ({"game": "quiz", "score": 3, "total": 5}, 10),
        ({"game": "quiz", "score": 2, "total": 5}, 0),
        ({"game": "memory", "score": 6, "moves": 14}, 8),
        ({"game": "memory", "score": 5, "moves": 14}, 0),
        ({"game": "bug", "score": 2, "total": 3}, 10),
        ({"game": "bug", "score": 1, "total": 3}, 0),
    ]
    for res, want in cases:
        r = post(client, "/games/results", {"type": "game", "result": {"id": str(uuid.uuid4()), **res}})
        assert r.status_code == 200 and r.json()["award"] == want, (res, r.text)


def test_battle_reward_needs_server_confirmed_win(client, db, acct):
    st, creds = acct
    claim = {"id": "match-forged-1", "game": "battle", "mode": "typing", "won": True, "draw": False,
             "score": 99, "matchId": "match-forged-1", "practice": False}
    assert post(client, "/games/results", {"type": "game", "result": claim}).json()["award"] == 0     # server bilmaydi
    practice = {**claim, "id": "match-practice-1", "matchId": "match-practice-1", "practice": True}
    assert post(client, "/games/results", {"type": "game", "result": practice}).json()["award"] == 0
    acc = db.query(MinarAccount).one()
    db.add(MinarBattle(code="ABC234", room_id=str(uuid.uuid4()), mode="typing", course="HTML",
                       host_account_id=acc.id, status="finished", match_id="match-real-0001",
                       winner_account_id=acc.id, created_at=datetime.utcnow()))
    db.commit()
    real = {**claim, "id": "match-real-0001", "matchId": "match-real-0001"}
    assert post(client, "/games/results", {"type": "game", "result": real}).json()["award"] == 15
    # boshqa akkaunt g'olib bo'lgan bellashuvga da'vo qilib bo'lmaydi
    other = models.Student(full_name="Boshqa Bola", phone1="+998900000000", is_active=True)
    db.add(other)
    db.flush()
    oa = MinarAccount(student_id=other.id, login_id="MA7777", password_hash="x", course="HTML")
    db.add(oa)
    db.flush()
    db.add(MinarBattle(code="XYZ234", room_id=str(uuid.uuid4()), mode="typing", course="HTML", host_account_id=oa.id,
                       status="finished", match_id="match-real-0002", winner_account_id=oa.id,
                       created_at=datetime.utcnow()))
    db.commit()
    steal = {**claim, "id": "match-real-0002", "matchId": "match-real-0002"}
    assert post(client, "/games/results", {"type": "game", "result": steal}).json()["award"] == 0


# ── Xarid, kiyim, qahramon ──────────────────────────────────────────────────

def test_purchase_rules_server_price_and_idempotency(client, db, acct, metodist_user):
    st, _ = acct
    req = str(uuid.uuid4())
    r = post(client, "/shop/purchases", {"type": "purchase", "productId": "cap", "requestId": req}, key=req)
    assert r.status_code == 400 and "yetmaydi" in r.json()["message"]                  # coin yo'q
    give_coins(db, st, 100, metodist_user.id)                                          # o'qituvchi coini
    assert client.get("/minar/students/me/bootstrap").json()["balance"] == 100
    r = post(client, "/shop/purchases", {"type": "purchase", "productId": "cap", "requestId": req, "price": 1}, key=req)
    s = r.json()["state"]
    assert r.status_code == 200 and s["balance"] == 35 and s["owned"] == ["cap"]        # narx serverdan (65)
    assert s["purchases"][0]["status"] == "delivered" and s["purchases"][0]["price"] == 65
    assert s["earned"] == 100                                                          # sarf earned ni kamaytirmaydi
    assert s["history"][0]["kind"] == "purchase" and s["history"][0]["amount"] == -65
    replay = post(client, "/shop/purchases", {"type": "purchase", "productId": "cap", "requestId": req}, key=req).json()
    assert replay["state"]["balance"] == 35 and len(replay["state"]["purchases"]) == 1  # ikki marta yechilmadi
    again = post(client, "/shop/purchases", {"type": "purchase", "productId": "cap", "requestId": str(uuid.uuid4())})
    assert again.status_code == 409                                                     # Hero buyumi bir marta
    assert post(client, "/shop/purchases", {"productId": "nope", "requestId": str(uuid.uuid4())}).status_code == 404
    assert post(client, "/shop/purchases", {"productId": "crown"}).status_code == 400   # requestId yo'q


def test_equip_toggle_and_ownership(client, db, acct, metodist_user):
    st, _ = acct
    give_coins(db, st, 500, metodist_user.id)
    assert post(client, "/avatar/equipment", {"type": "equip", "productId": "cap"}).status_code == 400    # olinmagan
    for pid in ("cap", "crown"):
        post(client, "/shop/purchases", {"productId": pid, "requestId": str(uuid.uuid4())})
    eq = post(client, "/avatar/equipment", {"type": "equip", "productId": "cap"}).json()["state"]["equipment"]
    assert eq["hat"] == "cap"
    eq = post(client, "/avatar/equipment", {"type": "equip", "productId": "crown"}).json()["state"]["equipment"]
    assert eq["hat"] == "crown"                                                          # almashtiradi
    eq = post(client, "/avatar/equipment", {"type": "equip", "productId": "crown"}).json()["state"]["equipment"]
    assert eq["hat"] is None                                                             # yechadi
    assert post(client, "/avatar/equipment", {"type": "equip", "productId": "mouse"}).status_code == 400  # sovg'a kiyilmaydi


def test_character_change_keeps_everything(client, db, acct, metodist_user):
    st, _ = acct
    give_coins(db, st, 100, metodist_user.id)
    post(client, "/shop/purchases", {"productId": "cap", "requestId": str(uuid.uuid4())})
    before = client.get("/minar/students/me/bootstrap").json()
    after = post(client, "/avatar/character", {"type": "character", "character": "drako"}).json()["state"]
    assert after["profile"]["character"] == "drako"
    assert (after["balance"], after["owned"], after["purchases"]) == (before["balance"], before["owned"], before["purchases"])
    assert post(client, "/avatar/character", {"character": "godzilla"}).status_code == 400


def test_shop_gift_order_lifecycle(client, db, metodist_token, acct, metodist_user):
    st, _ = acct
    give_coins(db, st, 300, metodist_user.id)
    for _ in range(2):                                                                   # sovg'a ko'p marta olinadi
        r = post(client, "/shop/purchases", {"productId": "stickers", "requestId": str(uuid.uuid4())})
        assert r.status_code == 200
    s = r.json()["state"]
    assert s["balance"] == 140 and s["owned"] == [] and [p["status"] for p in s["purchases"]] == ["pending", "pending"]
    orders = client.get("/minar-admin/orders", headers=H(metodist_token)).json()
    assert len(orders) == 2 and orders[0]["student_name"] == "Azizbek Komilov"
    oid = orders[0]["id"]
    assert client.patch(f"/minar-admin/orders/{oid}", json={"status": "ready"}, headers=H(metodist_token)).status_code == 200
    assert client.patch(f"/minar-admin/orders/{oid}", json={"status": "bogus"}, headers=H(metodist_token)).status_code == 400
    statuses = {p["id"]: p["status"] for p in client.get("/minar/students/me/bootstrap").json()["purchases"]}
    assert statuses[oid] == "ready"


# ── CRM ma'lumotlari: coin tarixi va davomat ────────────────────────────────

def test_teacher_coins_and_attendance_flow_into_state(client, db, acct, metodist_user):
    st, _ = acct
    group = db.query(models.Group).one()
    lesson_day = tz.today() - timedelta(days=2)
    give_coins(db, st, 10, metodist_user.id, "Darsda faol", when=tz.to_utc(datetime.combine(lesson_day, datetime.min.time()) + timedelta(hours=15)))
    give_coins(db, st, -3, metodist_user.id, "Tuzatish")
    db.add(models.Attendance(group_id=group.id, student_id=st.id, lesson_date=lesson_day, is_present=True))
    db.add(models.Attendance(group_id=group.id, student_id=st.id, lesson_date=tz.today() - timedelta(days=4), is_present=False))
    db.add(models.Attendance(group_id=group.id, student_id=st.id, lesson_date=tz.today() - timedelta(days=6), is_present=None))
    db.add(models.CameraAttendance(student_id=st.id, person_type="student", event_type="keldi",
                                   detected_at=tz.to_utc(datetime.combine(lesson_day, datetime.min.time()) + timedelta(hours=14, minutes=2))))
    db.commit()
    s = client.get("/minar/students/me/bootstrap").json()
    assert (s["balance"], s["earned"]) == (7, 10)
    titles = {h["title"]: h for h in s["history"]}
    assert titles["Darsda faol"]["kind"] == "reward" and titles["Tuzatish"]["amount"] == -3
    att = {a["date"]: a for a in s["attendance"]}
    assert att[lesson_day.isoformat()] == {"date": lesson_day.isoformat(), "status": "present", "time": "14:02", "coins": 10}
    absent = att[(tz.today() - timedelta(days=4)).isoformat()]
    assert absent["status"] == "absent" and absent["time"] is None and absent["coins"] == 0
    assert (tz.today() - timedelta(days=6)).isoformat() not in att                       # belgilanmagan dars ko'rsatilmaydi


# ── Reyting ─────────────────────────────────────────────────────────────────

def test_leaderboard_masks_names_filters_and_includes_self(client, db, metodist_token, metodist_user):
    _, c1 = new_account(client, db, metodist_token, "Azizbek Komilov")
    st2, c2 = new_account(client, db, metodist_token, "Malika Karimova", stage="fullstack")     # JavaScript
    give_coins(db, st2, 80, metodist_user.id)
    login(client, c1)
    post(client, "/rewards/check-in")
    rows = client.get("/minar/leaderboard?metric=coins&period=all&course=all").json()
    assert isinstance(rows, list) and [r["name"] for r in rows] == ["Malika K.", "Azizbek K."]
    assert rows[0] == {"id": c2["login_id"], "name": "Malika K.", "avatar": "🤖", "coins": 80, "week": 80, "xp": 0,
                       "active": 0, "course": "JavaScript"}
    js = client.get("/minar/leaderboard?course=JavaScript").json()
    assert [r["id"] for r in js] == [c2["login_id"]]
    assert client.get("/minar/leaderboard?metric=hack").status_code == 400
    assert client.get("/minar/leaderboard?course=Python").status_code == 400


# ── AI yordamchi ────────────────────────────────────────────────────────────

def test_assistant_offline_fallback_privacy_and_rate_limit(client, acct, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    msgs = [{"role": "assistant", "content": "Salom!"}, {"role": "user", "content": "Flexbox nima?"}]
    r = post(client, "/assistant/messages", {"messages": msgs, "course": "CSS"})
    assert r.status_code == 200 and "Flexbox" in r.json()["message"]
    r = post(client, "/assistant/messages", {"messages": [{"role": "user", "content": "parolim 1234"}]})
    assert "shaxsiy" in r.json()["message"]
    assert post(client, "/assistant/messages", {"messages": []}).status_code == 400
    assert post(client, "/assistant/messages", {"messages": [{"role": "assistant", "content": "x"}]}).status_code == 400
    for _ in range(25):
        last = post(client, "/assistant/messages", {"messages": msgs})
    assert last.status_code == 429


def test_assistant_uses_model_when_key_set(client, acct, monkeypatch):
    from backend.minar import assistant
    seen = {}

    def fake(messages, course):
        seen["messages"], seen["course"] = messages, course
        return "Model javobi"
    monkeypatch.setattr(assistant, "_ask_model", fake)
    r = post(client, "/assistant/messages", {"messages": [{"role": "user", "content": "let nima?"}]})
    assert r.json() == {"message": "Model javobi"} and seen["course"] == "HTML"


# ── Battle: REST ────────────────────────────────────────────────────────────

def test_battle_rest_create_join_rules(client, db, metodist_token):
    _, host = new_account(client, db, metodist_token, "Host Bola")
    _, guest = new_account(client, db, metodist_token, "Guest Bola")
    _, third = new_account(client, db, metodist_token, "Third Bola")
    login(client, host)
    room = post(client, "/battles", {"mode": "typing"}).json()
    assert set(room) == {"code", "roomId", "ticket", "wsUrl"} and len(room["code"]) == 6
    assert post(client, "/battles", {"mode": "chess"}).status_code == 400
    assert post(client, f"/battles/{room['code']}/join").status_code == 400            # o'z xonasi
    login(client, guest)
    joined = post(client, f"/battles/{room['code'].lower()}/join")
    assert joined.status_code == 200 and joined.json()["roomId"] == room["roomId"]
    login(client, third)
    assert post(client, f"/battles/{room['code']}/join").status_code == 409             # xona to'lgan
    assert post(client, "/battles/NOPE22/join").status_code == 404


# ── Battle: WebSocket ───────────────────────────────────────────────────────

def _ws_pair(client, db, metodist_token, mode):
    _, host = new_account(client, db, metodist_token, "Host Bola")
    _, guest = new_account(client, db, metodist_token, "Guest Bola")
    hc, gc = TestClient(app), TestClient(app)
    login(hc, host)
    login(gc, guest)
    room = post(hc, "/battles", {"mode": mode}).json()
    joined = post(gc, f"/battles/{room['code']}/join").json()
    return hc, gc, host, guest, room, joined


def _recv_until(ws, kind, limit=8):
    for _ in range(limit):
        m = ws.receive_json()
        if m["type"] == kind:
            return m
    raise AssertionError(f"{kind} kelmadi")


def test_ws_typing_battle_full_flow_and_reward(client, ws_client, db, metodist_token, monkeypatch):
    hc, gc, host, guest, room, joined = _ws_pair(client, db, metodist_token, "typing")
    with ws_client.websocket_connect("/minar/battles") as hws, ws_client.websocket_connect("/minar/battles") as gws:
        hws.send_json({"type": "join", "ticket": room["ticket"], "roomId": room["roomId"], "sender": "tab-host", "name": "X"})
        gws.send_json({"type": "join", "ticket": joined["ticket"], "roomId": joined["roomId"], "sender": "tab-guest", "name": "Y"})
        welcome = _recv_until(gws, "welcome")
        assert welcome["sender"] == "tab-host" and welcome["target"] == "tab-guest" and welcome["name"] == "Host"
        assert welcome["mode"] == "typing" and welcome["course"] == "HTML"
        assert _recv_until(hws, "join")["sender"] == "tab-guest"
        gws.send_json({"type": "start"})                                                 # mehmon boshlay olmaydi
        hws.send_json({"type": "start", "at": 1, "matchId": "forged"})
        start = _recv_until(hws, "start")
        assert _recv_until(gws, "start")["matchId"] == start["matchId"] != "forged"
        assert start["sender"] == "server" and start["at"] > 1_700_000_000_000
        battles.ROOMS[room["roomId"]].start_ms -= 10_000                                 # vaqtni oldinga suramiz
        # Mehmon chala yozadi, xost hammasini yozadi
        gws.send_json({"type": "progress", "matchId": start["matchId"], "typed": C.BATTLE_TEXT[:20], "score": 999, "done": True})
        prog = _recv_until(hws, "progress")
        assert prog["score"] == 20 and prog["done"] is False and prog["sender"] == "tab-guest"   # client `score`/`done` inobatga olinmadi
        hws.send_json({"type": "progress", "matchId": start["matchId"], "typed": C.BATTLE_TEXT, "score": 1, "done": False})
        res_h, res_g = _recv_until(hws, "result"), _recv_until(gws, "result")
        assert res_h == res_g and res_h["winnerId"] == host["login_id"] and res_h["draw"] is False
        match_id = start["matchId"]

    b = db.query(MinarBattle).filter(MinarBattle.match_id == match_id).one()
    db.refresh(b)
    assert b.status == "finished" and b.winner_account_id is not None
    win = {"id": match_id, "game": "battle", "mode": "typing", "won": True, "draw": False, "score": 130,
           "matchId": match_id, "practice": False}
    lose = {**win, "won": False}
    assert post(hc, "/games/results", {"type": "game", "result": win}, key=match_id).json()["award"] == 15
    assert post(gc, "/games/results", {"type": "game", "result": {**win, "won": True}}, key=match_id).json()["award"] == 0  # yutqazgan da'vo qila olmaydi
    assert post(gc, "/games/results", {"type": "game", "result": {**lose, "id": "another-id-0001"}}).json()["award"] == 0


def test_ws_typing_speed_limit_blocks_instant_paste(client, ws_client, db, metodist_token):
    hc, gc, host, guest, room, joined = _ws_pair(client, db, metodist_token, "typing")
    with ws_client.websocket_connect("/minar/battles") as hws, ws_client.websocket_connect("/minar/battles") as gws:
        hws.send_json({"type": "join", "ticket": room["ticket"], "roomId": room["roomId"], "sender": "h", "name": "X"})
        gws.send_json({"type": "join", "ticket": joined["ticket"], "roomId": joined["roomId"], "sender": "g", "name": "Y"})
        _recv_until(hws, "join")
        hws.send_json({"type": "start"})
        start = _recv_until(hws, "start")
        hws.send_json({"type": "progress", "matchId": start["matchId"], "typed": C.BATTLE_TEXT})   # 0 soniyada butun matn
        gws.send_json({"type": "progress", "matchId": start["matchId"], "typed": "hel"})
        p = _recv_until(hws, "progress")
        assert p["sender"] == "g"                                    # faqat mehmonning xabari o'tdi
        assert battles.ROOMS[room["roomId"]].state == "playing"


def test_ws_quiz_battle_scoring_and_draw(client, ws_client, db, metodist_token):
    hc, gc, host, guest, room, joined = _ws_pair(client, db, metodist_token, "quiz")
    with ws_client.websocket_connect("/minar/battles") as hws, ws_client.websocket_connect("/minar/battles") as gws:
        hws.send_json({"type": "join", "ticket": room["ticket"], "roomId": room["roomId"], "sender": "h", "name": "X"})
        gws.send_json({"type": "join", "ticket": joined["ticket"], "roomId": joined["roomId"], "sender": "g", "name": "Y"})
        _recv_until(hws, "join")
        hws.send_json({"type": "start"})
        start = _recv_until(hws, "start")
        battles.ROOMS[room["roomId"]].start_ms -= 5000
        answers = C.QUIZ_ANSWERS["HTML"]
        for qi in range(5):
            time.sleep(0.35)                                         # server: javoblar orasida >= 300 ms
            hws.send_json({"type": "progress", "matchId": start["matchId"], "questionIndex": qi, "answerIndex": answers[qi]})
            wrong = (answers[qi] + 1) % 4 if qi < 2 else answers[qi]  # mehmon 2 ta xato qiladi
            gws.send_json({"type": "progress", "matchId": start["matchId"], "questionIndex": qi, "answerIndex": wrong})
        result = _recv_until(hws, "result")
        assert result["scores"] == {"host": 5, "guest": 3} and result["winnerId"] == host["login_id"]


def test_ws_rejects_bad_ticket_and_leave_notifies(client, ws_client, db, metodist_token):
    hc, gc, host, guest, room, joined = _ws_pair(client, db, metodist_token, "typing")
    with pytest.raises(Exception):
        with ws_client.websocket_connect("/minar/battles") as bad:
            bad.send_json({"type": "join", "ticket": "garbage", "roomId": room["roomId"], "sender": "h", "name": "X"})
            bad.receive_json()
    with pytest.raises(Exception):                                   # mehmon chiptasi xost roli bilan ishlamaydi
        with ws_client.websocket_connect("/minar/battles") as bad:
            bad.send_json({"type": "join", "ticket": joined["ticket"], "roomId": "other-room", "sender": "g", "name": "Y"})
            bad.receive_json()
    with ws_client.websocket_connect("/minar/battles") as hws:
        hws.send_json({"type": "join", "ticket": room["ticket"], "roomId": room["roomId"], "sender": "h", "name": "X"})
        with ws_client.websocket_connect("/minar/battles") as gws:
            gws.send_json({"type": "join", "ticket": joined["ticket"], "roomId": joined["roomId"], "sender": "g", "name": "Y"})
            _recv_until(hws, "join")
        assert _recv_until(hws, "leave")["sender"] == "g"            # mehmon chiqdi — xost xabar oldi
    for _ in range(40):                                              # DB yangilanishi xabardan keyin (asinxron)
        db.expire_all()
        if db.query(MinarBattle).one().status in ("waiting", "abandoned"):
            break
        time.sleep(0.05)
    assert db.query(MinarBattle).one().status in ("waiting", "abandoned")


def test_battle_ticket_is_not_a_staff_token(client, db, metodist_token):
    hc, gc, host, guest, room, joined = _ws_pair(client, db, metodist_token, "typing")
    r = client.get("/auth/me", headers=H(room["ticket"]))
    assert r.status_code == 401


def test_existing_crm_error_format_unchanged(client):
    r = client.post("/auth/login", json={"username": "nobody", "password": "nope"})
    assert r.status_code == 401 and "detail" in r.json() and "message" not in r.json()
