"""Har bir o'quvchining hozirlik holatini kuzatadi va keldi/ketdi hodisalarini aniqlaydi."""
import time
import logging
from dataclasses import dataclass, field

import config
import db
import notifier

log = logging.getLogger("camera.tracker")


@dataclass
class Presence:
    present: bool = False
    last_seen: float = 0.0
    last_notified: float = 0.0
    student: dict = field(default_factory=dict)


class PresenceTracker:
    """Kadrlarda ko'ringan yuzlarga qarab keldi/ketdi holatini boshqaradi."""

    def __init__(self):
        self._state: dict[int, Presence] = {}

    def seen(self, student_id: int) -> None:
        """Kadrda o'quvchi ko'rindi — kerak bo'lsa 'keldi' hodisasini yuboradi."""
        now = time.time()
        st = self._state.get(student_id)
        if st is None:
            st = Presence(student=db.get_student(student_id) or {"id": student_id})
            self._state[student_id] = st

        st.last_seen = now
        if not st.present:
            st.present = True
            if now - st.last_notified >= config.NOTIFY_COOLDOWN:
                st.last_notified = now
                log.info("KELDI: %s", st.student.get("full_name", student_id))
                notifier.notify_arrival(st.student)

    def sweep(self) -> None:
        """Belgilangan vaqtdan beri ko'rinmaganlarni 'ketdi' deb belgilaydi."""
        now = time.time()
        for student_id, st in self._state.items():
            if st.present and (now - st.last_seen) >= config.ABSENCE_TIMEOUT:
                st.present = False
                st.last_notified = now
                log.info("KETDI: %s", st.student.get("full_name", student_id))
                notifier.notify_departure(st.student)
