"""CRM serverdan o'quvchilar va xodimlar rasmlarini yuklab, encodinglarni yangilaydi.
Ma'lumotlar (ism, guruh, telegram_id) lokal JSON keshga saqlanadi — DB kerak emas.

Sinxronizatsiya tartibi:
  1) /camera/students   — Camera API key bilan (to'liq, guruh + foto URL)
  2) Agar fails → /api/auth/login + /students — admin auth bilan (faqat nomlar)
  Rasmlar: /camera/photo/student/{id}  (Camera API key)
"""
import os
import json
import time
import logging

import requests

import config

log = logging.getLogger("camera.syncer")

_last_sync: float = 0.0
_admin_token: str = ""
_token_expiry: float = 0.0

_CACHE_DIR      = os.path.join(os.path.dirname(__file__), "cache")
_STUDENTS_CACHE = os.path.join(_CACHE_DIR, "students.json")
_STAFF_CACHE    = os.path.join(_CACHE_DIR, "staff.json")


def _load_cache(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return {str(p["id"]): p for p in json.load(f)}
    except Exception:
        return {}


def _save_cache(path: str, persons: list) -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(persons, f, ensure_ascii=False, indent=2)


def get_student(student_id: int) -> dict | None:
    cache = _load_cache(_STUDENTS_CACHE)
    return cache.get(str(student_id))


def get_staff(user_id: int) -> dict | None:
    cache = _load_cache(_STAFF_CACHE)
    return cache.get(str(user_id))


def needs_sync() -> bool:
    return time.time() - _last_sync >= config.SYNC_INTERVAL


# ── Admin token ───────────────────────────────────────────────────────────────

def _get_admin_token() -> str:
    global _admin_token, _token_expiry
    if _admin_token and time.time() < _token_expiry:
        return _admin_token
    user = getattr(config, "CRM_ADMIN_USER", "")
    pwd  = getattr(config, "CRM_ADMIN_PASS", "")
    if not user or not pwd:
        return ""
    try:
        resp = requests.post(
            f"{config.CRM_URL}/api/auth/login",
            json={"username": user, "password": pwd},
            timeout=15,
        )
        data = resp.json()
        token = data.get("access_token", "")
        if token:
            _admin_token  = token
            _token_expiry = time.time() + 3600 * 8  # 8 soat
            log.info("Admin token olindi")
        else:
            log.warning("Admin login muvaffaqiyatsiz: %s", data)
    except Exception as exc:
        log.warning("Admin login xatosi: %s", exc)
    return _admin_token


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync_students(face_db) -> None:
    global _last_sync

    if not config.CRM_URL or not config.CAMERA_API_KEY:
        log.warning("CRM_URL yoki CAMERA_API_KEY sozlanmagan")
        _last_sync = time.time()
        return

    changed = False
    changed |= _sync_students()
    changed |= _sync_staff()

    if changed:
        log.info("O'zgarish bor — encoding qayta tuzilmoqda...")
        face_db.reload()

    _last_sync = time.time()


# ── Students sync ─────────────────────────────────────────────────────────────

def _sync_students() -> bool:
    cam_headers = {"X-Camera-Key": config.CAMERA_API_KEY}

    # 1) Camera API orqali to'liq ma'lumot
    try:
        resp = requests.get(
            f"{config.CRM_URL}/camera/students",
            headers=cam_headers,
            timeout=30,
        )
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type:
                persons = resp.json()
                log.info("camera/students: %d ta o'quvchi", len(persons))
                _save_cache(_STUDENTS_CACHE, persons)
                return _download_photos(persons, "students", cam_headers)
    except Exception as exc:
        log.warning("camera/students xatosi: %s", exc)

    # 2) Fallback: admin auth + /api/students
    return _sync_students_admin()


def _sync_students_admin() -> bool:
    token = _get_admin_token()
    if not token:
        log.warning("Admin token yo'q — studentlar yangilanmaydi")
        return False

    headers = {"Authorization": f"Bearer {token}"}
    try:
        # Barcha faol o'quvchilarni yuklash (sahifalar)
        all_persons = []
        page = 1
        while True:
            resp = requests.get(
                f"{config.CRM_URL}/api/students",
                headers=headers,
                params={"is_active": True, "limit": 200, "skip": (page - 1) * 200},
                timeout=30,
            )
            resp.raise_for_status()
            batch = resp.json()
            if isinstance(batch, list):
                all_persons.extend(batch)
                if len(batch) < 200:
                    break
                page += 1
            elif isinstance(batch, dict) and "items" in batch:
                all_persons.extend(batch["items"])
                if len(all_persons) >= batch.get("total", 0):
                    break
                page += 1
            else:
                break
        log.info("Admin /students: %d ta o'quvchi", len(all_persons))
        _save_cache(_STUDENTS_CACHE, all_persons)
        # Rasmlarni camera API orqali yuklaymiz
        cam_headers = {"X-Camera-Key": config.CAMERA_API_KEY}
        return _download_photos_by_id(all_persons, "students", cam_headers)
    except Exception as exc:
        log.warning("Admin students xatosi: %s", exc)
        return False


# ── Staff sync ────────────────────────────────────────────────────────────────

def _sync_staff() -> bool:
    cam_headers = {"X-Camera-Key": config.CAMERA_API_KEY}
    try:
        resp = requests.get(
            f"{config.CRM_URL}/camera/staff",
            headers=cam_headers,
            timeout=30,
        )
        if resp.status_code == 200 and "json" in resp.headers.get("Content-Type", ""):
            persons = resp.json()
            log.info("camera/staff: %d ta xodim", len(persons))
            _save_cache(_STAFF_CACHE, persons)
            return _download_staff_photos(persons, cam_headers)
    except Exception as exc:
        log.warning("camera/staff xatosi: %s", exc)
    return False


# ── Photo download helpers ────────────────────────────────────────────────────

def _download_photos(persons: list, sub_dir: str, cam_headers: dict) -> bool:
    """photo_url bor bo'lsa, to'g'ridan-to'g'ri yuklab oladi."""
    changed  = False
    base_dir = os.path.join(config.FACES_DIR, sub_dir)
    os.makedirs(base_dir, exist_ok=True)

    for p in persons:
        pid       = p.get("id")
        photo_url = p.get("photo_url")
        if not pid:
            continue

        dir_path = os.path.join(base_dir, str(pid))
        os.makedirs(dir_path, exist_ok=True)

        if not photo_url:
            # photo_url yo'q — camera API photo endpoint ni sinab ko'rish
            changed |= _fetch_photo_by_id(pid, "student", dir_path, cam_headers)
            continue

        full_url = (f"{config.CRM_URL}{photo_url}"
                    if photo_url.startswith("/") else photo_url)
        changed |= _save_photo(full_url, dir_path, cam_headers)

    return changed


def _download_staff_photos(persons: list, cam_headers: dict) -> bool:
    changed  = False
    base_dir = os.path.join(config.FACES_DIR, "staff")
    os.makedirs(base_dir, exist_ok=True)

    for p in persons:
        pid       = p.get("id")
        photo_url = p.get("face_photo_url")
        if not pid:
            continue

        dir_path = os.path.join(base_dir, str(pid))
        os.makedirs(dir_path, exist_ok=True)

        if not photo_url:
            changed |= _fetch_photo_by_id(pid, "staff", dir_path, cam_headers)
            continue

        full_url = (f"{config.CRM_URL}{photo_url}"
                    if photo_url.startswith("/") else photo_url)
        changed |= _save_photo(full_url, dir_path, cam_headers)

    return changed


def _download_photos_by_id(persons: list, sub_dir: str, cam_headers: dict) -> bool:
    """Admin auth bilan olingan ro'yxat uchun — rasmlarni ID orqali yuklaydi."""
    changed  = False
    base_dir = os.path.join(config.FACES_DIR, sub_dir)
    os.makedirs(base_dir, exist_ok=True)

    for p in persons:
        pid = p.get("id")
        if not pid:
            continue
        dir_path = os.path.join(base_dir, str(pid))
        os.makedirs(dir_path, exist_ok=True)
        changed |= _fetch_photo_by_id(pid, "student", dir_path, cam_headers)

    return changed


def _fetch_photo_by_id(pid: int, ptype: str, dir_path: str, cam_headers: dict) -> bool:
    """/camera/photo/{ptype}/{pid} endpointidan rasm yuklaydi."""
    img_path = os.path.join(dir_path, "face.jpg")
    # Agar rasm allaqachon bor va 10KB+ bo'lsa, qayta yuklamaymiz
    if os.path.exists(img_path) and os.path.getsize(img_path) > 10_000:
        return False
    url = f"{config.CRM_URL}/camera/photo/{ptype}/{pid}"
    try:
        resp = requests.get(url, headers=cam_headers, timeout=15)
        if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("image"):
            with open(img_path, "wb") as f:
                f.write(resp.content)
            log.info("Rasm yuklandi: %s id=%s", ptype, pid)
            return True
    except Exception as exc:
        log.debug("Rasm yuklanmadi (%s id=%s): %s", ptype, pid, exc)
    return False


def _save_photo(url: str, dir_path: str, headers: dict) -> bool:
    img_path = os.path.join(dir_path, "face.jpg")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False
        ct = resp.headers.get("Content-Type", "")
        if not ct.startswith("image"):
            return False
        new_bytes = resp.content
        if os.path.exists(img_path):
            with open(img_path, "rb") as f:
                if f.read() == new_bytes:
                    return False
        with open(img_path, "wb") as f:
            f.write(new_bytes)
        return True
    except Exception as exc:
        log.debug("Rasm saqlanmadi: %s", exc)
        return False
