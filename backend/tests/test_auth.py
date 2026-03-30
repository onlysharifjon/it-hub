"""Tests for authentication endpoints."""


def test_login_success(client, metodist_user):
    res = client.post("/auth/login", json={"username": "metodist", "password": "metodist123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, metodist_user):
    res = client.post("/auth/login", json={"username": "metodist", "password": "yalton"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/auth/login", json={"username": "ghost", "password": "pass"})
    assert res.status_code == 401


def test_me_authenticated(client, metodist_token):
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {metodist_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "metodist"
    assert data["role"] == "metodist"


def test_me_no_token(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_invalid_token(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert res.status_code == 401