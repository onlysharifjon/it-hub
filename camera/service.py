"""Kamera davomat servisi — background detection, annotated photos, trajectory."""
import os
import sys
import time
import json
import logging
import signal
import threading
import queue
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import cv2
import face_recognition
import numpy as np

import config
import syncer
import notifier
import bot
from known_faces import FaceDB
from tracker import PresenceTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("camera.service")

# TCP transport + 10s timeout — UDP packet loss va infinite read() hang oldini olish
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                      "rtsp_transport;tcp|timeout;10000000")

_running = True

# ── MJPEG + Meta ──────────────────────────────────────────────────────────────
MJPEG_PORT   = 8765
_mjpeg_frame = None
_mjpeg_lock  = threading.Lock()
_meta        = {"locs": [], "names": [], "fps": 0, "w": 1280, "h": 720, "trails": {}, "face_count": 0}
_meta_lock   = threading.Lock()

# ── Detection thread shared state ─────────────────────────────────────────────
_det_input  = queue.Queue(maxsize=1)
_det_result = {"locs": [], "names": [], "trails": {}}
_det_lock   = threading.Lock()


# ── Drawing helpers ───────────────────────────────────────────────────────────
def _draw_box(img, x1, y1, x2, y2, label, color):
    """Bounding box + label rasm ustiga chizadi."""
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    font   = cv2.FONT_HERSHEY_SIMPLEX
    fscale = max(0.55, min(1.1, (x2 - x1) / 300))
    thick  = 2
    (tw, th), _ = cv2.getTextSize(label, font, fscale, thick)
    lx = x1
    ly = max(y1 - 8, th + 10)
    cv2.rectangle(img, (lx, ly - th - 8), (lx + tw + 14, ly + 2), color, -1)
    cv2.putText(img, label, (lx + 7, ly - 4), font, fscale,
                (0, 0, 0), thick, cv2.LINE_AA)


def _draw_trajectory(img, pts, sx, sy, color):
    """Harakat traektoriyasini rasm ustiga chizadi."""
    if len(pts) < 2:
        return
    n = len(pts)
    for i in range(1, n):
        x1 = int(pts[i - 1][0] * sx);  y1 = int(pts[i - 1][1] * sy)
        x2 = int(pts[i][0]     * sx);  y2 = int(pts[i][1]     * sy)
        alpha = (i + 1) / n
        thick = max(1, int(alpha * 3))
        cv2.line(img, (x1, y1), (x2, y2), color, thick, cv2.LINE_AA)
    # Oxirgi nuqtada doira
    cx = int(pts[-1][0] * sx);  cy = int(pts[-1][1] * sy)
    cv2.circle(img, (cx, cy), 7, color, -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 7, (255, 255, 255), 1, cv2.LINE_AA)


# ── Placeholder frame ─────────────────────────────────────────────────────────
def _placeholder_frame():
    img = np.zeros((480, 854, 3), dtype=np.uint8)
    h, w = img.shape[:2]
    cv2.putText(img, "Kamera ulanmoqda...", (int(w * .2), int(h * .47)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (55, 55, 55), 2, cv2.LINE_AA)
    cv2.putText(img, "192.168.1.108", (int(w * .33), int(h * .58)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (38, 38, 38), 1, cv2.LINE_AA)
    _, j = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return j.tobytes()


# ── MJPEG HTTP server ─────────────────────────────────────────────────────────
class _MJPEGHandler(BaseHTTPRequestHandler):
    _ph = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith('/meta'):
            with _meta_lock:
                data = json.dumps(_meta).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path.startswith('/snap'):
            with _mjpeg_lock:
                data = _mjpeg_frame or (_MJPEGHandler._ph or _placeholder_frame())
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if _MJPEGHandler._ph is None:
            _MJPEGHandler._ph = _placeholder_frame()
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=--jpgbnd")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while _running:
                with _mjpeg_lock:
                    data = _mjpeg_frame or _MJPEGHandler._ph
                self.wfile.write(b"--jpgbnd\r\nContent-Type: image/jpeg\r\n\r\n")
                self.wfile.write(data)
                self.wfile.write(b"\r\n")
                time.sleep(0.033)
        except Exception:
            pass


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _run_mjpeg():
    try:
        _ThreadedHTTPServer(("localhost", MJPEG_PORT), _MJPEGHandler).serve_forever()
    except Exception as exc:
        log.warning("MJPEG: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────
def emit(event_type, name, person_type, groups=None):
    print(json.dumps({
        "event": event_type, "name": name,
        "person_type": person_type, "ts": time.strftime("%H:%M"),
        "groups": groups or [],
    }), flush=True)


def _stop(*_):
    global _running
    _running = False


def _open_camera():
    if config.RTSP_URL:
        url = config.RTSP_URL
        log.info("RTSP ulanmoqda: %s",
                 url.split("@")[-1] if "@" in url else url[-40:])
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if cap.isOpened():
            log.info("RTSP ulandi")
            return cap
        cap.release()
        log.warning("RTSP ochilmadi — webcam sinaydi")

    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        log.info("Webcam (0) ochildi")
        return cap
    log.error("Kamera topilmadi!")
    return None


# ── Background detection thread ───────────────────────────────────────────────
def _detection_worker(faces, tracker):
    """
    Asosiy loopni bloklamaydi.
    face_recognition CPU-da 200-800ms — shuning uchun alohida thread.
    Telegram fotosiga: bounding box + ism + harakat traektoriyasi chiziladi.
    """
    # Har bir shaxs uchun harakatini kuzatish: key = "type_id"
    trajectories  = {}   # key → {"name": str, "pts": deque[(cx,cy,ts)]}

    log.info("Detection thread ishga tushdi")

    while _running:
        try:
            task = _det_input.get(timeout=0.5)
        except queue.Empty:
            continue

        rgb, tg_frame, mw, mh, sf_w, sf_h, now = task
        sx    = mw / sf_w
        sy    = mh / sf_h
        tg_h, tg_w = tg_frame.shape[:2]
        tg_sx = tg_w / mw
        tg_sy = tg_h / mh

        try:
            upsample = 1 if config.DETECTION_MODEL == "cnn" else 2
            locs_raw = face_recognition.face_locations(
                rgb, model=config.DETECTION_MODEL, number_of_times_to_upsample=upsample)

            if not locs_raw:
                with _det_lock:
                    _det_result["locs"]   = []
                    _det_result["names"]  = []
                    _det_result["trails"] = _encode_trails(trajectories, now)
                continue

            encs        = face_recognition.face_encodings(rgb, locs_raw)
            scaled_locs = [(int(t * sy), int(r * sx), int(b * sy), int(l * sx))
                           for t, r, b, l in locs_raw]
            names = []
            os.makedirs(config.TEMP_DIR, exist_ok=True)

            for enc, sloc in zip(encs, scaled_locs):
                t_c, r_c, b_c, l_c = sloc   # full-frame coords
                cx = (l_c + r_c) // 2
                cy = (t_c + b_c) // 2
                tx1 = int(l_c * tg_sx);  ty1 = int(t_c * tg_sy)
                tx2 = int(r_c * tg_sx);  ty2 = int(b_c * tg_sy)

                person, dist = faces.match(enc)

                if person is None:
                    names.append("?")
                    ann_u = tg_frame.copy()
                    _draw_box(ann_u, tx1, ty1, tx2, ty2, "Noma'lum", (0, 0, 255))
                    tmp_u = os.path.join(
                        config.TEMP_DIR, f"f_unknown_{int(now * 1000)}.jpg")
                    cv2.imwrite(tmp_u, ann_u, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    notifier.notify_unknown(tmp_u)
                    continue

                # Yuqori ishonchli aniqlanganda yuz cropini saqlaymiz (trening uchun)
                if dist < 0.35:
                    sub = "staff" if person['type'] == 'staff' else "students"
                    auto_dir = os.path.join(config.FACES_DIR, sub, str(person['id']))
                    existing = [f for f in os.listdir(auto_dir)
                                if f.startswith("auto_") and f.endswith(".jpg")]
                    if len(existing) < 20:
                        crop = tg_frame[max(0, ty1):ty2, max(0, tx1):tx2]
                        if crop.size > 0:
                            apath = os.path.join(auto_dir, f"auto_{int(now)}.jpg")
                            cv2.imwrite(apath, crop, [cv2.IMWRITE_JPEG_QUALITY, 85])

                # Ism va prefix
                info    = (syncer.get_staff(person['id'])
                           if person['type'] == 'staff'
                           else syncer.get_student(person['id']))
                display = (info.get('full_name', f"ID{person['id']}")
                           if info else f"ID{person['id']}")
                prefix    = "[X] " if person['type'] == 'staff' else ""
                full_name = f"{prefix}{display}"
                names.append(full_name)

                # Traektoriyani yangilash
                traj_key = f"{person['type']}_{person['id']}"
                if traj_key not in trajectories:
                    trajectories[traj_key] = {
                        "name":          full_name,
                        "pts":           deque(maxlen=60),
                        "side":          None,
                        "pending":       None,
                        "pending_count": 0,
                    }
                traj = trajectories[traj_key]
                traj["pts"].append((cx, cy, now))

                # Telegram uchun annotated rasm
                color_bgr = (94, 197, 34) if person['type'] == 'student' else (255, 160, 50)
                ann      = tg_frame.copy()
                traj_pts = list(traj["pts"])
                _draw_trajectory(ann, traj_pts, tg_sx, tg_sy, color_bgr)
                _draw_box(ann, tx1, ty1, tx2, ty2, display, color_bgr)

                tmp = os.path.join(config.TEMP_DIR,
                      f"f_{person['type']}_{person['id']}_{int(now * 1000)}.jpg")
                cv2.imwrite(tmp, ann, [cv2.IMWRITE_JPEG_QUALITY, 90])

                # Ko'rindi = KELDI; pastga tushsa = KETDI
                event = _analyze_movement(traj, mh, cy)
                if event == "depart":
                    tracker.depart(person, tmp)
                else:
                    tracker.arrive(person, tmp)

            # Eski traektoriyalarni o'chirish (10s ko'rinmagan)
            stale = [k for k, v in trajectories.items()
                     if v["pts"] and now - v["pts"][-1][2] > 10]
            for k in stale:
                del trajectories[k]

            with _det_lock:
                _det_result["locs"]   = scaled_locs
                _det_result["names"]  = names
                _det_result["trails"] = _encode_trails(trajectories, now)

            log.info("Detection: %d yuz — %s",
                     len(scaled_locs),
                     ", ".join(n for n in names if n != "?") or "noma'lum")

        except Exception as exc:
            log.warning("Detection xatolik: %s", exc)

    log.info("Detection thread to'xtadi")



def _analyze_movement(traj: dict, frame_h: int, cy: int) -> str | None:
    """
    Virtual chiziq kesib o'tish + 2-kadr tasdiqlash.
    LINE_1_Y_FRAC (standart 0.55) pozitsiyasida gorizontal chiziq.
    near (Y < line) = kamera yaqini,  far (Y > line) = zina pastki qismi.
    far→near = KELDI,  near→far = KETDI.
    2 ta ketma-ket kadrda yangi tomonda bo'lsa tasdiqlash.
    """
    line_y = frame_h * config.LINE_1_Y_FRAC
    side   = "near" if cy < line_y else "far"

    if traj["side"] is None:
        traj["side"] = side
        return None

    if side == traj["side"]:
        traj["pending"]       = None
        traj["pending_count"] = 0
        return None

    # Chiziq kesib o'tildi — tasdiqlash kutilmoqda
    direction = "arrive" if side == "near" else "depart"

    if traj["pending"] == direction:
        traj["pending_count"] += 1
    else:
        traj["pending"]       = direction
        traj["pending_count"] = 1

    if traj["pending_count"] >= 2:
        traj["side"]          = side
        traj["pending"]       = None
        traj["pending_count"] = 0
        return direction

    return None


def _encode_trails(trajectories, now):
    """Traektoriyalarni meta uchun JSON-serializatsiya qilingan formatga o'giradi."""
    out = {}
    for data in trajectories.values():
        name = data["name"]
        pts  = [(x, y) for x, y, ts in data["pts"] if now - ts <= 6.0]
        if pts:
            out[name] = pts
    return out


# ── Main loop ─────────────────────────────────────────────────────────────────
def _already_running(port: int) -> bool:
    """Try to connect as client — if it works, another server is already up."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("localhost", port))
        s.close()
        return True
    except OSError:
        return False


def main():
    global _mjpeg_frame, _running, _meta

    if _already_running(MJPEG_PORT):
        log.info("Port %d already in use — another instance is running. Exiting.", MJPEG_PORT)
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    threading.Thread(target=_run_mjpeg, daemon=True).start()
    log.info("MJPEG server: http://localhost:%d", MJPEG_PORT)

    threading.Thread(target=bot.run, daemon=True).start()
    log.info("Telegram bot ishga tushdi")

    faces = FaceDB()
    log.info("CRM sinxronizatsiya...")
    syncer.sync_students(faces)
    faces.load()
    log.info("%d ta yuz yuklandi", len(faces.encodings))

    tracker = PresenceTracker()
    tracker._emit = emit

    threading.Thread(
        target=_detection_worker, args=(faces, tracker), daemon=True
    ).start()

    cap        = None
    frame_no   = 0
    fps_t      = time.time()
    fps_c      = 0
    fps_val    = 0
    last_sweep = time.time()

    while _running:
        if syncer.needs_sync():
            syncer.sync_students(faces)

        if cap is None or not cap.isOpened():
            if cap:
                cap.release()
            cap = _open_camera()
            if cap is None:
                time.sleep(5)
                continue

        ok, frame = cap.read()
        if not ok:
            log.warning("Kadr o'qilmadi — qayta ulanish")
            cap.release()
            cap = None
            time.sleep(2)
            continue

        frame_no += 1
        fps_c    += 1
        now       = time.time()
        if now - fps_t >= 1.0:
            fps_val = fps_c
            fps_c   = 0
            fps_t   = now

        # ── Detection threadga frame yuborish (non-blocking) ──────────────────
        if frame_no % config.FRAME_SKIP == 0:
            mh, mw = frame.shape[:2]
            det_w  = 960
            det_h  = int(mh * det_w / mw)
            small  = cv2.resize(frame, (det_w, det_h))
            rgb    = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            tg     = (cv2.resize(frame, (1920, int(mh * 1920 / mw)))
                      if mw > 1920 else frame.copy())
            try:
                _det_input.put_nowait((rgb, tg, mw, mh, det_w, det_h, now))
            except queue.Full:
                pass

        # sweep o'chirilgan — KETDI faqat pastga tushganda

        # ── So'nggi detection natijasini olish ───────────────────────────────
        with _det_lock:
            last_locs  = list(_det_result["locs"])
            last_names = list(_det_result["names"])
            last_trails = dict(_det_result["trails"])

        # ── MJPEG display frame (1280px, 92%) ────────────────────────────────
        h, w = frame.shape[:2]
        dw   = 1280
        disp = cv2.resize(frame, (dw, int(h * dw / w)))
        dh   = disp.shape[0]
        sx2  = dw / w
        sy2  = dh / h
        disp_locs = [(int(t * sy2), int(r * sx2), int(b * sy2), int(l * sx2))
                     for t, r, b, l in last_locs]

        # Traektoriyani display koordinataga o'tkazish
        disp_trails = {}
        for name, pts in last_trails.items():
            disp_trails[name] = [[int(x * sx2), int(y * sy2)] for x, y in pts]

        with _meta_lock:
            _meta = {
                "locs":       [list(loc) for loc in disp_locs],
                "names":      last_names,
                "fps":        fps_val,
                "w":          dw,
                "h":          dh,
                "trails":     disp_trails,
                "face_count": len(faces.encodings),
                "line1_y":    int(dh * config.LINE_1_Y_FRAC),
            }

        _, jpeg = cv2.imencode(".jpg", disp, [cv2.IMWRITE_JPEG_QUALITY, 92])
        with _mjpeg_lock:
            _mjpeg_frame = jpeg.tobytes()

    if cap:
        cap.release()
    log.info("Servis to'xtadi.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("Kutilmagan xatolik: %s", exc)
        sys.exit(1)
