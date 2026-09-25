"""Fon vazifalari servisi (Docker: `worker`) — investor statistikasi va eslatmalar.

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

    threads = [
        app_main.start_investor_scheduler(force=True),
        app_main.start_reminder_scheduler(force=True),
    ]
    log.info("Worker ishga tushdi: %s", ", ".join(t.name for t in threads))
    while True:
        time.sleep(30)
        dead = [t.name for t in threads if not t.is_alive()]
        if dead:
            log.error("Rejalashtiruvchi to'xtadi: %s — qayta ishga tushiriladi", ", ".join(dead))
            sys.exit(1)


if __name__ == "__main__":
    main()
