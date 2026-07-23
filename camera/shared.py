"""Servis modullari o'rtasida umumiy holat (thread-safe)."""
import threading
from datetime import datetime

_lock   = threading.Lock()
_events = []          # [{name, event_type, time}]


def record(name: str, event_type: str) -> None:
    with _lock:
        _events.append({
            "name":       name,
            "event_type": event_type,
            "time":       datetime.now().strftime("%H:%M"),
        })
        if len(_events) > 200:
            del _events[0]


def get_events() -> list:
    with _lock:
        return list(_events)
