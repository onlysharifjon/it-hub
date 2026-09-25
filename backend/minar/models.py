"""Minar Space jadvallari. Barcha nomlar `minar_` bilan boshlanadi (CRM jadvallari bilan aralashmasin)."""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)

from ..database import Base


class MinarAccount(Base):
    """O'quvchining Minar Space akkaunti (CRM `students` bilan 1:1)."""
    __tablename__ = "minar_accounts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, unique=True)
    login_id = Column(String(20), nullable=False, unique=True, index=True)   # "MA0042" (katta harf)
    password_hash = Column(String(255), nullable=False)
    course = Column(String(20), nullable=False, default="HTML")              # HTML | CSS | JavaScript
    character = Column(String(10), nullable=False, default="robo")           # robo | foxy | drako
    equipment = Column(Text, nullable=False, default="{}")                   # {"hat": "cap", ...} JSON
    xp = Column(Integer, nullable=False, default=0)
    streak = Column(Integer, nullable=False, default=0)
    last_login = Column(String(10), nullable=True)                           # YYYY-MM-DD (Toshkent)
    is_active = Column(Boolean, nullable=False, default=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)


class MinarSession(Base):
    __tablename__ = "minar_sessions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("minar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MinarLedger(Base):
    """Ilova ichida topilgan/sarflangan coinlar. Uniqueness: (account_id, ref_key)."""
    __tablename__ = "minar_ledger"
    __table_args__ = (UniqueConstraint("account_id", "ref_key", name="uq_minar_ledger_ref"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("minar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    ref_key = Column(String(120), nullable=False)      # checkin:DATE | game:ID | lesson:COURSE-N | quest:DATE:Q | purchase:REQ
    kind = Column(String(12), nullable=False)          # checkin | game | lesson | quest | purchase
    title = Column(String(200), nullable=False)
    amount = Column(Integer, nullable=False)
    local_date = Column(String(10), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MinarResult(Base):
    __tablename__ = "minar_results"
    __table_args__ = (UniqueConstraint("account_id", "result_id", name="uq_minar_result"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("minar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    result_id = Column(String(64), nullable=False)
    game = Column(String(12), nullable=False)
    payload = Column(Text, nullable=False)             # tekshirilgan maydonlar (JSON)
    award = Column(Integer, nullable=False, default=0)
    xp = Column(Integer, nullable=False, default=0)
    local_date = Column(String(10), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MinarLesson(Base):
    __tablename__ = "minar_lessons"
    __table_args__ = (UniqueConstraint("account_id", "course", "lesson_index", name="uq_minar_lesson"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("minar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    course = Column(String(20), nullable=False)
    lesson_index = Column(Integer, nullable=False)
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MinarQuest(Base):
    __tablename__ = "minar_quests"
    __table_args__ = (UniqueConstraint("account_id", "local_date", "quest", name="uq_minar_quest"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("minar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    local_date = Column(String(10), nullable=False)
    quest = Column(String(12), nullable=False)
    claimed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MinarPurchase(Base):
    __tablename__ = "minar_purchases"
    __table_args__ = (UniqueConstraint("account_id", "request_id", name="uq_minar_purchase_req"),)

    id = Column(String(36), primary_key=True)          # buyurtma ID (uuid)
    account_id = Column(Integer, ForeignKey("minar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id = Column(String(64), nullable=False)    # client `requestId` (idempotentlik)
    product_id = Column(String(30), nullable=False)
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)
    status = Column(String(12), nullable=False)        # hero: delivered | shop: pending -> ready -> collected
    local_date = Column(String(10), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class MinarBattle(Base):
    __tablename__ = "minar_battles"

    id = Column(Integer, primary_key=True)
    code = Column(String(12), nullable=False, unique=True, index=True)
    room_id = Column(String(36), nullable=False, unique=True)
    mode = Column(String(10), nullable=False)          # typing | quiz
    course = Column(String(20), nullable=False)
    host_account_id = Column(Integer, ForeignKey("minar_accounts.id"), nullable=False, index=True)
    guest_account_id = Column(Integer, ForeignKey("minar_accounts.id"), nullable=True)
    status = Column(String(12), nullable=False, default="waiting")   # waiting | ready | playing | finished | abandoned
    match_id = Column(String(36), nullable=True, index=True)
    winner_account_id = Column(Integer, ForeignKey("minar_accounts.id"), nullable=True)
    draw = Column(Boolean, nullable=False, default=False)
    host_score = Column(Integer, nullable=True)
    guest_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
