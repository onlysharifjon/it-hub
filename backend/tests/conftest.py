"""
Test configuration: SQLite in-memory DB, overrides FastAPI dependencies.
"""
import atexit
import os
import shutil
import tempfile

# backend import qilinishidan OLDIN: har test sessiyasi o'zining vaqtinchalik
# bazasi va uploads papkasini oladi — .env dagi production DATABASE_URL/UPLOAD_DIR
# hech qachon ishlatilmaydi (load_dotenv mavjud env qiymatlarini almashtirmaydi),
# parallel ishga tushgan sessiyalar ham bir-biriga xalaqit bermaydi.
_TMP = tempfile.mkdtemp(prefix="ithub-tests-")
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ["RATE_LIMIT_ENABLED"] = "true"

# bcrypt'ning standart 12 raundi har parol uchun ~0.3 s — testlarda 4 raund
# yetarli (to'plam sekinligining asosiy sababi shu edi).
import bcrypt as _bcrypt_mod
_orig_gensalt = _bcrypt_mod.gensalt
_bcrypt_mod.gensalt = lambda rounds=4, prefix=b"2b": _orig_gensalt(rounds=4, prefix=prefix)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from backend.database import Base, engine, get_db
from backend.main import app, hash_password
from backend.models import User, Lesson, UserRole

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@event.listens_for(engine, "connect")
def _fast_sqlite(dbapi_conn, _):
    # Test bazasi vaqtinchalik — diskka fsync kutish shart emas.
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA synchronous=OFF")
    cur.execute("PRAGMA journal_mode=MEMORY")
    cur.close()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def setup_db():
    """Har test toza bazadan boshlanadi. Sxemani har safar yaratib-o'chirish
    (55 jadval) test boshiga ~20 s edi — endi faqat qatorlar o'chiriladi."""
    yield
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        if conn.exec_driver_sql(
                "SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").first():
            conn.exec_driver_sql("DELETE FROM sqlite_sequence")


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Login rate-limiterlar modul-global — testlar bir xil IP'dan kelgani uchun
    har testdan oldin tozalanadi (aks holda 429 ga uriladi)."""
    from backend import security as _security
    _security._hits.clear()
    yield


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(db, username: str, password: str, role: UserRole) -> User:
    from datetime import datetime
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_lesson(db, lesson_number: int = 1, category: str = 'foundation') -> Lesson:
    lesson = Lesson(
        category=category,
        lesson_number=lesson_number,
        title=f"Test dars {lesson_number}",
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


def _login(client, username: str, password: str) -> str:
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def metodist_user(db):
    return _create_user(db, "metodist", "metodist123", UserRole.metodist)


@pytest.fixture
def teacher_user(db):
    return _create_user(db, "teacher", "teacher123", UserRole.teacher)


@pytest.fixture
def metodist_token(client, metodist_user):
    return _login(client, "metodist", "metodist123")


@pytest.fixture
def teacher_token(client, teacher_user):
    return _login(client, "teacher", "teacher123")


@pytest.fixture
def sample_lesson(db):
    return _create_lesson(db, lesson_number=1)