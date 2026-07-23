"""
O'quvchilar va xodimlarning yuz encodinglarini yuklaydi va keshlaydi.

Papka tuzilmasi:
  faces/students/{id}/*.jpg  — o'quvchilar
  faces/staff/{id}/*.jpg     — xodimlar (users)
"""
import os
import pickle
import logging

import numpy as np
import face_recognition

import config

log = logging.getLogger("camera.faces")


class FaceDB:
    """Ma'lum yuzlar to'plami: encodinglar va ularga mos shaxs ma'lumotlari."""

    def __init__(self):
        self.encodings: list[np.ndarray] = []
        # Har bir encoding uchun {'id': int, 'type': 'student'|'staff'}
        self.persons: list[dict] = []

    def load(self) -> None:
        if self._load_cache():
            log.info("Kesh yuklandi: %d ta yuz encodingi", len(self.encodings))
            return
        self._build_from_images()
        self._save_cache()

    def reload(self) -> None:
        """Keshni o'chirib, rasmlardan encodinglarni qayta yuklaydi."""
        cache_path = config.ENCODINGS_CACHE
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception:
                pass
        self.encodings = []
        self.persons = []
        self._build_from_images()
        self._save_cache()
        log.info("Encodinglar qayta yuklandi: %d ta yuz", len(self.encodings))

    def match(self, encoding: np.ndarray) -> tuple:
        """(person_dict | None, distance) qaytaradi."""
        if not self.encodings:
            return None, 1.0
        distances = face_recognition.face_distance(self.encodings, encoding)
        best = int(np.argmin(distances))
        dist = float(distances[best])
        if dist <= config.RECOGNITION_TOLERANCE:
            return self.persons[best], dist
        return None, dist

    # ── private ───────────────────────────────────────────────────────────────

    def _build_from_images(self) -> None:
        self._scan_dir(os.path.join(config.FACES_DIR, "students"), "student")
        self._scan_dir(os.path.join(config.FACES_DIR, "staff"),    "staff")
        log.info("Jami %d ta encoding yuklandi", len(self.encodings))

    def _scan_dir(self, base_dir: str, person_type: str) -> None:
        if not os.path.isdir(base_dir):
            return
        for entry in sorted(os.listdir(base_dir)):
            person_path = os.path.join(base_dir, entry)
            if not os.path.isdir(person_path):
                continue
            try:
                person_id = int(entry.split("_")[0])
            except ValueError:
                log.warning("Katalog nomidan ID ajratilmadi: %s", entry)
                continue

            count = 0
            for fname in os.listdir(person_path):
                if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img_path = os.path.join(person_path, fname)
                try:
                    image = face_recognition.load_image_file(img_path)
                    encs = face_recognition.face_encodings(image)
                except Exception as exc:
                    log.warning("Rasmni o'qib bo'lmadi %s: %s", img_path, exc)
                    continue
                if not encs:
                    log.warning("Yuz topilmadi: %s", img_path)
                    continue
                self.encodings.append(encs[0])
                self.persons.append({"id": person_id, "type": person_type})
                count += 1
            if count:
                log.info("%s id=%s uchun %d ta yuz yuklandi", person_type, person_id, count)

    def _load_cache(self) -> bool:
        path = config.ENCODINGS_CACHE
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.encodings = data["encodings"]
            self.persons = data.get("persons", [])
            # Eski format (student_ids) bilan muvofiqlik
            if not self.persons and "student_ids" in data:
                self.persons = [{"id": sid, "type": "student"} for sid in data["student_ids"]]
            return len(self.encodings) > 0
        except Exception as exc:
            log.warning("Keshni o'qib bo'lmadi: %s", exc)
            return False

    def _save_cache(self) -> None:
        try:
            with open(config.ENCODINGS_CACHE, "wb") as f:
                pickle.dump({"encodings": self.encodings, "persons": self.persons}, f)
        except Exception as exc:
            log.warning("Keshni saqlab bo'lmadi: %s", exc)
