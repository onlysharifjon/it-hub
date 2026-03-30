from datetime import datetime

import bcrypt as _bcrypt
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Lesson, User, UserRole
from backend.seed_data import LESSON_SEED_DATA


def _hash(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


# 3 ta default foydalanuvchi — har bir rol uchun bittadan
DEFAULT_USERS = [
    {"username": "admin",    "password": "Admin@2026",    "role": UserRole.admin.value},
    {"username": "metodist", "password": "Metodist@2026", "role": UserRole.metodist.value},
    {"username": "teacher",  "password": "Teacher@2026",  "role": UserRole.teacher.value},
]


def seed_users(db: Session) -> None:
    created = 0
    for u in DEFAULT_USERS:
        if not db.query(User).filter(User.username == u["username"]).first():
            db.add(User(
                username=u["username"],
                hashed_password=_hash(u["password"]),
                role=u["role"],
                is_active=True,
                created_at=datetime.utcnow(),
            ))
            created += 1
    if created:
        db.commit()
        print(f"Seeded {created} users.")
    else:
        print("Users already exist, skipping.")


def seed_database(db: Session) -> None:
    if db.query(Lesson).count():
        print("Lessons table already has data; skipping seed.")
        return
    lessons = [Lesson(**lesson) for lesson in LESSON_SEED_DATA]
    db.add_all(lessons)
    db.commit()
    print(f"Seeded {len(lessons)} lessons.")


def main() -> None:
    db = SessionLocal()
    try:
        seed_users(db)
        seed_database(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
