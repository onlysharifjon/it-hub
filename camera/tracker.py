"""Har bir shaxsning hozirlik holatini kuzatadi va keldi/ketdi hodisalarini aniqlaydi."""
import time
import logging
from dataclasses import dataclass, field

import config
import db
import logger as xl
import notifier

log = logging.getLogger("camera.tracker")


@dataclass
class Presence:
    present: bool = False
    last_seen: float = 0.0
    last_notified: float = 0.0
    person: dict = field(default_factory=dict)
    person_type: str = "student"


class PresenceTracker:
    """Kadrlarda ko'ringan yuzlarga qarab keldi/ketdi holatini boshqaradi."""

    def __init__(self):
        # key: (person_id, person_type)
        self._state: dict[tuple, Presence] = {}

    def seen(self, person_info: dict, photo_path: str | None = None) -> None:
        """Kadrda shaxs ko'rindi — kerak bo'lsa 'keldi' hodisasini yuboradi."""
        pid = person_info["id"]
        ptype = person_info["type"]   # 'student' | 'staff'
        key = (pid, ptype)
        now = time.time()

        st = self._state.get(key)
        if st is None:
            # DB dan to'liq ma'lumot yuklaymiz
            if ptype == "staff":
                data = db.get_staff(pid) or {"id": pid, "type": "staff", "groups": []}
            else:
                data = db.get_student(pid) or {"id": pid, "type": "student", "groups": []}
            st = Presence(person=data, person_type=ptype)
            self._state[key] = st

        st.last_seen = now

        if not st.present:
            st.present = True
            if now - st.last_notified >= config.NOTIFY_COOLDOWN:
                st.last_notified = now
                log.info("KELDI [%s]: %s", ptype, st.person.get("full_name", pid))
                notifier.notify_arrival(st.person, photo_path)
                xl.log_event(st.person, ptype, "arrival")
                return  # foto notifier tomonidan o'chiriladi

        # Xabar yuborilmadi — fotoни tozalaymiz
        if photo_path:
            notifier._cleanup(photo_path)

    def sweep(self) -> None:
        """Belgilangan vaqtdan beri ko'rinmaganlarni 'ketdi' deb belgilaydi."""
        now = time.time()
        for (pid, ptype), st in self._state.items():
            if st.present and (now - st.last_seen) >= config.ABSENCE_TIMEOUT:
                st.present = False
                st.last_notified = now
                log.info("KETDI [%s]: %s", ptype, st.person.get("full_name", pid))
                notifier.notify_departure(st.person)
                xl.log_event(st.person, ptype, "departure")
