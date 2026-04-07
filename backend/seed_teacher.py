"""
teacher1 (Sarvar Toshmatov) uchun test data:
- 10 guruh (foundation x3, frontend x4, backend x3)
- 120 talaba (har guruhga 12 ta)
- Aprel 2026 uchun davomat (random)
"""
import random
from datetime import date, datetime, timedelta

from backend.database import SessionLocal
from backend.models import (
    Attendance, Group, GroupStudent, Student, Tariff, User, UserRole
)


FIRST_NAMES = [
    "Asilbek", "Bobur", "Doniyor", "Eldor", "Farrux",
    "Jahongir", "Kamol", "Lochinbek", "Mansur", "Nodir",
    "Otabek", "Parviz", "Qodir", "Rustam", "Sanjar",
    "Timur", "Ulugbek", "Vohid", "Xurshid", "Zafar",
    "Aziza", "Barno", "Dilnoza", "Feruza", "Gulnora",
    "Hulkar", "Iroda", "Kamola", "Lobar", "Mavluda",
    "Nargiza", "Oydin", "Parizod", "Robiya", "Sarvinoz",
    "Tabassum", "Umida", "Vazira", "Xilola", "Zulfiya",
]

LAST_NAMES = [
    "Toshmatov", "Xasanov", "Yusupov", "Karimov", "Rahimov",
    "Mirzayev", "Nazarov", "Holmatov", "Ergashev", "Sultanov",
    "Abdullayev", "Botirov", "Choriyev", "Davlatov", "Eshmatov",
    "G'aniyev", "Hamidov", "Ismoilov", "Jo'rayev", "Komilов",
]

SCHEDULES = [
    "Du, Chor, Ju 09:00",
    "Du, Chor, Ju 11:00",
    "Du, Chor, Ju 14:00",
    "Du, Chor, Ju 16:00",
    "Se, Pay, Shan 10:00",
    "Se, Pay, Shan 13:00",
    "Se, Pay, Shan 15:00",
    "Se, Pay, Shan 17:00",
    "Du, Chor 18:00",
    "Se, Pay 18:00",
]

GROUPS_DEF = [
    {"name": "Foundation-1",  "stage": "foundation", "start": date(2026, 1, 5)},
    {"name": "Foundation-2",  "stage": "foundation", "start": date(2026, 2, 3)},
    {"name": "Foundation-3",  "stage": "foundation", "start": date(2026, 3, 3)},
    {"name": "Frontend-1",    "stage": "frontend",   "start": date(2025, 10, 6)},
    {"name": "Frontend-2",    "stage": "frontend",   "start": date(2025, 11, 4)},
    {"name": "Frontend-3",    "stage": "frontend",   "start": date(2026, 1, 7)},
    {"name": "Frontend-4",    "stage": "frontend",   "start": date(2026, 2, 10)},
    {"name": "Backend-1",     "stage": "backend",    "start": date(2025, 7, 1)},
    {"name": "Backend-2",     "stage": "backend",    "start": date(2025, 9, 2)},
    {"name": "Backend-3",     "stage": "backend",    "start": date(2025, 11, 4)},
]

# Aprel 2026 dars kunlari (schedule ga mos)
APRIL_DATES_ODD  = [date(2026, 4, d) for d in [1,3,5,8,10,12,15,17,19,22,24,26]]   # Se,Pay,Shan
APRIL_DATES_EVEN = [date(2026, 4, d) for d in [2,4,7,9,11,14,16,18,21,23,25,28]]   # Du,Chor,Ju


def run():
    db = SessionLocal()
    try:
        # 1. teacher1 ni top
        teacher = db.query(User).filter(User.username == "teacher1").first()
        if not teacher:
            print("ERROR: teacher1 topilmadi. Avval seed_users ishga tushiring.")
            return
        print(f"Teacher: {teacher.full_name} (id={teacher.id})")

        # 2. Tarif (mavjud bo'lsa ishlatamiz, yo'q bo'lsa yaratamiz)
        tariff = db.query(Tariff).filter(Tariff.is_active == True).first()
        if not tariff:
            tariff = Tariff(name="Standart", price=600000, is_active=True)
            db.add(tariff)
            db.commit()
            db.refresh(tariff)
            print(f"Tariff yaratildi: {tariff.name}")
        else:
            print(f"Mavjud tariff ishlatiladi: {tariff.name}")

        # 3. Guruhlarni yaratish (allaqachon borlarini o'tkazib yuboramiz)
        created_groups = []
        for i, gdef in enumerate(GROUPS_DEF):
            existing = db.query(Group).filter(
                Group.name == gdef["name"],
                Group.teacher_id == teacher.id,
            ).first()
            if existing:
                print(f"  Guruh mavjud: {gdef['name']}")
                created_groups.append(existing)
                continue

            grp = Group(
                name=gdef["name"],
                stage=gdef["stage"],
                teacher_id=teacher.id,
                course_price=600000,
                teacher_pay_per_student=50000,
                schedule=SCHEDULES[i],
                start_date=datetime.combine(gdef["start"], datetime.min.time()),
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(grp)
            db.flush()
            created_groups.append(grp)
            print(f"  Guruh yaratildi: {grp.name} ({grp.stage})")
        db.commit()

        # 4. 120 talaba yaratish va guruhlarga bo'lish (12 ta / guruh)
        random.seed(42)
        used_names = set()
        total_students = 0
        total_enrolled = 0
        total_attendance = 0

        for grp_idx, grp in enumerate(created_groups):
            # Guruhda allaqachon nechta talaba bor?
            existing_count = db.query(GroupStudent).filter(GroupStudent.group_id == grp.id).count()
            needed = 12 - existing_count
            if needed <= 0:
                print(f"  {grp.name}: talabalar to'liq ({existing_count}/12)")
                continue

            new_students = []
            for _ in range(needed):
                # Noyob ism yaratish
                for attempt in range(100):
                    fn = random.choice(FIRST_NAMES)
                    ln = random.choice(LAST_NAMES)
                    full = f"{ln} {fn}"
                    if full not in used_names:
                        used_names.add(full)
                        break

                phone_suffix = random.randint(1000000, 9999999)
                student = Student(
                    full_name=full,
                    phone1=f"+9989{phone_suffix}",
                    is_active=True,
                    is_archived=False,
                    created_at=datetime.utcnow(),
                )
                db.add(student)
                db.flush()
                new_students.append(student)
                total_students += 1

                # Guruhga qo'shish
                gs = GroupStudent(
                    group_id=grp.id,
                    student_id=student.id,
                    tariff_id=tariff.id,
                    joined_at=datetime.utcnow(),
                )
                db.add(gs)
                total_enrolled += 1

            db.flush()

            # 5. Aprel 2026 davomati (yangi talabalar uchun)
            # Juft indeksli guruhlar Du-Chor-Ju, toq indekslilar Se-Pay-Shan
            lesson_dates = APRIL_DATES_EVEN if grp_idx % 2 == 0 else APRIL_DATES_ODD

            for student in new_students:
                for ld in lesson_dates:
                    # 80% ehtimollik bilan keladi
                    is_present = random.random() < 0.80
                    existing_att = db.query(Attendance).filter(
                        Attendance.group_id   == grp.id,
                        Attendance.student_id == student.id,
                        Attendance.lesson_date == ld,
                    ).first()
                    if not existing_att:
                        db.add(Attendance(
                            group_id=grp.id,
                            student_id=student.id,
                            lesson_date=ld,
                            is_present=is_present,
                        ))
                        total_attendance += 1

            db.commit()
            all_in_group = db.query(GroupStudent).filter(GroupStudent.group_id == grp.id).count()
            print(f"  {grp.name}: {needed} yangi talaba qo'shildi (jami: {all_in_group})")

        db.commit()

        print(f"\n✓ Yaratildi: {total_students} talaba, {total_enrolled} enrollment, {total_attendance} davomat yozuvi")
        print("teacher1 bilan login qilib 'Mening panelim' ni tekshiring!")

    finally:
        db.close()


if __name__ == "__main__":
    run()
