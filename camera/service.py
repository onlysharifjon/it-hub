"""RTSP kamerasiga ulanib, yuzlarni aniqlab, keldi/ketdi xabarlarini yuboradigan asosiy servis."""
import os
import time
import logging
import signal
import sys

import cv2
import face_recognition

import config
import syncer
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
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        return None
    return cap


def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    faces = FaceDB()

    # CRM dan rasmlarni yuklaymiz (birinchi ishga tushishda)
    log.info("CRM bilan sinxronizatsiya boshlandi...")
    syncer.sync_students(faces)

    faces.load()
    if not faces.encodings:
        log.warning("Ma'lum yuzlar yo'q. faces/students/ va faces/staff/ papkalarini tekshiring.")

    tracker = PresenceTracker()

    cap = None
    frame_no = 0
    last_sweep = time.time()

    while _running:
        # Vaqti-vaqti bilan CRM bilan sinxronlaymiz
        if syncer.needs_sync():
            syncer.sync_students(faces)

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

        # Ketganlarni tekshirish
        if time.time() - last_sweep >= 10:
            tracker.sweep()
            last_sweep = time.time()

    if cap is not None:
        cap.release()
    log.info("Servis to'xtadi.")


def _process(frame, faces: FaceDB, tracker: PresenceTracker) -> None:
    small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

    locations = face_recognition.face_locations(rgb, model=config.DETECTION_MODEL)
    if not locations:
        return
    encodings = face_recognition.face_encodings(rgb, locations)

    h, w = frame.shape[:2]
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    for enc, loc in zip(encodings, locations):
        person = faces.match(enc)
        if person is None:
            continue  # begona — skip

        # Yuz sohasini crop qilib temp faylga saqlaymiz
        top, right, bottom, left = [v * 2 for v in loc]  # 0.5x kichraytirish teskari
        pad = 30
        face_crop = frame[
            max(0, top - pad):min(h, bottom + pad),
            max(0, left - pad):min(w, right + pad),
        ]
        tmp_name = f"face_{person['type']}_{person['id']}_{int(time.time() * 1000)}.jpg"
        tmp_path = os.path.join(config.TEMP_DIR, tmp_name)
        cv2.imwrite(tmp_path, face_crop)

        tracker.seen(person, tmp_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("Kutilmagan xatolik: %s", exc)
        sys.exit(1)
