"""Space: bildirishnomalar, yutuqlar, daraja qulflari."""
import uuid

from backend import models
from backend.minar import achievements, catalog as C
from backend.minar.models import MinarAccount, MinarAchievement, MinarLedger, MinarNotification
from backend.tests.test_minar import (  # noqa: F401  (fixture'lar)
    H, _minar_env, acct, give_coins, post, start_game,
)


def _acc(db):
    db.expire_all()
    return db.query(MinarAccount).one()


def test_notifications_list_read_and_unread_in_state(client, db, acct, metodist_token):
    st, _ = acct
    r = client.post("/coins/give", json={"student_id": st.id, "amount": 7, "reason": "Zo‘r savol"},
                    headers=H(metodist_token))
    assert r.status_code == 201, r.text
    boot = client.get("/space/students/me/bootstrap").json()
    assert boot["unreadNotifications"] == 1
    items = client.get("/space/notifications").json()
    assert items["unread"] == 1 and items["items"][0]["kind"] == "coin" and "7 coin" in items["items"][0]["title"]
    assert items["items"][0]["link"] == "history" and items["items"][0]["read"] is False
    assert post(client, "/notifications/read", {"ids": "all"}).status_code == 400
    assert post(client, "/notifications/read", {}).json() == {"unread": 0}
    assert client.get("/space/notifications").json()["items"][0]["read"] is True


def test_notifications_are_private_and_pruned(client, db, acct):
    acc = _acc(db)
    for i in range(120):
        db.add(MinarNotification(account_id=acc.id, kind="system", title=f"n{i}"))
    db.commit()
    data = client.get("/space/notifications").json()
    assert len(data["items"]) == 50 and data["items"][0]["title"] == "n119"
    assert db.query(MinarNotification).count() == 100
    st2 = models.Student(full_name="Boshqa Bola", phone1="+998900000002", is_active=True)
    db.add(st2)
    db.flush()
    acc2 = MinarAccount(student_id=st2.id, login_id="MA9999", password_hash="x")
    db.add(acc2)
    db.flush()
    other = MinarNotification(account_id=acc2.id, kind="system", title="boshqa")
    db.add(other)
    db.commit()
    assert post(client, "/notifications/read", {"ids": [other.id]}).status_code == 200
    db.refresh(other)
    assert other.read_at is None                                                   # begona bildirishnoma


def test_order_ready_notifies_student(client, db, acct, metodist_user, metodist_token):
    st, _ = acct
    give_coins(db, st, 100, metodist_user.id)
    post(client, "/shop/purchases", {"productId": "stickers", "requestId": str(uuid.uuid4())})
    order = client.get("/space/admin/orders", headers=H(metodist_token)).json()[0]
    client.patch(f"/space/admin/orders/{order['id']}", json={"status": "ready"}, headers=H(metodist_token))
    n = client.get("/space/notifications").json()["items"][0]
    assert n["kind"] == "order" and n["link"] == "shop" and "tayyor" in n["title"]


def test_achievement_unlocks_once_with_reward_and_notification(client, db, acct):
    acc = _acc(db)
    acc.streak, acc.last_login = 2, None
    db.commit()
    r = post(client, "/rewards/check-in").json()                                   # streak 3
    assert "streak_3" in [a["id"] for a in r["unlocked"]]
    reward = achievements.BY_CODE["streak_3"].reward
    assert r["state"]["balance"] == C.CHECKIN_COIN + reward
    ach = {a["id"]: a for a in r["state"]["achievements"]}
    assert ach["streak_3"]["unlockedAt"] and ach["streak_3"]["progress"] == 3
    assert ach["streak_7"]["unlockedAt"] is None and ach["streak_7"]["progress"] == 3
    assert db.query(MinarAchievement).count() == 1
    assert db.query(MinarLedger).filter(MinarLedger.kind == "achievement").count() == 1
    assert client.get("/space/notifications").json()["items"][0]["kind"] == "achievement"
    again = post(client, "/avatar/character", {"type": "character", "character": "foxy"}).json()
    assert again["unlocked"] == [] and db.query(MinarAchievement).count() == 1      # ikkinchi marta yo'q


def test_level_locks_game_difficulty(client, db, acct):
    assert post(client, "/games/start", {"game": "ztype", "difficulty": "hard"}).status_code == 403
    assert post(client, "/games/start", {"game": "typing", "difficulty": "normal"}).status_code == 403
    boot = client.get("/space/students/me/bootstrap").json()
    assert boot["level"] == 1 and boot["unlocks"]["ztype:hard"] == 4 and boot["productLevels"]["crown"] == 4
    acc = _acc(db)
    acc.xp = 3 * C.LEVEL_XP
    db.commit()
    assert start_game(client, "ztype", difficulty="hard")["difficulty"] == "hard"


def test_coin_give_without_space_account_is_silent(client, db, metodist_token):
    st = models.Student(full_name="Akkauntsiz Bola", phone1="+998900000001", is_active=True)
    db.add(st)
    db.commit()
    r = client.post("/coins/give", json={"student_id": st.id, "amount": 3}, headers=H(metodist_token))
    assert r.status_code == 201 and db.query(MinarNotification).count() == 0
