"""
500+ talaba, 10 guruh, 1 yillik to'lovlar va test foydalanuvchilar seed qiluvchi skript.
Ishga tushirish: python -m backend.seed_test_data
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

import bcrypt as _bcrypt
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import User, UserRole, Student, Group, GroupStudent, Payment

# ── O'zbek ismlari ────────────────────────────────────────────────────────────

MALE_NAMES = [
    "Abdulloh", "Akbar", "Alisher", "Amir", "Anvar", "Asliddin", "Aziz", "Azizjon",
    "Bobur", "Behruz", "Doniyor", "Eldor", "Elmurod", "Farhodjon", "Firdavs",
    "Husayn", "Ibrohim", "Islom", "Jasur", "Javlon", "Kamol", "Komiljon",
    "Lochinbek", "Mansur", "Mirzo", "Muhammadali", "Murod", "Muzaffar",
    "Nodir", "Nurbek", "Odil", "Otabek", "Parviz", "Qodir", "Ravshan",
    "Rustam", "Saidakbar", "Sardor", "Sarvar", "Sherzod", "Shohruh",
    "Sirojiddin", "Temur", "Tohir", "Ulugbek", "Umid", "Utkir",
    "Vohid", "Xurshid", "Yorqin", "Zafar", "Zubaydullo",
]

FEMALE_NAMES = [
    "Adolat", "Aziza", "Barno", "Dildora", "Dilorom", "Feruza", "Gavhar",
    "Gulnora", "Gulzor", "Hilola", "Hulkar", "Kamola", "Lola", "Lobar",
    "Madina", "Malika", "Maftuna", "Mavluda", "Mohira", "Muazzam",
    "Munira", "Muslima", "Nargiza", "Nasiba", "Nilufar", "Nodira",
    "Noila", "Oydin", "Oysha", "Ozoda", "Parizod", "Rohila",
    "Sabina", "Sarvinoz", "Sabohat", "Sevinch", "Shahlo", "Shahnoza",
    "Shirin", "Umida", "Xurmo", "Yulduz", "Zulfiya", "Zuhra",
]

SURNAMES = [
    "Abdullayev", "Ahmedov", "Aliyev", "Askarov", "Azimov",
    "Baxtiyorov", "Botirov", "Ergashev", "Eshmatov", "Hasanov",
    "Holiqov", "Ibragimov", "Ismoilov", "Islomov", "Jurayev",
    "Karimov", "Komilov", "Mahmudov", "Mamatov", "Mirzayev",
    "Muhammadiyev", "Murodov", "Nazarov", "Normatov", "Ortiqov",
    "Pulatov", "Qodirov", "Qosimov", "Rahimov", "Raximov",
    "Razzaqov", "Rustamov", "Saidov", "Salimov", "Sharipov",
    "Sultanov", "Toshmatov", "Tursunov", "Umarov", "Usmonov",
    "Yusupov", "Zokirov", "Ziyodullayev", "Xasanov", "Xolmatov",
]

FEMALE_SURNAMES = [s + "a" if not s.endswith("a") else s for s in SURNAMES]

COURSES = [
    "Python dasturlash", "Web dasturlash", "Mobile ilovalar",
    "Grafik dizayn", "UI/UX dizayn", "Ingliz tili (A1-A2)",
    "Ingliz tili (B1-B2)", "Matematika (7-9 sinf)", "Matematika (10-11 sinf)",
    "Robototexnika",
]

SCHEDULES = [
    "Du,Cho,Ju 09:00", "Du,Cho,Ju 11:00", "Du,Cho,Ju 14:00",
    "Du,Cho,Ju 16:00", "Se,Pay,Sha 10:00", "Se,Pay,Sha 14:00",
    "Se,Pay,Sha 17:00", "Du,Cho,Ju 18:00", "Se,Pay,Sha 19:00",
    "Shanba,Yakshanba 10:00",
]

PRICES = [500_000, 600_000, 700_000, 800_000, 1_000_000, 1_200_000]


def _hash(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def random_phone() -> str:
    operators = ["90", "91", "93", "94", "95", "97", "98", "99", "33", "50", "88"]
    op = random.choice(operators)
    num = random.randint(1_000_000, 9_999_999)
    return f"+998{op}{num}"


def random_name(gender: str) -> tuple[str, str]:
    if gender == "male":
        first = random.choice(MALE_NAMES)
        last = random.choice(SURNAMES)
    else:
        first = random.choice(FEMALE_NAMES)
        last = random.choice(FEMALE_SURNAMES)
    return first, last


def seed_test_data():
    db: Session = SessionLocal()
    try:
        print("=" * 50)
        print("IT Hub — Test ma'lumotlar seed qilinmoqda...")
        print("=" * 50)

        # ── 1. Test foydalanuvchilar ───────────────────────────────────────────
        print("\n[1/5] Foydalanuvchilar...")

        test_users = [
            {"username": "admin",     "password": "Admin@2026",    "role": UserRole.admin,    "full_name": "Shamsiddin Karimov"},
            {"username": "metodist",  "password": "Metodist@2026", "role": UserRole.metodist, "full_name": "Dilnoza Hasanova"},
            {"username": "teacher1",  "password": "Teacher@2026",  "role": UserRole.teacher,  "full_name": "Sarvar Toshmatov"},
            {"username": "teacher2",  "password": "Teacher@2026",  "role": UserRole.teacher,  "full_name": "Malika Yusupova"},
            {"username": "teacher3",  "password": "Teacher@2026",  "role": UserRole.teacher,  "full_name": "Jasur Rahimov"},
            {"username": "teacher4",  "password": "Teacher@2026",  "role": UserRole.teacher,  "full_name": "Nodira Ergasheva"},
            {"username": "teacher5",  "password": "Teacher@2026",  "role": UserRole.teacher,  "full_name": "Otabek Mirzayev"},
        ]

        teacher_ids = []
        for u in test_users:
            existing = db.query(User).filter(User.username == u["username"]).first()
            if not existing:
                user = User(
                    username=u["username"],
                    hashed_password=_hash(u["password"]),
                    role=u["role"].value,
                    full_name=u["full_name"],
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                db.add(user)
                db.flush()
                if u["role"] == UserRole.teacher:
                    teacher_ids.append(user.id)
            else:
                if u["role"] == UserRole.teacher:
                    teacher_ids.append(existing.id)
                # Update full_name if missing
                if not existing.full_name:
                    existing.full_name = u["full_name"]

        db.commit()
        print(f"   ✓ {len(test_users)} ta foydalanuvchi tayyor")

        # ── 2. 500 ta talaba ──────────────────────────────────────────────────
        print("\n[2/5] 500 ta talaba yaratilmoqda...")

        existing_count = db.query(Student).count()
        students_to_create = max(0, 500 - existing_count)

        new_students = []
        for i in range(students_to_create):
            gender = random.choice(["male", "female"])
            first, last = random_name(gender)
            full_name = f"{last} {first}"
            has_phone2 = random.random() > 0.5
            has_telegram = random.random() > 0.6
            s = Student(
                full_name=full_name,
                phone1=random_phone(),
                phone2=random_phone() if has_phone2 else None,
                telegram_id=f"{first.lower()}{random.randint(10,99)}" if has_telegram else None,
                is_active=random.random() > 0.1,  # 90% faol
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)),
            )
            new_students.append(s)

        if new_students:
            db.add_all(new_students)
            db.commit()

        all_students = db.query(Student).all()
        print(f"   ✓ Jami {len(all_students)} ta talaba tayyor")

        # ── 3. 10 ta guruh ────────────────────────────────────────────────────
        print("\n[3/5] Guruhlar yaratilmoqda...")

        existing_groups = db.query(Group).count()
        groups = []

        if existing_groups < 10:
            for i in range(10 - existing_groups):
                course = COURSES[i % len(COURSES)]
                group_num = i + existing_groups + 1
                teacher_id = random.choice(teacher_ids) if teacher_ids else None
                g = Group(
                    name=f"{course} — {group_num}-guruh",
                    teacher_id=teacher_id,
                    course_price=Decimal(random.choice(PRICES)),
                    schedule=SCHEDULES[i % len(SCHEDULES)],
                    start_date=datetime.utcnow() - timedelta(days=random.randint(30, 300)),
                    is_active=i < 8,  # 8 ta faol, 2 ta yopiq
                    created_at=datetime.utcnow() - timedelta(days=random.randint(30, 300)),
                )
                db.add(g)
                groups.append(g)
            db.commit()

        all_groups = db.query(Group).all()
        print(f"   ✓ Jami {len(all_groups)} ta guruh tayyor")

        # ── 4. Talabalarni guruhlarga biriktirish ─────────────────────────────
        print("\n[4/5] Talabalar guruhlarga biriktrilmoqda...")

        all_students = db.query(Student).filter(Student.is_active == True).all()
        added_count = 0

        for g in all_groups:
            existing_members = {gs.student_id for gs in db.query(GroupStudent).filter(GroupStudent.group_id == g.id).all()}
            target = random.randint(30, 60)
            candidates = [s for s in all_students if s.id not in existing_members]
            selected = random.sample(candidates, min(target, len(candidates)))

            for s in selected:
                gs = GroupStudent(
                    group_id=g.id,
                    student_id=s.id,
                    joined_at=datetime.utcnow() - timedelta(days=random.randint(0, 200)),
                )
                db.add(gs)
                added_count += 1

        db.commit()
        print(f"   ✓ {added_count} ta guruh-talaba bog'liq yaratildi")

        # ── 5. 1 yillik to'lovlar ─────────────────────────────────────────────
        print("\n[5/5] 1 yillik to'lov tarixi yaratilmoqda...")

        existing_payments = db.query(Payment).count()
        if existing_payments == 0:
            now = datetime.utcnow()
            payments = []

            for g in all_groups:
                members = db.query(GroupStudent).filter(GroupStudent.group_id == g.id).all()
                price = float(g.course_price)

                for month_offset in range(12):
                    pay_date = now - timedelta(days=30 * month_offset)
                    m = pay_date.month
                    y = pay_date.year

                    # Har oyda 75-95% to'laydi
                    paying_members = random.sample(members, int(len(members) * random.uniform(0.75, 0.95)))

                    for gs in paying_members:
                        # Ba'zi vaqt chegirma (80-100%)
                        discount = random.choice([1.0, 1.0, 1.0, 0.9, 0.8])
                        amount = round(price * discount)

                        p = Payment(
                            student_id=gs.student_id,
                            group_id=g.id,
                            amount=Decimal(amount),
                            month=m,
                            year=y,
                            paid_at=pay_date - timedelta(days=random.randint(0, 25)),
                            notes=None,
                        )
                        payments.append(p)

                # Batch insert
                if len(payments) >= 500:
                    db.add_all(payments)
                    db.commit()
                    payments = []

            if payments:
                db.add_all(payments)
                db.commit()

        total_payments = db.query(Payment).count()
        print(f"   ✓ Jami {total_payments} ta to'lov yozuvi yaratildi")

        # ── Natija ────────────────────────────────────────────────────────────
        print("\n" + "=" * 50)
        print("✅  SEED MUVAFFAQIYATLI YAKUNLANDI!")
        print("=" * 50)
        print(f"  👤 Foydalanuvchilar : {db.query(User).count()}")
        print(f"  👨‍🎓 Talabalar        : {db.query(Student).count()}")
        print(f"  👥 Guruhlar         : {db.query(Group).count()}")
        print(f"  💳 To'lovlar        : {db.query(Payment).count()}")
        print()
        print("  Login ma'lumotlari:")
        print("  ┌─────────────┬─────────────────┬───────────────┐")
        print("  │ Username    │ Parol           │ Rol           │")
        print("  ├─────────────┼─────────────────┼───────────────┤")
        print("  │ admin       │ Admin@2026      │ Admin         │")
        print("  │ metodist    │ Metodist@2026   │ Metodist      │")
        print("  │ teacher1..5 │ Teacher@2026    │ O'qituvchi    │")
        print("  └─────────────┴─────────────────┴───────────────┘")
        print()

    except Exception as e:
        db.rollback()
        print(f"\nXATOLIK: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_data()
