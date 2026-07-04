"""RTSP kamerasiga ulanib, yuzlarni aniqlab, keldi/ketdi xabarlarini yuboradigan asosiy servis."""
import time
import logging
import signal
import sys

import cv2
import face_recognition

import config
from known_faces import FaceDB
from tracker import PresenceTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("camera.service")

_running = True


def _stop(*_):
    global _running
    _running = False
    log.info("To'xtatish signali qabul qilindi...")


def _open_stream() -> cv2.VideoCapture | None:
    if not config.RTSP_URL:
        log.error("RTSP_URL sozlanmagan (.env faylini tekshiring)")
        return None
    log.info("Kameraga ulanmoqda: %s", config.RTSP_URL.split("@")[-1])
    cap = cv2.VideoCapture(config.RTSP_URL, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # kechikishni kamaytirish
    if not cap.isOpened():
        return None
    return cap


def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    faces = FaceDB()
    faces.load()
    if not faces.encodings:
        log.warning("Ma'lum yuzlar yo'q. faces/<student_id>/*.jpg qo'shing.")

    tracker = PresenceTracker()

    cap = None
    frame_no = 0
    last_sweep = time.time()

    while _running:
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            cap = _open_stream()
            if cap is None:
                log.warning("Ulanib bo'lmadi, 5s dan so'ng qayta urinish...")
                time.sleep(5)
                continue

        ok, frame = cap.read()
        if not ok:
            log.warning("Kadr o'qilmadi, qayta ulanish...")
            cap.release()
            cap = None
            time.sleep(2)
            continue

        frame_no += 1
        if frame_no % config.FRAME_SKIP == 0:
            _process(frame, faces, tracker)

        # Vaqti-vaqti bilan ketganlarni tekshirish
        if time.time() - last_sweep >= 10:
            tracker.sweep()
            last_sweep = time.time()

    if cap is not None:
        cap.release()
    log.info("Servis to'xtadi.")


def _process(frame, faces: FaceDB, tracker: PresenceTracker) -> None:
    # Tezlik uchun kadrni kichraytiramiz va BGR->RGB o'giramiz
    small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

    locations = face_recognition.face_locations(rgb, model=config.DETECTION_MODEL)
    if not locations:
        return
    encodings = face_recognition.face_encodings(rgb, locations)

    for enc in encodings:
        student_id = faces.match(enc)
        if student_id is not None:
            tracker.seen(student_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("Kutilmagan xatolik: %s", exc)
        sys.exit(1)
