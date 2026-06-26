"""Tests for audit log endpoints."""
import json


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_update_creates_audit_log(client, db, metodist_token, sample_lesson):
    client.put(
        f"/lessons/{sample_lesson.id}",
        json={"guide": "Yangi ko'rsatma", "homework": "Uyga vazifa"},
        headers=auth(metodist_token),
    )
    res = client.get("/audit-logs", headers=auth(metodist_token))
    assert res.status_code == 200
    logs = res.json()["items"]
    assert len(logs) >= 1
    last = logs[0]
    assert last["action"] == "update"
    assert last["entity_type"] == "lesson"
    assert last["entity_id"] == sample_lesson.id
    new_val = json.loads(last["new_value"])
    assert new_val.get("guide") == "Yangi ko'rsatma"


def test_create_lesson_creates_audit_log(client, metodist_token):
    payload = {"category": "foundation", "lesson_number": 99, "title": "Test"}
    client.post("/lessons", json=payload, headers=auth(metodist_token))
    res = client.get("/audit-logs", headers=auth(metodist_token))
    logs = res.json()["items"]
    assert any(l["action"] == "create" for l in logs)


def test_delete_creates_audit_log(client, metodist_token, sample_lesson):
    client.delete(f"/lessons/{sample_lesson.id}", headers=auth(metodist_token))
    res = client.get("/audit-logs", headers=auth(metodist_token))
    logs = res.json()["items"]
    assert any(l["action"] == "delete" and l["entity_id"] == sample_lesson.id for l in logs)


def test_audit_logs_forbidden_for_teacher(client, teacher_token):
    res = client.get("/audit-logs", headers=auth(teacher_token))
    assert res.status_code == 403


def test_lesson_audit_log_history(client, metodist_token, sample_lesson):
    client.put(
        f"/lessons/{sample_lesson.id}",
        json={"section": "Bo'lim 1"},
        headers=auth(metodist_token),
    )
    client.put(
        f"/lessons/{sample_lesson.id}",
        json={"section": "Bo'lim 2"},
        headers=auth(metodist_token),
    )
    res = client.get(f"/audit-logs/lesson/{sample_lesson.id}", headers=auth(metodist_token))
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) == 2


def test_audit_log_has_username(client, metodist_token, sample_lesson):
    client.put(
        f"/lessons/{sample_lesson.id}",
        json={"guide": "Ko'rsatma"},
        headers=auth(metodist_token),
    )
    res = client.get("/audit-logs", headers=auth(metodist_token))
    log = res.json()["items"][0]
    assert log["changed_by_username"] == "metodist"