"""Fon vazifalari servisi (Docker: `worker`) — investor statistikasi, eslatmalar, Space haftalik turniri.

API'dan ajratilgan: crm-api konteynerlari `SCHEDULERS_ENABLED=false` bilan ishlaydi, shu jarayon
esa rejalashtiruvchilarni yagona nusxada yuritadi. Oqimlardan biri to'xtasa jarayon xato bilan
chiqadi — Docker (`restart: unless-stopped`) uni qayta ishga tushiradi.

    python -m backend.worker
"""
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("ithub.worker")


def main() -> None:
    from . import main as app_main
    from .minar import weekly
    from .parent import apns, digests

    threads = [
        app_main.start_investor_scheduler(force=True),
        app_main.start_reminder_scheduler(force=True),
        weekly.start_scheduler(),       # Space: haftalik turnir + ota-onaga hisobot
    ]
    push_thread = apns.start_scheduler()
    if push_thread is not None:
        threads.append(push_thread)
    digest_thread = digests.start_scheduler(app_main._students_payment_map)
    if digest_thread is not None:
        threads.append(digest_thread)
    log.info("Worker ishga tushdi: %s", ", ".join(t.name for t in threads))
    while True:
        time.sleep(30)
        dead = [t.name for t in threads if not t.is_alive()]
        if dead:
            log.error("Rejalashtiruvchi to'xtadi: %s — qayta ishga tushiriladi", ", ".join(dead))
            sys.exit(1)


if __name__ == "__main__":
    main()
