"""
Test configuration: SQLite in-memory DB, overrides FastAPI dependencies.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app, hash_password
from backend.models import User, Lesson, UserRole

TEST_DB_URL = "sqlite:///./test_ithub.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Login rate-limiterlar modul-global — testlar bir xil IP'dan kelgani uchun
    har testdan oldin tozalanadi (aks holda 429 ga uriladi)."""
    from backend import main as _main
    from backend import security as _security
    _main._rate_hits.clear()
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