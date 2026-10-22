"""Learning assessments share CRM identities and the existing SPACE wallet."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from ..database import Base

class AcademyTopic(Base):
    __tablename__ = 'minar_academy_topics'
    id = Column(Integer, primary_key=True)
    slug = Column(String(100), unique=True, nullable=False)
    course = Column(String(80), nullable=False)
    title = Column(String(250), nullable=False)
    data = Column(Text, nullable=False)
    published = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class AcademyAssignment(Base):
    __tablename__ = 'minar_academy_assignments'
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey('minar_academy_topics.id'), nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'))
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(250), nullable=False)
    count = Column(Integer, nullable=False, default=10)
    minutes = Column(Integer, nullable=False, default=15)
    max_attempts = Column(Integer, nullable=False, default=2)
    starts_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    due_at = Column(DateTime, nullable=False)
    public_token = Column(String(100), unique=True)
    active = Column(Boolean, nullable=False, default=True)

class AcademyAttempt(Base):
    __tablename__ = 'minar_academy_attempts'
    id = Column(String(40), primary_key=True)
    assignment_id = Column(Integer, ForeignKey('minar_academy_assignments.id'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('minar_accounts.id'), index=True)
    guest_name = Column(String(120))
    guest_phone = Column(String(30))
    guest_key = Column(String(64))
    language = Column(String(2), nullable=False, default='uz')
    snapshot = Column(Text, nullable=False)
    answers = Column(Text, nullable=False, default='{}')
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    score = Column(Integer)
    warnings = Column(Integer, nullable=False, default=0)
    lead_id = Column(Integer)

class AcademyPractice(Base):
    __tablename__ = 'minar_academy_practice'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('minar_accounts.id'), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey('minar_academy_topics.id'), nullable=False)
    question_id = Column(String(100), nullable=False)
    snapshot = Column(Text, nullable=False)
    streak = Column(Integer, nullable=False, default=0)
    resolved_at = Column(DateTime)
    rewarded = Column(Boolean, nullable=False, default=False)
    last_answer_at = Column(DateTime)
    __table_args__ = (UniqueConstraint('account_id','topic_id','question_id',name='uq_academy_practice'),)

class AcademyBonus(Base):
    __tablename__ = 'minar_academy_bonus'
    id = Column(String(40), primary_key=True)
    account_id = Column(Integer, ForeignKey('minar_accounts.id'), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey('minar_academy_topics.id'), nullable=False)
    question_id = Column(String(100), nullable=False)
    day = Column(String(10), nullable=False)
    snapshot = Column(Text, nullable=False)
    correct = Column(Boolean)
    answered_at = Column(DateTime)
    __table_args__ = (UniqueConstraint('account_id','day','question_id',name='uq_academy_bonus'),)

class AcademyNotice(Base):
    __tablename__ = 'minar_academy_notices'
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey('minar_academy_assignments.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('minar_accounts.id'), nullable=False)
    kind = Column(String(20), nullable=False)
    __table_args__ = (UniqueConstraint('assignment_id','account_id','kind',name='uq_academy_notice'),)
