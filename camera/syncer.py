"""CRM serverdan o'quvchilar va xodimlar rasmlarini yuklab, encodinglarni yangilaydi."""
import os
import time
import logging

import requests

import config

log = logging.getLogger("camera.syncer")

_last_sync: float = 0.0


def needs_sync() -> bool:
    return time.time() - _last_sync >= config.SYNC_INTERVAL


def sync_students(face_db) -> None:
    """CRM dan o'quvchilar va xodimlar rasmlarini yuklab, kerak bo'lsa encodinglarni qayta tuzadi."""
    global _last_sync

    if not config.CRM_URL or not config.CAMERA_API_KEY:
        log.warning("CRM_URL yoki CAMERA_API_KEY sozlanmagan — sinxronizatsiya o'tkazilmadi")
        _last_sync = time.time()
        return

    changed = False

    # O'quvchilar
    changed |= _sync_endpoint(
        endpoint="/camera/students",
        photo_key="photo_url",
        sub_dir="students",
    )

    # Xodimlar
    changed |= _sync_endpoint(
        endpoint="/camera/staff",
        photo_key="face_photo_url",
        sub_dir="staff",
    )

    if changed:
        log.info("Rasm bazasi o'zgardi, encoding qayta tuzilmoqda...")
        face_db.reload()

    _last_sync = time.time()


def _sync_endpoint(endpoint: str, photo_key: str, sub_dir: str) -> bool:
    """Berilgan endpoint dan shaxslar ro'yxatini yuklab, rasmlarni saqlaydi.
    O'zgarish bo'lsa True qaytaradi."""
    try:
        resp = requests.get(
            f"{config.CRM_URL}{endpoint}",
            headers={"X-Camera-Key": config.CAMERA_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        persons = resp.json()
    except Exception as exc:
        log.warning("CRM dan yuklab bo'lmadi (%s): %s", endpoint, exc)
        return False

    changed = False
    base_dir = os.path.join(config.FACES_DIR, sub_dir)
    os.makedirs(base_dir, exist_ok=True)

    for p in persons:
        person_id = p.get("id")
        photo_url = p.get(photo_key)
        if not person_id or not photo_url:
            continue

        dir_path = os.path.join(base_dir, str(person_id))
        os.makedirs(dir_path, exist_ok=True)
        img_path = os.path.join(dir_path, "face.jpg")

        full_url = f"{config.CRM_URL}{photo_url}" if photo_url.startswith("/") else photo_url
        try:
            img_resp = requests.get(
                full_url,
                headers={"X-Camera-Key": config.CAMERA_API_KEY},
                timeout=15,
            )
            img_resp.raise_for_status()
            new_content = img_resp.content
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    if f.read() == new_content:
                        continue  # o'zgarmagan
            with open(img_path, "wb") as f:
                f.write(new_content)
            log.info("Rasm yangilandi: %s id=%s", sub_dir, person_id)
            changed = True
        except Exception as exc:
            log.warning("Rasm yuklab bo'lmadi (%s id=%s): %s", sub_dir, person_id, exc)

    log.info("%s sinxronlandi: %d ta", sub_dir, len(persons))
    return changed
