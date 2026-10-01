"""Space: haftalik turnir (ochko, reyting, mukofot) va ota-onaga haftalik hisobot."""
from datetime import date, datetime, timedelta

import pytest

from backend import models, tz
from backend.minar import weekly
from backend.minar.models import (
    MinarAccount, MinarAchievement, MinarLedger, MinarLesson, MinarNotification, MinarPlaygroundSolve, MinarResult,
    MinarTournamentAward,
)
from backend.tests.test_minar import _minar_env, login  # noqa: F401

WEEK = date(2026, 9, 28)                      # dushanba
MID = datetime(2026, 9, 30, 8, 0)             # hafta o'rtasi (UTC)


@pytest.fixture
def league(db):
    """Ikki guruh, har birida o'quvchilar; bitta test akkaunt va bitta guruhsiz o'quvchi."""
    g1 = models.Group(name="F-1", stage="foundation", is_active=True)
    g2 = models.Group(name="F-2", stage="foundation", is_active=True)
    db.add_all([g1, g2])
    db.flush()
    accs = {}

    def make(name, group, test=False):
        st = models.Student(full_name=name, phone1="+998900000000", is_active=not test, is_archived=test)
        db.add(st)
        db.flush()
        if group:
            db.add(models.GroupStudent(group_id=group.id, student_id=st.id))
        acc = MinarAccount(student_id=st.id, login_id=f"MA{st.id:04d}", password_hash="x", is_test=test)
        db.add(acc)
        db.flush()
        accs[name] = acc
        return acc

    for n in ("Ali A", "Bek B", "Can C", "Dil D"):
        make(n, g1)
    make("Eli E", g2)
    make("Test T", g1, test=True)
    make("Yolg‘iz Y", None)
    db.commit()
    return accs, g1, g2


def xp(db, acc, amount, when=MID):
    db.add(MinarResult(account_id=acc.id, result_id=f"r{acc.id}-{amount}-{when.timestamp()}", game="quiz",
                       payload="{}", award=0, xp=amount, local_date=when.date().isoformat(), created_at=when))
    db.commit()


def test_points_sum_week_sources_only(db, league):
    accs, _, _ = league
    a = accs["Ali A"]
    xp(db, a, 50)
    xp(db, a, 50, when=datetime(2026, 9, 27, 18, 59))     # Toshkentda yakshanba 23:59 — o'tgan hafta
    xp(db, a, 10, when=datetime(2026, 9, 27, 19, 0))      # Toshkentda dushanba 00:00 — shu hafta
    db.add(MinarLesson(account_id=a.id, course="HTML", lesson_index=0, completed_at=MID))
    db.add(MinarPlaygroundSolve(account_id=a.id, task_id="html-1", code="{}", xp=30, solved_at=MID))
    db.commit()
    assert weekly.points(db, WEEK, [a.id]) == {a.id: 50 + 10 + 50 + 30}


def test_finalize_awards_top3_per_group_once(db, league):
    accs, g1, g2 = league
    for name, pts in (("Ali A", 300), ("Bek B", 200), ("Can C", 100), ("Dil D", 90), ("Eli E", 40), ("Test T", 999)):
        xp(db, accs[name], pts)
    assert weekly.finalize_week(db, WEEK) == 3                                     # Eli < MIN_POINTS, Test — test akkaunt
    awards = {a.account_id: a for a in db.query(MinarTournamentAward).all()}
    assert [(awards[accs[n].id].place, awards[accs[n].id].coins) for n in ("Ali A", "Bek B", "Can C")] == \
        [(1, 50), (2, 30), (3, 20)]
    assert db.query(MinarLedger).filter(MinarLedger.kind == "tournament").count() == 3
    assert db.query(MinarNotification).filter(MinarNotification.kind == "tournament").count() == 3
    codes = {a.code for a in db.query(MinarAchievement).filter(MinarAchievement.account_id == accs["Ali A"].id)}
    assert {"tournament_win", "tournament_podium"} <= codes
    assert weekly.finalize_week(db, WEEK) == 0                                     # qayta — hech narsa
    assert db.query(MinarTournamentAward).count() == 3


def test_standings_for_group_and_overall(client, db, league, monkeypatch):
    accs, _, _ = league
    monkeypatch.setattr(weekly.tz, "today", lambda: date(2026, 9, 30))
    xp(db, accs["Ali A"], 120)
    xp(db, accs["Eli E"], 500)
    xp(db, accs["Test T"], 999)
    data = weekly.standings(db, accs["Bek B"])
    assert data["week"] == {"start": "2026-09-28", "end": "2026-10-04", "endsAt": "2026-10-05T00:00:00+05:00"}
    names = [r["name"] for r in data["group"]["standings"]]
    assert data["group"]["name"] == "F-1" and names[0] == "Ali A." and "Test T." not in names
    me = next(r for r in data["group"]["standings"] if r["me"])
    assert me["points"] == 0 and data["myPoints"] == 0
    assert [r["name"] for r in data["overall"]] == ["Eli E.", "Ali A."]           # 0 ochkolilar umumiy ro'yxatda yo'q
    assert weekly.standings(db, accs["Yolg‘iz Y"])["group"] is None


def test_run_due_respects_first_week(db, league, monkeypatch):
    accs, _, _ = league
    xp(db, accs["Ali A"], 300, when=datetime(2026, 9, 23, 8, 0))                 # turnirdan oldingi hafta
    monkeypatch.setattr(weekly.tz, "today", lambda: date(2026, 9, 30))
    weekly.run_due(db)
    assert db.query(MinarTournamentAward).count() == 0
    xp(db, accs["Ali A"], 300)
    monkeypatch.setattr(weekly.tz, "today", lambda: date(2026, 10, 5))
    monkeypatch.setattr(weekly.tz, "now", lambda: datetime(2026, 10, 5, 10, 0))
    weekly.run_due(db)
    assert db.query(MinarTournamentAward).count() == 1


def test_parent_weekly_report(db, league):
    accs, g1, _ = league
    ali = accs["Ali A"]
    parent = models.Parent(full_name="Ota", phone="+998901234500", username="ota", hashed_password="x")
    db.add(parent)
    db.flush()
    db.add(models.ParentChild(parent_id=parent.id, student_id=ali.student_id))
    db.add(models.Attendance(group_id=g1.id, student_id=ali.student_id, lesson_date=date(2026, 9, 29), is_present=True))
    db.add(models.Attendance(group_id=g1.id, student_id=ali.student_id, lesson_date=date(2026, 10, 1), is_present=False))
    db.add(MinarLedger(account_id=ali.id, ref_key="x", kind="game", title="t", amount=15, local_date="2026-09-30"))
    xp(db, ali, 50)
    assert weekly.send_parent_reports(db, WEEK) == 1
    n = db.query(models.ParentNotification).one()
    assert n.type == "report" and n.title == "Haftalik hisobot: Ali"
    assert "Davomat: 1/2" in n.body and "O‘yinlar: 1 ta" in n.body and "ochko (XP): 50" in n.body
    assert "coin: 15" in n.body
    assert weekly.send_parent_reports(db, WEEK) == 0                              # bir marta


def test_tournament_endpoint(client, db, metodist_token):
    from backend.tests.test_minar import new_account
    _, creds = new_account(client, db, metodist_token)
    login(client, creds)
    r = client.get("/space/tournament")
    assert r.status_code == 200 and r.json()["prizes"] == list(weekly.PRIZES) and r.json()["group"]["name"] == "S-100"
