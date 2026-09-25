"""Xavfsizlik tuzatishlari: /uploads imzosi, token turlari, parol almashganda
tokenni bekor qilish, yuz rasmi yuklash tekshiruvi, kamera kaliti."""
import io
import os

import pytest

from backend import main as _main
from backend.models import UserRole
from backend.tests.conftest import _create_user

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def admin_user(db):
    return _create_user(db, "admin", "admin12345", UserRole.admin)


def _token(client, username="admin", password="admin12345"):
    return client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_uploads_require_signature(client, admin_user):
    tok = _token(client)
    res = client.post("/me/avatar", headers=_h(tok),
                      files={"file": ("a.png", io.BytesIO(PNG), "image/png")})
    assert res.status_code == 200
    avatar = res.json()["avatar"]
    rel = avatar.split("?")[0]
    # tasodifiy nom, ID emas
    assert rel.startswith("avatars/") and rel != f"avatars/{admin_user.id}.png"
    assert "sig=" in avatar

    assert client.get(f"/uploads/{avatar}").status_code == 200
    assert client.get(f"/uploads/{rel}").status_code == 403                  # imzosiz
    assert client.get(f"/uploads/{rel}?exp=9999999999&sig=00").status_code == 403
    assert client.get("/uploads/../.env").status_code in (403, 404)


def test_certificates_stay_public(client):
    d = os.path.join(_main.UPLOAD_DIR, "certificates")
    with open(os.path.join(d, "abc.pdf"), "wb") as f:
        f.write(b"%PDF-1.4")
    assert client.get("/uploads/certificates/abc.pdf").status_code == 200


def test_download_token_rejected_as_api_token(client, admin_user):
    tok = _token(client)
    dl = client.get("/auth/download-token", headers=_h(tok)).json()["token"]
    assert client.get("/auth/me", headers=_h(dl)).status_code == 401


def test_password_change_revokes_old_tokens(client, admin_user):
    old = _token(client)
    assert client.get("/auth/me", headers=_h(old)).status_code == 200
    res = client.put("/me", headers=_h(old),
                     json={"password": "newpass12345", "current_password": "admin12345"})
    assert res.status_code == 200
    assert client.get("/auth/me", headers=_h(old)).status_code == 401
    new = _token(client, password="newpass12345")
    assert client.get("/auth/me", headers=_h(new)).status_code == 200


def test_face_photo_checks_content_and_size(client, db, admin_user):
    from backend.models import Student
    s = Student(full_name="Ali", phone1="+998901234567", is_active=True)
    db.add(s); db.commit()
    h = _h(_token(client))
    bad = client.post(f"/students/{s.id}/face-photo", headers=h,
                      files={"file": ("x.jpg", io.BytesIO(b"<html>not an image"), "image/jpeg")})
    assert bad.status_code == 400
    big = client.post(f"/students/{s.id}/face-photo", headers=h,
                      files={"file": ("x.png", io.BytesIO(PNG + b"\x00" * (6 * 1024 * 1024)), "image/png")})
    assert big.status_code == 400
    ok = client.post(f"/students/{s.id}/face-photo", headers=h,
                     files={"file": ("x.png", io.BytesIO(PNG), "image/png")})
    assert ok.status_code == 200
    url = ok.json()["photo_url"]
    assert "sig=" in url and "/student_photos/" in url and f"/{s.id}." not in url


def test_camera_key_required(client, monkeypatch):
    monkeypatch.setattr(_main, "CAMERA_API_KEY", "cam-key-123")
    assert client.get("/camera/staff").status_code == 403
    assert client.get("/camera/staff", headers={"x-camera-key": "wrong"}).status_code == 403
    assert client.get("/camera/staff", headers={"x-camera-key": "cam-key-123"}).status_code == 200


def test_login_lockout_is_per_ip(client, admin_user):
    for _ in range(5):
        client.post("/auth/login", json={"username": "admin", "password": "wrong"},
                    headers={"x-real-ip": "6.6.6.6"})
    assert client.post("/auth/login", json={"username": "admin", "password": "wrong"},
                       headers={"x-real-ip": "6.6.6.6"}).status_code == 429
    # boshqa IP'dan haqiqiy egasi kira oladi
    assert client.post("/auth/login", json={"username": "admin", "password": "admin12345"},
                       headers={"x-real-ip": "1.2.3.4"}).status_code == 200
