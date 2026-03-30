"""Tests for lesson endpoints and role-based access."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Read access (both roles) ──────────────────────────────────────────────────

def test_list_lessons_as_teacher(client, teacher_token, sample_lesson):
    res = client.get("/lessons", headers=auth(teacher_token))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_list_lessons_as_metodist(client, metodist_token, sample_lesson):
    res = client.get("/lessons", headers=auth(metodist_token))
    assert res.status_code == 200


def test_get_lesson_as_teacher(client, teacher_token, sample_lesson):
    res = client.get(f"/lessons/{sample_lesson.id}", headers=auth(teacher_token))
    assert res.status_code == 200
    assert res.json()["id"] == sample_lesson.id


def test_get_lesson_not_found(client, metodist_token):
    res = client.get("/lessons/9999", headers=auth(metodist_token))
    assert res.status_code == 404


def test_list_lessons_unauthenticated(client):
    res = client.get("/lessons")
    assert res.status_code == 401


# ── Create (metodist only) ────────────────────────────────────────────────────

def test_create_lesson_as_metodist(client, metodist_token):
    payload = {"month": 1, "week": 1, "lesson_number": 10, "title": "Yangi dars"}
    res = client.post("/lessons", json=payload, headers=auth(metodist_token))
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Yangi dars"
    assert data["lesson_number"] == 10


def test_create_lesson_as_teacher_forbidden(client, teacher_token):
    payload = {"month": 1, "week": 1, "lesson_number": 10, "title": "Yangi dars"}
    res = client.post("/lessons", json=payload, headers=auth(teacher_token))
    assert res.status_code == 403


def test_create_lesson_duplicate_number(client, metodist_token, sample_lesson):
    payload = {"month": 1, "week": 1, "lesson_number": 1, "title": "Takroriy"}
    res = client.post("/lessons", json=payload, headers=auth(metodist_token))
    assert res.status_code == 400


# ── Update (metodist only) ────────────────────────────────────────────────────

def test_update_lesson_as_metodist(client, metodist_token, sample_lesson):
    res = client.put(
        f"/lessons/{sample_lesson.id}",
        json={"guide": "Yangi ko'rsatma"},
        headers=auth(metodist_token),
    )
    assert res.status_code == 200
    assert res.json()["guide"] == "Yangi ko'rsatma"


def test_update_lesson_as_teacher_forbidden(client, teacher_token, sample_lesson):
    res = client.put(
        f"/lessons/{sample_lesson.id}",
        json={"guide": "Yo'q"},
        headers=auth(teacher_token),
    )
    assert res.status_code == 403


# ── Delete (metodist only) ────────────────────────────────────────────────────

def test_delete_lesson_as_metodist(client, metodist_token, sample_lesson):
    res = client.delete(f"/lessons/{sample_lesson.id}", headers=auth(metodist_token))
    assert res.status_code == 204
    res2 = client.get(f"/lessons/{sample_lesson.id}", headers=auth(metodist_token))
    assert res2.status_code == 404


def test_delete_lesson_as_teacher_forbidden(client, teacher_token, sample_lesson):
    res = client.delete(f"/lessons/{sample_lesson.id}", headers=auth(teacher_token))
    assert res.status_code == 403


# ── Reorder (metodist only) ───────────────────────────────────────────────────

def test_reorder_lessons_as_metodist(client, db, metodist_token):
    from backend.tests.conftest import _create_lesson
    l1 = _create_lesson(db, lesson_number=1)
    l2 = _create_lesson(db, lesson_number=2)
    payload = {"items": [{"id": l1.id, "lesson_number": 2}, {"id": l2.id, "lesson_number": 1}]}
    res = client.put("/lessons/reorder", json=payload, headers=auth(metodist_token))
    assert res.status_code == 200


def test_reorder_lessons_as_teacher_forbidden(client, db, teacher_token):
    from backend.tests.conftest import _create_lesson
    l1 = _create_lesson(db, lesson_number=1)
    payload = {"items": [{"id": l1.id, "lesson_number": 5}]}
    res = client.put("/lessons/reorder", json=payload, headers=auth(teacher_token))
    assert res.status_code == 403