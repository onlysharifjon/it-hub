"""
Kamera oqimini real vaqtda ko'rsatadi — yuz detection (mediapipe).
Ishga tushirish: python preview.py
Chiqish: 'Q' yoki ESC tugmasini bosing
"""
import os
import sys
import time
import logging

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("preview")

# ── Ranglar ───────────────────────────────────────────────────────────────────
GREEN  = (34, 197, 94)
BLUE   = (59, 130, 246)
WHITE  = (255, 255, 255)
BLACK  = (0, 0, 0)
GRAY   = (100, 100, 100)
FONT   = cv2.FONT_HERSHEY_SIMPLEX

# ── Face_recognition mavjudligini tekshirish ──────────────────────────────────
try:
    import face_recognition
    import config
    from known_faces import FaceDB
    FULL_RECOGNITION = True
    log.info("face_recognition topildi — to'liq tanish rejimi yoqildi")
except ImportError:
    FULL_RECOGNITION = False
    log.info("face_recognition yo'q — faqat detection rejimi (mediapipe)")

# ── Yuz detektori ─────────────────────────────────────────────────────────────
try:
    import mediapipe as mp
    _mp_face = mp.solutions.face_detection
    _detector = _mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.6)
    USE_MEDIAPIPE = True
    log.info("Mediapipe face detector tayyor")
except Exception as exc:
    USE_MEDIAPIPE = False
    log.warning("Mediapipe yo'q: %s", exc)
    # Fallback: OpenCV Haar cascade
    _cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    _cascade = cv2.CascadeClassifier(_cascade_path)
    log.info("OpenCV Haar cascade ishlatilmoqda")


def detect_faces_mp(frame):
    """Mediapipe bilan yuzlarni topadi. [(top, right, bottom, left), ...]"""
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = _detector.process(rgb)
    boxes = []
    if result.detections:
        for det in result.detections:
            bb = det.location_data.relative_bounding_box
            x1 = max(0, int(bb.xmin * w))
            y1 = max(0, int(bb.ymin * h))
            x2 = min(w, int((bb.xmin + bb.width) * w))
            y2 = min(h, int((bb.ymin + bb.height) * h))
            boxes.append((y1, x2, y2, x1))  # top, right, bottom, left
    return boxes


def detect_faces_haar(frame):
    """OpenCV Haar cascade bilan yuzlarni topadi."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    boxes = []
    for (x, y, w, h) in faces:
        boxes.append((y, x + w, y + h, x))  # top, right, bottom, left
    return boxes


def detect_faces(frame):
    return detect_faces_mp(frame) if USE_MEDIAPIPE else detect_faces_haar(frame)


def draw_box(frame, top, right, bottom, left, label, color):
    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
    lbl_y = top - 10 if top > 30 else bottom + 22
    (tw, th), _ = cv2.getTextSize(label, FONT, 0.55, 1)
    cv2.rectangle(frame, (left, lbl_y - th - 6), (left + tw + 8, lbl_y + 2), color, -1)
    cv2.putText(frame, label, (left + 4, lbl_y - 3), FONT, 0.55, BLACK, 1, cv2.LINE_AA)


def open_source():
    rtsp = ""
    if FULL_RECOGNITION:
        rtsp = config.RTSP_URL
    else:
        # .env dan o'qiymiz
        from dotenv import dotenv_values
        env = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
        rtsp = env.get("RTSP_URL", "")

    if rtsp:
        log.info("RTSP ulanmoqda: ...%s", rtsp.split("@")[-1] if "@" in rtsp else rtsp[-30:])
        cap = cv2.VideoCapture(rtsp, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    else:
        log.info("RTSP_URL yo'q — webcam (0) ishlatilmoqda")
        cap = cv2.VideoCapture(0)
    return cap


def main():
    # Yuzlar bazasi
    face_db = None
    if FULL_RECOGNITION:
        log.info("Yuz bazasi yuklanmoqda...")
        face_db = FaceDB()
        face_db.load()
        log.info("%d ta encoding yuklandi", len(face_db.encodings))
        if not face_db.encodings:
            log.warning("Yuzlar yo'q — faces/students/ va faces/staff/ ni to'ldiring")

    cap = open_source()
    if not cap.isOpened():
        log.error("Kamera ochilmadi!")
        sys.exit(1)

    cv2.namedWindow("Minar Camera Preview", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Minar Camera Preview", 1280, 720)

    log.info("Oyna ochildi. Chiqish: Q yoki ESC")

    frame_no  = 0
    last_locs = []
    last_encs = []
    fps_time  = time.time()
    fps_count = 0
    fps_val   = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            log.warning("Kadr o'qilmadi, qayta urinish...")
            time.sleep(1)
            cap.release()
            cap = open_source()
            continue

        frame_no += 1
        fps_count += 1
        now = time.time()
        if now - fps_time >= 1.0:
            fps_val   = fps_count
            fps_count = 0
            fps_time  = now

        display = frame.copy()

        # Har 4 kadrda bir yuz topish
        if frame_no % 4 == 0:
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            last_locs = detect_faces(small)
            last_locs = [(t*2, r*2, b*2, l*2) for (t, r, b, l) in last_locs]
            if FULL_RECOGNITION and face_db and face_db.encodings:
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                fr_locs = [(t//2, r//2, b//2, l//2) for (t, r, b, l) in last_locs]
                last_encs = face_recognition.face_encodings(rgb, fr_locs) if fr_locs else []

        # Har kadrda box chizish
        for i, (top, right, bottom, left) in enumerate(last_locs):
            if FULL_RECOGNITION and face_db and face_db.encodings and i < len(last_encs):
                person = face_db.match(last_encs[i])
                if person:
                    pid   = person["id"]
                    ptype = person["type"]
                    from db import get_student, get_staff
                    data  = (get_staff(pid) if ptype == "staff" else get_student(pid)) or {}
                    name  = data.get("full_name") or f"ID {pid}"
                    prefix = "[XODIM]" if ptype == "staff" else "[O'QUVCHI]"
                    label  = f"{prefix} {name}"
                    color  = BLUE if ptype == "staff" else GREEN
                else:
                    label, color = "BEGONA", (0, 0, 220)
            else:
                label, color = f"Yuz #{i+1}", GREEN

            draw_box(display, top, right, bottom, left, label, color)

        # Info paneli
        mode = "To'liq tanish" if FULL_RECOGNITION else "Faqat detection"
        det  = "Mediapipe" if USE_MEDIAPIPE else "Haar"
        info = f"  {mode} | {det} | Yuzlar: {len(last_locs)} | FPS: {fps_val} | Q/ESC = chiqish  "
        cv2.rectangle(display, (0, 0), (display.shape[1], 30), (20, 20, 20), -1)
        cv2.putText(display, info, (6, 22), FONT, 0.55, WHITE, 1, cv2.LINE_AA)

        cv2.imshow("Minar Camera Preview", display)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    log.info("Yopildi.")


if __name__ == "__main__":
    main()
