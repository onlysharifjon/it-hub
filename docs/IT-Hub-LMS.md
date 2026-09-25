---
tags: [project, lms, fastapi, react, documentation]
created: 2026-04-12
status: active
---

# IT Hub — O'quv Markaz LMS

> To'liq stack o'quv markaz boshqaruv tizimi. Backend: FastAPI + PostgreSQL. Frontend: React (Vite). Deploy: Docker Compose.

---

## Mundarija

- [[#Loyiha haqida]]
- [[#Texnologiyalar]]
- [[#Arxitektura]]
- [[#Ma'lumotlar bazasi modellari]]
- [[#API endpointlar]]
- [[#Rollar va huquqlar]]
- [[#Frontend sahifalar]]
- [[#Ishga tushirish]]
- [[#Default foydalanuvchilar]]
- [[#Test natijalar]]
- [[#Muhim fayllar]]

---

## Loyiha haqida

IT Hub — o'quv markazlar uchun yozilgan boshqaruv tizimi (LMS). Tizim quyidagilarni qamrab oladi:

- **Metodika boshqaruvi** — darslar, bo'limlar, topshiriqlar
- **O'quvchilar boshqaruvi** — profil, arxivlash, guruh a'zoligi
- **Guruhlar** — bosqich (Foundation / Frontend / Backend), jadval, o'qituvchi tayinlash
- **To'lovlar** — oylik to'lov, kvitansiya generatsiyasi (HTML)
- **Davomat** — kunlik/oylik davomat jadvali
- **Moliya** — daromad, xarajatlar, sof foyda, Excel export
- **O'qituvchi ish haqi** — har bir guruh bo'yicha hisoblash
- **Audit log** — barcha o'zgarishlarni kuzatish
- **Foydalanuvchi boshqaruvi** — bloklash, muddatli kirish

---

## Texnologiyalar

### Backend
| Kutubxona | Versiya | Vazifa |
|-----------|---------|--------|
| FastAPI | ^0.109.2 | REST API framework |
| SQLAlchemy | ^2.0.27 | ORM |
| Alembic | ^1.13.1 | DB migratsiyalar |
| Pydantic | ^1.10.14 | Ma'lumot validatsiyasi |
| PostgreSQL | 16 | Asosiy baza (Docker) |
| bcrypt | ^4.0.0 | Parol xeshlash |
| python-jose | ^3.5.0 | JWT token |
| openpyxl | ^3.1.2 | Excel export |
| uvicorn | ^0.27.1 | ASGI server |

### Frontend
| Kutubxona | Vazifa |
|-----------|--------|
| React 18 | UI framework |
| Vite | Build tool |
| react-hot-toast | Bildirishnomalar |
| @fortawesome/react-fontawesome | Ikonlar |

### DevOps
| Vosita | Vazifa |
|--------|--------|
| Docker | Konteynerizatsiya |
| Docker Compose | Servislarni boshqarish |
| Nginx | Frontend serving |

---

## Arxitektura

```
it-hub/
├── backend/
│   ├── main.py          ← Barcha API endpointlar (1800+ qator)
│   ├── models.py        ← SQLAlchemy modellari
│   ├── schemas.py       ← Pydantic schemalar
│   ├── database.py      ← DB ulanish va sessiya
│   ├── alembic/         ← Migratsiya fayllari
│   └── tests/
│       ├── conftest.py  ← Test fixtures
│       ├── test_auth.py
│       ├── test_lessons.py
│       └── test_audit.py
├── frontend/
│   └── src/
│       ├── App.jsx      ← Asosiy app, routing (hash-based)
│       ├── api.js       ← Barcha API chaqiruvlar
│       ├── components/  ← 23 ta komponent
│       └── styles.css
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

### Arxitektura diagrammasi

```
Browser
  │
  │  HTTP (port 5373)
  ▼
Nginx (frontend static)
  │
  │  fetch() API calls
  ▼
FastAPI (port 8000)
  │
  │  SQLAlchemy ORM
  ▼
PostgreSQL (port 5432)
```

### Frontend routing

Hash-based routing (`#lessons`, `#students` va h.k.) — server-side routing yo'q, SPA.

---

## Ma'lumotlar bazasi modellari

### User

```
users
├── id (PK)
├── username (unique)
├── hashed_password
├── full_name
├── role → admin | metodist | teacher
├── is_active
├── blocked_reason
├── blocked_contact
├── blocked_at
├── expires_at       ← null = muddatsiz
└── created_at
```

**Munosabatlar:**
- `updated_lessons` ← Lesson (updated_by_id)
- `audit_logs` ← AuditLog
- `teaching_groups` ← Group

---

### Lesson

```
lessons
├── id (PK)
├── category → foundation | frontend | backend
├── lesson_number  [UniqueConstraint(category, lesson_number)]
├── title
├── section
├── guide
├── homework
├── extra_notes
├── updated_at
└── updated_by_id (FK → users)
```

**Bosqich hajmlari:**

| Bosqich | Darslar soni | Davomiyligi |
|---------|-------------|-------------|
| Foundation | 24 | 2 oy |
| Frontend | 72 | 6 oy |
| Backend | 108 | 9 oy |

---

### AuditLog

```
audit_logs
├── id (PK)
├── entity_type  ← "lesson", "user", va h.k.
├── entity_id
├── action       ← "create" | "update" | "delete" | "reorder"
├── changed_by_id (FK → users)
├── changed_at
├── old_value    ← JSON string
└── new_value    ← JSON string
```

---

### Student

```
students
├── id (PK)
├── full_name
├── phone1
├── father_name / father_phone
├── mother_name / mother_phone
├── telegram_id
├── notes
├── is_active
├── is_archived
└── created_at
```

**Munosabatlar:**
- `group_memberships` ← GroupStudent
- `payments` ← Payment

---

### Group

```
groups
├── id (PK)
├── name
├── stage → foundation | frontend | backend
├── teacher_id (FK → users)
├── course_price
├── teacher_pay_per_student
├── schedule   ← "Du,Cho,Ju 14:00"
├── start_date
├── is_active
└── created_at
```

---

### GroupStudent (ko'p-ko'p)

```
group_students
├── id (PK)
├── group_id (FK → groups)
├── student_id (FK → students)
├── tariff_id (FK → tariffs)
└── joined_at
```

---

### Payment

```
payments
├── id (PK)
├── student_id (FK → students)
├── group_id (FK → groups)
├── amount
├── month (1–12)
├── year (≥2020)
├── paid_at
└── notes
```

---

### Tariff

```
tariffs
├── id (PK)
├── name
├── price
├── description
├── is_active
└── created_at
```

---

### Expense

```
expenses
├── id (PK)
├── name
├── amount
├── month (1–12)
├── year (≥2020)
└── created_at
```

---

### Attendance

```
attendance
├── id (PK)
├── group_id (FK → groups)
├── student_id (FK → students)
├── lesson_date (Date)
├── is_present
└── [UniqueConstraint(group_id, student_id, lesson_date)]
```

---

## API Endpointlar

### Auth

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| POST | `/auth/login` | Login, JWT token olish | Hammaga |
| GET | `/auth/me` | Joriy foydalanuvchi ma'lumoti | Login bo'lgan |

**Login javob:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### Foydalanuvchilar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/users` | Ro'yxat (pagination, qidiruv) | metodist+ |
| POST | `/users` | Yangi foydalanuvchi | admin |
| PUT | `/users/{id}` | Tahrirlash | admin |
| POST | `/users/{id}/block` | Bloklash (sabab, kontakt) | admin |
| POST | `/users/{id}/unblock` | Blokdan chiqarish | admin |

---

### Darslar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/lessons` | Ro'yxat (`?category=foundation`) | login |
| GET | `/lessons/{id}` | Bitta dars | login |
| POST | `/lessons` | Yangi dars | metodist+ |
| PUT | `/lessons/{id}` | Tahrirlash | metodist+ |
| PUT | `/lessons/reorder` | Tartibni o'zgartirish | metodist+ |
| DELETE | `/lessons/{id}` | O'chirish | metodist+ |

---

### O'quvchilar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/students` | Ro'yxat (pagination, qidiruv, arxiv filter) | metodist+ |
| GET | `/students/{id}` | Bitta o'quvchi | metodist+ |
| POST | `/students` | Yangi o'quvchi | metodist+ |
| PUT | `/students/{id}` | Tahrirlash | metodist+ |
| POST | `/students/{id}/archive` | Arxivlash | metodist+ |
| POST | `/students/{id}/unarchive` | Arxivdan qaytarish | metodist+ |

---

### Guruhlar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/groups` | Ro'yxat | login |
| GET | `/groups/{id}` | Guruh detail (a'zolar bilan) | login |
| POST | `/groups` | Yangi guruh | metodist+ |
| PUT | `/groups/{id}` | Tahrirlash | metodist+ |
| DELETE | `/groups/{id}` | O'chirish | metodist+ |
| POST | `/groups/{id}/students` | O'quvchi qo'shish | metodist+ |
| DELETE | `/groups/{id}/students/{sid}` | O'quvchi chiqarish | metodist+ |

---

### To'lovlar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/payments` | Ro'yxat (filter: student, group, month, year) | metodist+ |
| POST | `/payments` | Yangi to'lov | metodist+ |
| PUT | `/payments/{id}` | Tahrirlash | metodist+ |
| DELETE | `/payments/{id}` | O'chirish | metodist+ |
| GET | `/payments/{id}/receipt` | HTML kvitansiya | download token |

---

### Davomat

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/attendance/today` | Bugungi davomat (barcha guruhlar) | login |
| GET | `/groups/{id}/attendance` | Guruh oylik davomat jadvali | login |
| POST | `/groups/{id}/attendance/{date}` | Davomat saqlash | metodist+ |
| DELETE | `/groups/{id}/attendance/{date}` | Davomat o'chirish | admin |

---

### Moliya va Statistika

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/stats/overview` | Umumiy statistika | admin |
| GET | `/stats/teacher-salaries` | O'qituvchi oylik | admin |
| GET | `/stats/export/excel` | Excel yuklash | admin (token) |
| GET | `/finance/monthly` | Oylik moliyaviy hisobot | admin |
| GET | `/teacher/dashboard` | O'qituvchi shaxsiy panel | teacher |

---

### Xarajatlar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/expenses` | Xarajatlar ro'yxati | admin |
| POST | `/expenses` | Yangi xarajat | admin |
| PUT | `/expenses/{id}` | Tahrirlash | admin |
| DELETE | `/expenses/{id}` | O'chirish | admin |

---

### Tariflar

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/tariffs` | Ro'yxat | login |
| POST | `/tariffs` | Yangi tarif | metodist+ |
| PUT | `/tariffs/{id}` | Tahrirlash | metodist+ |
| DELETE | `/tariffs/{id}` | O'chirish | metodist+ |

---

### Audit Log

| Method | URL | Tavsif | Ruxsat |
|--------|-----|--------|--------|
| GET | `/audit-logs` | Ro'yxat (paginated) | metodist+ |
| GET | `/audit-logs/lesson/{id}` | Dars tarixi | metodist+ |

**Javob formati** (paginated):
```json
{
  "items": [ { "id": 1, "action": "update", ... } ],
  "meta": { "total": 42, "page": 1, "page_size": 25, "total_pages": 2 }
}
```

---

### Tizim

| Method | URL | Tavsif |
|--------|-----|--------|
| GET | `/health` | Server holati tekshiruvi |

---

## Rollar va Huquqlar

```
admin
  ├── Barcha metodist huquqlari
  ├── Foydalanuvchi boshqaruvi (yaratish, bloklash)
  ├── Moliyaviy statistika va hisobotlar
  ├── Xarajatlar boshqaruvi
  ├── Excel export
  └── Davomat o'chirish

metodist
  ├── Darslar CRUD
  ├── O'quvchilar CRUD + arxivlash
  ├── Guruhlar CRUD
  ├── To'lovlar CRUD
  ├── Tariflar CRUD
  ├── Davomat saqlash
  └── Audit log ko'rish

teacher
  ├── Darslarni ko'rish (faqat o'qish)
  ├── O'z guruhlarini ko'rish
  ├── Davomat ko'rish
  └── Shaxsiy dashboard (ish haqi)
```

> **Eslatma:** `metodist+` = metodist yoki admin

---

## Frontend Sahifalar

| Sahifa (hash) | Komponent | Tavsif | Ko'rinish |
|---------------|-----------|--------|-----------|
| `#lessons` | `Lessons.jsx` | Darslar ro'yxati + tahrir | metodist, teacher |
| `#students` | `Students.jsx` | O'quvchilar + qidiruv | metodist+ |
| `#groups` | `Groups.jsx` | Guruhlar ro'yxati | hammaga |
| `#group_detail` | `GroupDetail.jsx` | Guruh a'zolari, davomat | hammaga |
| `#payments` | `Payments.jsx` | To'lovlar jadvali | metodist+ |
| `#dashboard` | `Dashboard.jsx` | Admin statistika paneli | admin |
| `#teacher_dashboard` | `TeacherDashboard.jsx` | O'qituvchi paneli | teacher |
| `#today_attendance` | `TodayAttendance.jsx` | Bugungi davomat | hammaga |
| `#teacher_salaries` | `TeacherSalaries.jsx` | O'qituvchilar ish haqi | admin |
| `#finance` | `Finance.jsx` | Oylik moliya hisoboti | admin |
| `#expenses` | `Expenses.jsx` | Xarajatlar | admin |
| `#tariffs` | `Tariffs.jsx` | Tarif rejalari | metodist+ |
| `#users` | `Users.jsx` | Foydalanuvchilar | admin |

---

## Ishga Tushirish

### Docker bilan (tavsiya etiladi)

```bash
# 1. Proyektni klonlash
git clone <repo-url>
cd it-hub

# 2. Servisllarni ishga tushirish
docker compose up -d

# Frontend: http://localhost:5373
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Lokal (development)

**Backend:**
```bash
poetry install
poetry run alembic -c backend/alembic.ini upgrade head
poetry run python -m backend.seed
poetry run uvicorn backend.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### Environment o'zgaruvchilari

| O'zgaruvchi | Default | Tavsif |
|-------------|---------|--------|
| `DATABASE_URL` | sqlite:///./ithub.db | DB ulanish |
| `SECRET_KEY` | `change-me-in-production` | JWT imzolash |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 480 (8 soat) | Token muddati |
| `CORS_ORIGINS` | `http://localhost:5173,5174` | Ruxsat etilgan originlar |
| `VITE_API_BASE` | `http://localhost:8000` | Frontend API URL |

---

## Default Foydalanuvchilar

Tizim birinchi ishga tushganda avtomatik yaratiladi:

| Username | Parol | Rol | Ism |
|----------|-------|-----|-----|
| `admin` | `Admin@2026` | admin | Administrator |
| `dev` | `Dev@2026` | admin | Developer |
| `metodist` | `Metodist@2026` | metodist | Metodist |
| `teacher1` | `Teacher@2026` | teacher | Sarvar Toshmatov |
| `teacher2` | `Teacher@2026` | teacher | Malika Yusupova |
| `teacher3` | `Teacher@2026` | teacher | Jasur Rahimov |

> **Xavfsizlik:** Production muhitda parollarni albatta o'zgartiring!

---

## Test Natijalari

**Oxirgi test (2026-04-12):** `26/26 PASSED`

```
backend/tests/test_auth.py     ......   6/6  ✓
backend/tests/test_lessons.py  ..........  16/16  ✓ (test_reorder bilan)
backend/tests/test_audit.py    ......   6/6  ✓ (tuzatishdan keyin)
```

### Test muhiti sozlash

```bash
# Virtual muhit yaratish
uv venv --python 3.11
uv pip install fastapi==0.109.2 pydantic==1.10.21 starlette==0.35.1 httpx==0.27.0 \
               sqlalchemy uvicorn python-dotenv bcrypt python-jose[cryptography] \
               openpyxl pytest pytest-asyncio anyio

# Testlarni ishga tushirish
.venv/Scripts/pytest backend/tests/ -v
```

### Tuzatilgan nosozliklar

| Xato | Sabab | Tuzatish |
|------|-------|----------|
| `'month' is not a keyword arg` | `Lesson` modeli refactor qilindi (month/week → category) | `conftest.py` yangilandi |
| `KeyError: 0` audit testlarida | `/audit-logs` paginated format qaytaradi `{"items": [...]}` | `res.json()["items"]` qilinadi |
| `TestClient.__init__` xatosi | httpx/starlette versiya noto'g'riliği | To'g'ri versiyalar o'rnatildi |

---

## Muhim Fayllar

| Fayl | Tavsif |
|------|--------|
| [backend/main.py](backend/main.py) | Barcha API (1800+ qator) |
| [backend/models.py](backend/models.py) | DB modellari |
| [backend/schemas.py](backend/schemas.py) | Pydantic schemalar |
| [backend/database.py](backend/database.py) | DB ulanish |
| [frontend/src/api.js](frontend/src/api.js) | Frontend API qatlamlari |
| [frontend/src/App.jsx](frontend/src/App.jsx) | Routing va holat boshqaruvi |
| [docker-compose.yml](docker-compose.yml) | Servislar konfiguratsiyasi |
| [pyproject.toml](pyproject.toml) | Python bog'liqliklar |

---

## Ma'lum Cheklovlar va Kelajakdagi Ishlar

### Cheklovlar
- `@app.on_event("startup")` — deprecated, `lifespan` bilan almashtirish kerak
- `schemas.py` — Pydantic v1 stil, v2 ga ko'chirish kerak (`ConfigDict`, `model_dump`)
- Frontend hash-based routing — `react-router` yoki boshqa kutubxona tavsiya etiladi
- Test coverage: faqat `auth`, `lessons`, `audit` qoplangan; `students`, `groups`, `payments`, `attendance` testlari yo'q

### Qo'shilishi mumkin bo'lgan xususiyatlar
- [ ] SMS yoki Telegram bildirishnomalar
- [ ] O'quvchi kirish huquqi (o'z darslarini ko'rish)
- [ ] Dars video/fayl biriktirish
- [ ] To'lov eslatmalari
- [ ] Mobile app (React Native)

---

*Hujjat avtomatik yaratilgan — 2026-04-12*
