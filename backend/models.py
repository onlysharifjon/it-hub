import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Numeric, Table, Date, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    admin       = "admin"        # superadmin — to'liq nazorat + daromad statistika
    metodist    = "metodist"     # metodist   — dars CRUD + talabalar/guruhlar
    teacher     = "teacher"      # o'qituvchi  — faqat metodika ko'rish
    call_center = "call_center"  # call center — lidlar holati + talabalar/guruhlar
    hunter      = "hunter"       # hunter     — lid qo'shish + talabalar/guruhlar
    sales       = "sales"        # sales      — CRM lidlar + talabalar/guruhlar (moliya yo'q)
    audit       = "audit"        # audit      — xodimlarga ogohlantirish/jarima berish


class LeadStatus(str, enum.Enum):
    new       = "new"        # Yangi lid
    called    = "called"     # Qo'ng'iroq qilindi
    will_come = "will_come"  # Keladi (vaqt belgilangan)
    rejected  = "rejected"   # Rad etildi
    callback  = "callback"   # Qayta qo'ng'iroq (1 soatdan keyin)
    enrolled  = "enrolled"   # Talabaga o'tkazildi


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default=UserRole.teacher.value)
    is_active = Column(Boolean, nullable=False, default=True)
    avatar = Column(String(500), nullable=True)
    phone = Column(String(30), nullable=True)          # kontakt (ota-ona ilovasida ko'rinadi)
    telegram = Column(String(100), nullable=True)      # @username
    telegram_chat_id = Column(String(50), nullable=True)  # Telegram bot bildirishnomasi uchun chat/user ID
    face_photo_path = Column(String(500), nullable=True)  # kamera orqali davomat uchun yuz rasmi
    # Block & expiry
    blocked_reason  = Column(Text, nullable=True)         # sabab matni
    blocked_contact = Column(String(300), nullable=True)  # bog'lanish ma'lumoti
    blocked_at      = Column(DateTime, nullable=True)
    expires_at      = Column(DateTime, nullable=True)     # null = cheksiz
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    updated_lessons = relationship(
        "Lesson", back_populates="updated_by_user", foreign_keys="[Lesson.updated_by_id]"
    )
    audit_logs = relationship("AuditLog", back_populates="changed_by_user")
    teaching_groups = relationship("Group", back_populates="teacher")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, default='foundation')
    lesson_number = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    section = Column(Text, nullable=True)
    guide = Column(Text, nullable=True)
    homework = Column(Text, nullable=True)
    extra_notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (UniqueConstraint("category", "lesson_number", name="uq_lesson_category_number"),)

    updated_by_user = relationship(
        "User", back_populates="updated_lessons", foreign_keys=[updated_by_id]
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    action = Column(String(50), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    changed_by_user = relationship("User", back_populates="audit_logs")


# ── LMS Modellari ─────────────────────────────────────────────────────────────

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    total_lessons = Column(Integer, nullable=False, default=24)
    duration_months = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    groups = relationship("Group", back_populates="course")


class Tariff(Base):
    __tablename__ = "tariffs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    price = Column(Numeric(12, 2), nullable=False, default=100000)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    phone1 = Column(String(20), nullable=False)
    father_name  = Column(String(200), nullable=True)
    father_phone = Column(String(20),  nullable=True)
    mother_name  = Column(String(200), nullable=True)
    mother_phone = Column(String(20),  nullable=True)
    telegram_id  = Column(String(120), nullable=True)
    telegram_user_id = Column(String(50), nullable=True)   # bildirishnoma yuboriladigan Telegram chat/user ID
    photo = Column(String(500), nullable=True)              # o'quvchi rasmi (uploads/students/...)
    photo_path   = Column(String(500), nullable=True)       # kamera orqali davomat uchun yuz rasmi
    notes = Column(Text, nullable=True)
    advance_balance = Column(Numeric(12, 2), nullable=False, default=0)  # avans (oldindan to'lov)
    is_active = Column(Boolean, nullable=False, default=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    is_demo = Column(Boolean, nullable=False, default=False, index=True)  # hali demo darsga kelmagan, guruhga biriktirilmagan
    # Sales orqali jalb qilingan talaba — to'lov qo'shishda "Sales" tugmasi bosilsa
    # belgilanadi, LeadReferralStat.paid_count'ga faqat BIR MARTA hisoblanadi.
    sales_credited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    group_memberships = relationship("GroupStudent", back_populates="student")
    payments = relationship("Payment", back_populates="student")


STAGE_TOTAL_LESSONS = {
    'foundation': 24,   # 2 oy × 12 dars/oy
    'frontend':   72,   # 6 oy × 12 dars/oy
    'backend':    108,  # 9 oy × 12 dars/oy
}


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    stage = Column(String(20), nullable=False, default='foundation')  # foundation | frontend | backend
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    course_price = Column(Numeric(12, 2), nullable=False, default=0)
    teacher_pay_per_student = Column(Numeric(12, 2), nullable=False, default=0)
    schedule = Column(String(200), nullable=True)   # e.g. "Du,Cho,Ju 14:00"
    lesson_time = Column(String(5), nullable=True)  # dars boshlanish vaqti, masalan "14:00"
    start_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    telegram_chat_id = Column(String(50), nullable=True)   # guruhning Telegram chat ID'si (uy vazifasi boti uchun)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    course = relationship("Course", back_populates="groups")
    teacher = relationship("User", back_populates="teaching_groups")
    members = relationship("GroupStudent", back_populates="group")
    payments = relationship("Payment", back_populates="group")


class GroupStudent(Base):
    __tablename__ = "group_students"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    group = relationship("Group", back_populates="members")
    student = relationship("Student", back_populates="group_memberships")
    tariff = relationship("Tariff")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    month = Column(Integer, nullable=False)   # 1-12
    year = Column(Integer, nullable=False)
    paid_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    notes = Column(Text, nullable=True)                                   # to'lov izohi
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # kim qabul qilgan
    via_sales = Column(Boolean, nullable=False, default=False)  # "Sales" tugmasi bosilganmi (audit uchun)

    student = relationship("Student", back_populates="payments")
    group = relationship("Group", back_populates="payments")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class CameraAttendance(Base):
    __tablename__ = "camera_attendance"

    id          = Column(Integer, primary_key=True, index=True)
    student_id  = Column(Integer, ForeignKey("students.id"), nullable=True)
    staff_id    = Column(Integer, ForeignKey("users.id"),    nullable=True)
    person_type = Column(String(20), nullable=False)   # student | staff | unknown
    event_type  = Column(String(10), nullable=False)   # keldi   | ketdi
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    student = relationship("Student")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    lesson_date = Column(Date, nullable=False)
    is_present = Column(Boolean, nullable=True)

    __table_args__ = (UniqueConstraint("group_id", "student_id", "lesson_date", name="uq_attendance"),)

    group = relationship("Group")
    student = relationship("Student")


class LeadStage(Base):
    """Sozlanadigan pipeline bosqichi (Kanban ustuni)."""
    __tablename__ = "lead_stages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    slug = Column(String(80), nullable=False, unique=True, index=True)
    order = Column(Integer, nullable=False, default=0)
    color = Column(String(20), nullable=False, default="slate")   # sky/indigo/amber/emerald/red/slate/violet...
    icon = Column(String(40), nullable=False, default="circle")
    kind = Column(String(10), nullable=False, default="lead")     # lead | won | lost
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LeadSource(Base):
    """Lid manbasi (Instagram, Telegram, Walk-in...)."""
    __tablename__ = "lead_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    is_campaign = Column(Boolean, nullable=False, default=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Bu manbadan kelgan lidlar avtomatik shu xodimga (masalan reklama/SMM
    # yurituvchi sales) "taklif qilgan" sifatida bog'lanadi — Lead.referred_by_id.
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    phone = Column(String(30), nullable=False)
    course_interest = Column(String(100), nullable=True)   # foundation/frontend/backend
    status = Column(String(30), nullable=False, default=LeadStatus.new.value, index=True)  # stage.slug bilan sinxron
    stage_id = Column(Integer, ForeignKey("lead_stages.id"), nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("lead_sources.id"), nullable=True)
    callback_at = Column(DateTime, nullable=True)          # will_come yoki callback holati uchun
    notes = Column(Text, nullable=True)
    # Boy maydonlar
    date_of_birth = Column(Date, nullable=True)
    parent_phone = Column(String(30), nullable=True)
    parent2_phone = Column(String(30), nullable=True)
    interested_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    # Umumiy havza / claim
    is_shared = Column(Boolean, nullable=False, default=False, index=True)
    claimed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    claimed_at = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Manba (masalan Facebook/Instagram) qaysi sales xodimga tegishli bo'lsa,
    # lid yaratilganda o'sha manbaning referrer_id'sidan ko'chiriladi —
    # hunter/call_center keyinchalik claim/close qilsa ham o'zgarmaydi.
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # Referral paid_count'ga faqat BIR MARTA hisoblanishi uchun — bosqich
    # "To'landi"ga qaytarilib-qaytarilib o'zgartirilsa ham qayta sanalmaydi.
    referral_credited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    claimed_by = relationship("User", foreign_keys=[claimed_by_id])
    referred_by = relationship("User", foreign_keys=[referred_by_id])
    stage = relationship("LeadStage", foreign_keys=[stage_id])
    source = relationship("LeadSource", foreign_keys=[source_id])
    interested_group = relationship("Group", foreign_keys=[interested_group_id])
    activities = relationship(
        "LeadActivity", back_populates="lead",
        cascade="all, delete-orphan", order_by="LeadActivity.created_at.desc()",
    )


class LeadActivity(Base):
    """Lid tarixi (timeline) — har o'zgarish yozib boriladi."""
    __tablename__ = "lead_activities"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(40), nullable=False)   # created | stage_changed | note | call | reminder
    description = Column(Text, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    meta_json = Column(Text, nullable=True)        # qo'shimcha JSON (old/new stage...)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="activities")
    author = relationship("User", foreign_keys=[author_id])


class LeadReferralStat(Base):
    """Oylik tarix: har sales xodim (referrer) uchun qancha lid kelgani va
    qanchasi to'landi — har oy alohida qator, o'tgan oylar qayta hisoblanmaydi."""
    __tablename__ = "lead_referral_stats"
    __table_args__ = (UniqueConstraint("referrer_id", "period", name="uq_referral_stat_period"),)

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)   # "YYYY-MM"
    leads_count = Column(Integer, nullable=False, default=0)
    paid_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    referrer = relationship("User", foreign_keys=[referrer_id])


class FacebookLead(Base):
    """Facebook Lead Ads'dan Make.com orqali kelgan xom lidlar (dedup uchun alohida jadval)."""
    __tablename__ = "facebook_leads"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True, index=True)  # Facebook'da telefonsiz (faqat email) forma ham bo'lishi mumkin
    email = Column(String(200), nullable=True)
    form_name = Column(String(200), nullable=True)
    source = Column(String(30), nullable=False, default="facebook")
    created_time = Column(DateTime, nullable=True)     # Facebook'da lid yaratilgan vaqt
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)  # bizga yetib kelgan vaqt
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)  # CRM Lidlar bo'limidagi mos yozuv

    lead = relationship("Lead", foreign_keys=[lead_id])


class Reminder(Base):
    """Lidga bog'liq eslatma / vazifa (qo'ng'iroq, tashrif...)."""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_at = Column(DateTime, nullable=False, index=True)
    body = Column(Text, nullable=True)
    kind = Column(String(20), nullable=False, default="call")      # call | visit | other
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | done | dismissed
    snoozed_until = Column(DateTime, nullable=True)
    done_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    lead = relationship("Lead", foreign_keys=[lead_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class Notification(Base):
    """Foydalanuvchiga bildirishnoma (yangi lid, eslatma...)."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(String(40), nullable=False, default="new_lead")
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(200), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])


class IntakeForm(Base):
    """Ommaviy qabul formasi — tashqi havola orqali lid yig'ish."""
    __tablename__ = "intake_forms"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(60), nullable=False, unique=True, index=True)
    name = Column(String(150), nullable=False)
    title = Column(String(200), nullable=True)             # formada ko'rinadigan sarlavha
    description = Column(Text, nullable=True)
    source_id = Column(Integer, ForeignKey("lead_sources.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    submissions = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    source = relationship("LeadSource", foreign_keys=[source_id])


# ── Ota-onalar mobil ilovasi (Parent app) ────────────────────────────────────

class Parent(Base):
    """Ota-ona akkaunti — hunter/admin tomonidan yaratiladi (login + parol)."""
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    display_name = Column(String(120), nullable=True)              # "Nodira opa"
    phone = Column(String(30), nullable=False, unique=True, index=True)   # +998...
    username = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    avatar = Column(Text, nullable=True)                            # base64 rasm (mobil ilova yuklaydi)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # qaysi xodim yaratgan
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    created_by = relationship("User", foreign_keys=[created_by_id])
    children = relationship("ParentChild", back_populates="parent", cascade="all, delete-orphan")


class ParentChild(Base):
    """Ota-ona ↔ talaba bog'lami (ko'p-ko'p)."""
    __tablename__ = "parent_children"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("parent_id", "student_id", name="uq_parent_child"),)

    parent = relationship("Parent", back_populates="children")
    student = relationship("Student", foreign_keys=[student_id])


class ParentRefreshToken(Base):
    """Rotatsiyalanadigan refresh token (hashlangan holda saqlanadi)."""
    __tablename__ = "parent_refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    parent = relationship("Parent", foreign_keys=[parent_id])


class ParentNotification(Base):
    """Ota-onaga bildirishnoma (to'lov / davomat / e'lon)."""
    __tablename__ = "parent_notifications"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    type = Column(String(20), nullable=False, default="payment")   # payment | attendance | announcement
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    read_at = Column(DateTime, nullable=True)

    parent = relationship("Parent", foreign_keys=[parent_id])


class ScheduleSlot(Base):
    """Guruh dars jadvali bo'lagi — strukturaviy (kun, vaqt, xona)."""
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)          # 1 = Dushanba .. 7 = Yakshanba
    start_time = Column(String(5), nullable=False)         # "14:00"
    end_time = Column(String(5), nullable=False)           # "16:00"
    room = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    group = relationship("Group", foreign_keys=[group_id])


class ParentInvoice(Base):
    """Onlayn to'lov uchun invoys (hozircha stub — Payme/Click/Uzum keyin)."""
    __tablename__ = "parent_invoices"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    provider = Column(String(20), nullable=False, default="payme")   # payme | click | uzum
    status = Column(String(20), nullable=False, default="pending")   # pending | paid | cancelled
    checkout_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    parent = relationship("Parent", foreign_keys=[parent_id])
    student = relationship("Student", foreign_keys=[student_id])
    group = relationship("Group", foreign_keys=[group_id])


class Holiday(Base):
    """Dam olish kunlari — admin belgilaydi, yo'qlama qiladiganlarga ko'rinadi."""
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False)              # sabab/nom (masalan: "Navro'z bayrami")
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)     # start_date bilan teng bo'lishi mumkin (1 kunlik)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    created_by = relationship("User", foreign_keys=[created_by_id])


class StudentVisit(Base):
    """Talabaning markazga kelishi/ketishi — Notifications bo'limi (CRM)."""
    __tablename__ = "student_visits"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    kind = Column(String(10), nullable=False)               # arrived | left
    noted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_sent = Column(Boolean, nullable=False, default=False)
    telegram_error = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    student = relationship("Student", foreign_keys=[student_id])
    noted_by = relationship("User", foreign_keys=[noted_by_id])


class SpecialDiscount(Base):
    """Special chegirma — to'lov hisobiga real ta'sir qiladi (core_calc orqali).

    kind:
      - free_month: tanlangan oy (month/year) to'liq bepul
      - monthly:    har oy uchun amount so'm chegirma (butun kurs davomida, is_active=True bo'lsa)
    group_id NULL bo'lsa — talabaning barcha guruhlariga tegishli.
    """
    __tablename__ = "special_discounts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True, index=True)
    kind = Column(String(20), nullable=False)               # free_month | monthly
    amount = Column(Numeric(12, 2), nullable=True)          # monthly uchun: so'm/oy
    month = Column(Integer, nullable=True)                  # free_month uchun
    year = Column(Integer, nullable=True)                   # free_month uchun
    reason = Column(String(300), nullable=True)             # sabab/izoh
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    student = relationship("Student", foreign_keys=[student_id])
    group = relationship("Group", foreign_keys=[group_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class StudentVacation(Base):
    """Talabaning ta'til oralig'i — shu kunlarga to'g'ri kelgan darslar oylik
    to'lovdan chiqarib tashlanadi (core_calc orqali, kurs_narxi/12 * dars soni).
    Talabaning barcha guruhlariga tegishli (guruh-bazli emas).
    """
    __tablename__ = "student_vacations"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(300), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    student = relationship("Student", foreign_keys=[student_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class Homework(Base):
    """Uy vazifasi — o'qituvchi CRM'dan yozadi, guruh Telegram'iga yuboriladi."""
    __tablename__ = "homeworks"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)   # metodikadagi dars
    lesson_number = Column(Integer, nullable=True)          # metodika bo'yicha nechanchi dars
    lesson_title = Column(String(500), nullable=True)       # metodika bo'yicha dars nomi
    text = Column(Text, nullable=False)                     # uy vazifasi matni
    lesson_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True)                  # topshirish muddati (bo'sh — keyingi dars)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    telegram_sent = Column(Boolean, nullable=False, default=False)
    telegram_error = Column(String(500), nullable=True)

    group = relationship("Group", foreign_keys=[group_id])
    lesson = relationship("Lesson", foreign_keys=[lesson_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    submissions = relationship("HomeworkSubmission", back_populates="homework", cascade="all, delete-orphan")


class HomeworkSubmission(Base):
    """Uy vazifasining talaba bo'yicha holati — pending | submitted | graded."""
    __tablename__ = "homework_submissions"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homeworks.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")   # pending | submitted | graded
    grade = Column(Integer, nullable=True)                           # graded bo'lsa: ball
    teacher_comment = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("homework_id", "student_id", name="uq_homework_submission"),)

    homework = relationship("Homework", back_populates="submissions")
    student = relationship("Student", foreign_keys=[student_id])


class Grade(Base):
    """Imtihon/test natijasi — o'qituvchi kiritadi, ota-ona ilovada ko'radi."""
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True, index=True)
    subject = Column(String(200), nullable=False)           # masalan: "Dart Basics"
    score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False, default=100)
    exam_type = Column(String(30), nullable=False, default="exam")   # exam | test | quiz | project
    exam_date = Column(Date, nullable=False, index=True)
    comment = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    student = relationship("Student", foreign_keys=[student_id])
    group = relationship("Group", foreign_keys=[group_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class TeacherFeedback(Base):
    """O'qituvchining talaba haqidagi izohi — ota-onaga ko'rinadi.

    status — hunter/call_center kuzatuvi: new | resolved (hal qilindi) |
    no_answer (telefonga ota-onasi javob bermadi)."""
    __tablename__ = "teacher_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = Column(String(20), nullable=False, default="new", index=True)
    status_updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status_updated_at = Column(DateTime, nullable=True)

    student = relationship("Student", foreign_keys=[student_id])
    group = relationship("Group", foreign_keys=[group_id])
    teacher = relationship("User", foreign_keys=[teacher_id])
    status_updated_by = relationship("User", foreign_keys=[status_updated_by_id])


class Event(Base):
    """Akademiya tadbiri — barcha ota-onalarga ko'rinadi."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    event_date = Column(DateTime, nullable=False, index=True)
    location = Column(String(300), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    created_by = relationship("User", foreign_keys=[created_by_id])


class Certificate(Base):
    """Talaba sertifikati — PDF fayl linki bilan."""
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(300), nullable=False)             # masalan: "Foundation kursi sertifikati"
    file_url = Column(String(500), nullable=False)          # PDF havolasi
    issued_at = Column(Date, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    student = relationship("Student", foreign_keys=[student_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class CoinTransaction(Base):
    """Coin berish yozuvi — o'qituvchi talabaga rag'bat sifatida coin beradi.

    O'qituvchining oylik budjeti alohida saqlanmaydi: joriy kalendar oyda
    berilganlari yig'indisi hisoblanadi (budjet - spent = qoldiq).
    Shu sabab har oyning 1-kunida budjet o'z-o'zidan 350 ga "to'ladi" — cron kerak emas.
    """
    __tablename__ = "coin_transactions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    amount = Column(Integer, nullable=False)                # musbat butun son
    reason = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    student = relationship("Student", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[teacher_id])
    group = relationship("Group", foreign_keys=[group_id])


class DisciplineCode(Base):
    """Ichki tartib qoidalari kodeksi — bob-band bo'yicha ogohlantirish shablonlari.
    Audit shu ro'yxatdan tanlab xodimga ogohlantirish beradi."""

    __tablename__ = "discipline_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(16), nullable=False, unique=True, index=True)  # masalan "2.4"
    severity = Column(String(16), nullable=False)  # "gray" | "yellow" | "red"
    short_name = Column(String(64), nullable=False)
    text = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StaffWarning(Base):
    """Audit tomonidan xodimga berilgan ogohlantirish/jarima yozuvi — Telegram bot
    orqali xodimga xabar sifatida yetkaziladi (bot faqat vositachi)."""

    __tablename__ = "staff_warnings"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    discipline_code_id = Column(Integer, ForeignKey("discipline_codes.id"), nullable=True)
    code = Column(String(16), nullable=True)         # nusxa — kodeks keyin o'zgarsa ham tarix saqlansin
    severity = Column(String(16), nullable=False)    # "gray" | "yellow" | "red"
    reason = Column(Text, nullable=False)             # nusxa — to'liq qoida matni
    photo_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    notified_at = Column(DateTime, nullable=True)     # botga muvaffaqiyatli yetkazilgan payt
    notify_error = Column(Text, nullable=True)        # yetkazib bo'lmasa sabab (qayta yuborish uchun)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    staff = relationship("User", foreign_keys=[staff_id])
    issued_by = relationship("User", foreign_keys=[issued_by_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])
    discipline_code = relationship("DisciplineCode")
