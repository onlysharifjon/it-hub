"""faces/ katalogidan o'quvchilarning yuz encodinglarini yuklaydi va keshlaydi."""
import os
import pickle
import logging

import numpy as np
import face_recognition

import config

log = logging.getLogger("camera.faces")


class FaceDB:
    """Ma'lum yuzlar to'plami: encodinglar va ularga mos student_id lar."""

    def __init__(self):
        self.encodings: list[np.ndarray] = []
        self.student_ids: list[int] = []

    def load(self) -> None:
        """Keshdan yoki rasm fayllaridan encodinglarni yuklaydi."""
        if self._load_cache():
            log.info("Kesh yuklandi: %d ta yuz encodingi", len(self.encodings))
            return
        self._build_from_images()
        self._save_cache()

    def _build_from_images(self) -> None:
        faces_dir = config.FACES_DIR
        if not os.path.isdir(faces_dir):
            log.warning("faces/ katalogi topilmadi: %s", faces_dir)
            return

        for entry in sorted(os.listdir(faces_dir)):
            student_path = os.path.join(faces_dir, entry)
            if not os.path.isdir(student_path):
                continue
            # Katalog nomi = student_id (masalan "42" yoki "42_Ali").
            try:
                student_id = int(entry.split("_")[0])
            except ValueError:
                log.warning("Katalog nomidan student_id ajratilmadi: %s", entry)
                continue

            count = 0
            for fname in os.listdir(student_path):
                if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img_path = os.path.join(student_path, fname)
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
                self.student_ids.append(student_id)
                count += 1
            log.info("student_id=%s uchun %d ta yuz yuklandi", student_id, count)

        log.info("Jami %d ta encoding yuklandi", len(self.encodings))

    def _load_cache(self) -> bool:
        path = config.ENCODINGS_CACHE
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.encodings = data["encodings"]
            self.student_ids = data["student_ids"]
            return len(self.encodings) > 0
        except Exception as exc:
            log.warning("Keshni o'qib bo'lmadi: %s", exc)
            return False

    def _save_cache(self) -> None:
        try:
            with open(config.ENCODINGS_CACHE, "wb") as f:
                pickle.dump({"encodings": self.encodings, "student_ids": self.student_ids}, f)
        except Exception as exc:
            log.warning("Keshni saqlab bo'lmadi: %s", exc)

    def match(self, encoding: np.ndarray) -> int | None:
        """Berilgan encodingga mos student_id ni qaytaradi yoki None."""
        if not self.encodings:
            return None
        distances = face_recognition.face_distance(self.encodings, encoding)
        best = int(np.argmin(distances))
        if distances[best] <= config.RECOGNITION_TOLERANCE:
            return self.student_ids[best]
        return None
