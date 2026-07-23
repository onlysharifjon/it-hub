"""Har bir shaxsning hozirlik holatini kuzatadi va keldi/ketdi hodisalarini aniqlaydi."""
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import requests

import config
import db
import logger as xl
import notifier
import shared

log = logging.getLogger("camera.tracker")


def _checkin_backend(person_id: int, person_type: str, event: str) -> None:
    """Backend'ga keldi/ketdi yuboradi (background thread)."""
    if not config.CRM_URL or not config.CAMERA_API_KEY:
        return
    def _send():
        try:
            requests.post(
                f"{config.CRM_URL}/camera/checkin",
                json={"student_id": person_id, "event": event, "person_type": person_type},
                headers={"X-Camera-Key": config.CAMERA_API_KEY},
                timeout=5,
            )
        except Exception as exc:
            log.debug("Checkin yuborilmadi: %s", exc)
    threading.Thread(target=_send, daemon=True).start()


@dataclass
class Presence:
    present: bool = False
    last_seen: float = 0.0
    last_notified: float = 0.0
    person: dict = field(default_factory=dict)
    person_type: str = "student"


class PresenceTracker:
    def __init__(self):
        self._state: dict[tuple, Presence] = {}
        self._emit: Optional[Callable] = None

    def _get_or_create(self, person_info: dict) -> Presence:
        pid   = person_info["id"]
        ptype = person_info["type"]
        key   = (pid, ptype)
        if key not in self._state:
            if ptype == "unknown":
                data = person_info
            else:
                data = (db.get_staff(pid) if ptype == "staff" else db.get_student(pid)) \
                       or {"id": pid, "type": ptype, "groups": []}
            self._state[key] = Presence(person=data, person_type=ptype)
        return self._state[key]

    def seen(self, person_info: dict, photo_path: str | None = None) -> None:
        """Shaxs ko'rindi — last_seen yangilaydi, hech qanday event chiqarmaydi."""
        st = self._get_or_create(person_info)
        st.last_seen = time.time()
        if photo_path:
            notifier._cleanup(photo_path)

    def arrive(self, person_info: dict, photo_path: str | None = None) -> None:
        """Yuz aniqlandi — agar avval yo'q bo'lsa keldi event."""
        st  = self._get_or_create(person_info)
        now = time.time()
        st.last_seen = now

        # Allaqachon hozir — takroriy event yo'q
        if st.present:
            if photo_path:
                notifier._cleanup(photo_path)
            return

        if now - st.last_notified < config.NOTIFY_COOLDOWN:
            if photo_path:
                notifier._cleanup(photo_path)
            return

        st.present       = True
        st.last_notified = now
        name   = st.person.get("full_name", str(person_info["id"]))
        groups = st.person.get("groups", [])
        log.info("KELDI [%s]: %s", person_info["type"], name)
        shared.record(name, "keldi")
        _checkin_backend(person_info["id"], person_info["type"], "keldi")
        if self._emit:
            self._emit("keldi", name, person_info["type"], groups)
        notifier.notify_arrival(st.person, photo_path)
        xl.log_event(st.person, person_info["type"], "arrival")

    def depart(self, person_info: dict, photo_path: str | None = None) -> None:
        """1-chiziq kesib o'tildi — ketdi event."""
        st  = self._get_or_create(person_info)
        now = time.time()
        st.last_seen = now

        if not st.present:
            if photo_path:
                notifier._cleanup(photo_path)
            return

        st.present       = False
        st.last_notified = now
        name   = st.person.get("full_name", str(person_info["id"]))
        groups = st.person.get("groups", [])
        log.info("KETDI [%s]: %s", person_info["type"], name)
        shared.record(name, "ketdi")
        _checkin_backend(person_info["id"], person_info["type"], "ketdi")
        if self._emit:
            self._emit("ketdi", name, person_info["type"], groups)
        notifier.notify_departure(st.person, photo_path)
        xl.log_event(st.person, person_info["type"], "departure")

    def sweep(self) -> None:
        """Fallback: uzoq ko'rinmagan bo'lsa ketdi (chiziq o'tkazib yuborilgan holat)."""
        now = time.time()
        for (pid, ptype), st in self._state.items():
            if st.present and (now - st.last_seen) >= config.ABSENCE_TIMEOUT:
                st.present       = False
                st.last_notified = now
                name = st.person.get("full_name", str(pid))
                log.info("KETDI [fallback] [%s]: %s", ptype, name)
                if self._emit:
                    self._emit("ketdi", name, ptype)
                notifier.notify_departure(st.person)
                xl.log_event(st.person, ptype, "departure")
