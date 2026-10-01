"""Space ↔ CRM: guruh dasturi va uy vazifasi (topshirish, baholash, coin, bildirishnomalar)."""
from datetime import date, timedelta

import pytest

from backend import models, tz
from backend.minar.models import MinarAchievement, MinarNotification
from backend.tests.conftest import _create_lesson
from backend.tests.test_minar import H, _minar_env, login, post  # noqa: F401


@pytest.fixture
def klass(client, db, metodist_token, teacher_user):
    """O'qituvchi guruhi + Space akkaunti bor talaba (sessiya ochilgan)."""
    group = models.Group(name="F-1", stage="foundation", is_active=True, teacher_id=teacher_user.id)
    db.add(group)
    db.flush()
    st = models.Student(full_name="Ali Valiyev", phone1="+998901112233", is_active=True)
    other = models.Student(full_name="Bekzod Karimov", phone1="+998901112234", is_active=True)
    db.add_all([st, other])
    db.flush()
    db.add_all([models.GroupStudent(group_id=group.id, student_id=st.id),
                models.GroupStudent(group_id=group.id, student_id=other.id)])
    db.commit()
    creds = client.post("/space/admin/accounts", json={"student_id": st.id}, headers=H(metodist_token)).json()
    login(client, creds)
    return group, st, other


def _homework(db, group, text="5 ta teg bilan sahifa yasang", number=2, days_ago=0, due=None):
    hw = models.Homework(group_id=group.id, lesson_number=number, lesson_title=f"{number}-dars mavzusi",
                         text=text, lesson_date=tz.today() - timedelta(days=days_ago), due_date=due)
    db.add(hw)
    db.commit()
    return hw


def test_curriculum_follows_group_progress(client, db, klass):
    group, st, _ = klass
    for n in (1, 2, 3):
        _create_lesson(db, lesson_number=n, category="foundation")
    db.query(models.Lesson).filter(models.Lesson.lesson_number == 1).update(
        {"guide": "USTOZ UCHUN MAXFIY", "title": "HTML kirish"})
    db.add(models.Attendance(student_id=st.id, group_id=group.id, lesson_date=date(2026, 9, 1), is_present=True))
    hw = _homework(db, group, number=2)
    data = client.get("/space/curriculum").json()
    assert data["group"] == "F-1" and data["completed"] == 1 and data["total"] == 24
    assert [l["status"] for l in data["lessons"]] == ["done", "next", "upcoming"]
    assert data["lessons"][1]["homeworkId"] == hw.id and data["lessons"][0]["title"] == "HTML kirish"
    assert "MAXFIY" not in str(data)                                               # metodika ochilmaydi


def test_curriculum_without_group(client, db, klass):
    _, st, _ = klass
    db.query(models.GroupStudent).filter(models.GroupStudent.student_id == st.id).update(
        {"left_at": tz.today()})
    db.commit()
    assert client.get("/space/curriculum").json() == {"group": None, "lessons": [], "completed": 0, "total": 0}


def test_submit_resubmit_and_lock_after_grading(client, db, klass, teacher_token):
    group, st, _ = klass
    hw = _homework(db, group)
    items = client.get("/space/homework").json()
    assert items[0]["status"] == "pending" and items[0]["id"] == hw.id
    assert client.get("/space/students/me/bootstrap").json()["homeworkPending"] == 1
    r = post(client, f"/homework/{hw.id}/submit", {"answer": "  <h1>Salom</h1>  ", "link": "https://codepen.io/x"})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["state"]["homeworkPending"] == 0
    assert [a["id"] for a in r["unlocked"]] == ["homework_1"]
    sub = db.query(models.HomeworkSubmission).one()
    assert sub.status == "submitted" and sub.answer == "<h1>Salom</h1>" and sub.link == "https://codepen.io/x"
    note = db.query(models.Notification).one()                                     # ustozga CRM bildirishnomasi
    assert note.user_id == group.teacher_id and "topshirdi" in note.title
    assert post(client, f"/homework/{hw.id}/submit", {"answer": "yangilandi"}).status_code == 200
    assert db.query(models.Notification).count() == 1                               # qayta topshirish — takror xabar yo'q
    g = client.patch(f"/homeworks/{hw.id}/submissions/{st.id}", json={"grade": 95, "comment": "Zo‘r!", "coins": 5},
                     headers=H(teacher_token))
    assert g.status_code == 200, g.text
    assert post(client, f"/homework/{hw.id}/submit", {"answer": "kech"}).status_code == 409
    mine = client.get("/space/homework").json()[0]
    assert mine["status"] == "graded" and mine["grade"] == 95 and mine["comment"] == "Zo‘r!" and mine["coins"] == 5


@pytest.mark.parametrize("payload,code", [
    ({"answer": ""}, 400),
    ({"answer": "   "}, 400),
    ({"answer": "x" * 5001}, 400),
    ({"answer": "ok", "link": "javascript:alert(1)"}, 400),
    ({"answer": "ok", "link": "ftp://x.uz"}, 400),
    ({"answer": 5}, 400),
])
def test_submit_validation(client, db, klass, payload, code):
    group, _, _ = klass
    hw = _homework(db, group)
    assert post(client, f"/homework/{hw.id}/submit", payload).status_code == code
    assert db.query(models.HomeworkSubmission).count() == 0


def test_cannot_submit_other_groups_homework(client, db, klass):
    other_group = models.Group(name="X-9", stage="foundation", is_active=True)
    db.add(other_group)
    db.commit()
    hw = _homework(db, other_group)
    assert post(client, f"/homework/{hw.id}/submit", {"answer": "hack"}).status_code == 404
    assert post(client, "/homework/999999/submit", {"answer": "hack"}).status_code == 404


def test_teacher_sees_submissions_and_grades_with_coins_once(client, db, klass, teacher_token):
    group, st, other = klass
    hw = _homework(db, group)
    post(client, f"/homework/{hw.id}/submit", {"answer": "javob"})
    rows = client.get(f"/homeworks/{hw.id}/submissions", headers=H(teacher_token)).json()
    assert [(r["full_name"], r["status"]) for r in rows] == [("Ali Valiyev", "submitted"), ("Bekzod Karimov", "pending")]
    assert rows[0]["answer"] == "javob" and rows[0]["has_space_account"] and not rows[1]["has_space_account"]
    lst = client.get(f"/groups/{group.id}/homeworks", headers=H(teacher_token)).json()
    assert lst[0]["submitted_count"] == 1 and lst[0]["graded_count"] == 0

    r = client.patch(f"/homeworks/{hw.id}/submissions/{st.id}", json={"grade": 92, "coins": 4}, headers=H(teacher_token))
    assert r.json()["coins"] == 4
    again = client.patch(f"/homeworks/{hw.id}/submissions/{st.id}", json={"grade": 80, "coins": 10},
                         headers=H(teacher_token))
    assert again.json()["grade"] == 80 and again.json()["coins"] == 4               # coin qayta berilmaydi
    tx = db.query(models.CoinTransaction).all()
    assert len(tx) == 1 and tx[0].amount == 4 and tx[0].teacher_id == group.teacher_id
    kinds = [n.kind for n in db.query(MinarNotification).order_by(MinarNotification.id).all()]
    assert kinds.count("homework") == 1 and "coin" in kinds                          # baho xabari bir marta
    assert db.query(MinarAchievement).filter(MinarAchievement.code == "homework_a").count() == 1
    # qog'ozda topshirganni ham baholash mumkin (javobsiz)
    paper = client.patch(f"/homeworks/{hw.id}/submissions/{other.id}", json={"grade": 70}, headers=H(teacher_token))
    assert paper.status_code == 200 and paper.json()["status"] == "graded" and paper.json()["coins"] == 0


def test_grading_respects_teacher_coin_budget(client, db, klass, teacher_token):
    group, st, _ = klass
    hw = _homework(db, group)
    db.add(models.CoinTransaction(student_id=st.id, teacher_id=group.teacher_id, amount=98))   # budjet: 2×50
    db.commit()
    r = client.patch(f"/homeworks/{hw.id}/submissions/{st.id}", json={"grade": 90, "coins": 5}, headers=H(teacher_token))
    assert r.status_code == 400 and "Coin yetarli emas" in r.json()["detail"]
    assert db.query(models.HomeworkSubmission).count() == 0                          # hech narsa saqlanmadi


def test_teacher_cannot_grade_foreign_group(client, db, klass, teacher_token):
    other_group = models.Group(name="X-9", stage="foundation", is_active=True)
    db.add(other_group)
    db.commit()
    hw = _homework(db, other_group)
    _, st, _ = klass
    assert client.get(f"/homeworks/{hw.id}/submissions", headers=H(teacher_token)).status_code == 403
    assert client.patch(f"/homeworks/{hw.id}/submissions/{st.id}", json={"grade": 90},
                        headers=H(teacher_token)).status_code == 403
    assert client.patch("/homeworks/{0}/submissions/{1}".format(_homework(db, klass[0]).id, 999999),
                        json={"grade": 90}, headers=H(teacher_token)).status_code == 404


def test_new_homework_notifies_space_students(client, db, klass, teacher_token):
    group, _, _ = klass
    r = client.post(f"/groups/{group.id}/homeworks", json={"text": "Mashq qiling", "lesson_title": "Ro‘yxatlar"},
                    headers=H(teacher_token))
    assert r.status_code == 201
    n = client.get("/space/notifications").json()["items"][0]
    assert n["kind"] == "homework" and n["link"] == "homework" and n["body"] == "Ro‘yxatlar"
    assert db.query(MinarNotification).count() == 1                                  # akkauntsiz talabaga yo'q


def test_overdue_flag(client, db, klass):
    group, _, _ = klass
    _homework(db, group, days_ago=10)
    item = client.get("/space/homework").json()[0]
    assert item["overdue"] is True and item["status"] == "pending"
