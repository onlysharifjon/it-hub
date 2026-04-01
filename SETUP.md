# IT Hub — Local Setup Guide

## Tizim talablari

- Python 3.11+
- PostgreSQL 16
- Poetry (dependency manager)
- Node.js 18+ (frontend uchun)

---

## 1. PostgreSQL sozlash

### O'rnatish (Ubuntu/Debian)
```bash
sudo apt-get install -y postgresql postgresql-contrib
```

### Database va user yaratish
```bash
sudo -u postgres psql -c "CREATE USER ithub_user WITH PASSWORD 'IthubSecure2026' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE ithub_db OWNER ithub_user ENCODING 'UTF8';"
```

### Ulanishni tekshirish
```bash
PGPASSWORD='IthubSecure2026' psql -U ithub_user -d ithub_db -h localhost -c "SELECT current_user;"
```

---

## 2. Poetry o'rnatish

```bash
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

---

## 3. .env fayl

Loyiha root da `.env` fayl yarating (`.env.dist` asosida):

```env
DATABASE_URL=postgresql://ithub_user:IthubSecure2026@localhost:5432/ithub_db
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32)" bilan generate qiling>
ACCESS_TOKEN_EXPIRE_MINUTES=480
CORS_ORIGINS=http://localhost:5173
VITE_API_BASE=http://localhost:8000
```

---

## 4. Python paketlarini o'rnatish

```bash
PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install
```

> **Eslatma:** `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` ni qo'shish shart,
> aks holda Poetry keyring tekshirishda qolib ketishi mumkin.

---

## 5. Alembic migratsiyalar

```bash
PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry run alembic -c backend/alembic.ini upgrade head
```

Muvaffaqiyatli bo'lsa oxirgi qator shunday ko'rinadi:
```
INFO  [alembic.runtime.migration] Running upgrade ... -> 20260331_add_category, ...
```

---

## 6. Serverni ishga tushirish

### Backend (FastAPI)
```bash
PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

---

## 7. API dokumentatsiya

Server ishlagach, brauzerda oching:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health check:** http://localhost:8000/health

---

## 8. Default foydalanuvchilar

Server birinchi ishga tushganda quyidagi userlar avtomatik yaratiladi:

| Username  | Parol         | Rol      |
|-----------|---------------|----------|
| admin     | Admin@2026    | admin    |
| metodist  | Metodist@2026 | metodist |
| teacher1  | Teacher@2026  | teacher  |
| teacher2  | Teacher@2026  | teacher  |
| teacher3  | Teacher@2026  | teacher  |

---

## 9. Database jadvallar

| Jadval          | Tavsif                        |
|-----------------|-------------------------------|
| users           | Foydalanuvchilar (admin/metodist/teacher) |
| lessons         | Darslar (foundation/frontend/backend) |
| audit_logs      | O'zgarishlar tarixi           |
| students        | O'quvchilar                   |
| groups          | Guruhlar                      |
| group_students  | Guruh-o'quvchi bog'lanish     |
| payments        | To'lovlar                     |
| attendance      | Davomat                       |

---

## 10. Muammolarni hal qilish

### Poetry keyring da qolib ketsa
```bash
PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install
```

### Alembic migration xatosi
```bash
# Joriy holatni ko'rish
poetry run alembic -c backend/alembic.ini current

# Barcha migration tarixini ko'rish
poetry run alembic -c backend/alembic.ini history --verbose
```

### PostgreSQL service tekshirish
```bash
pg_lsclusters           # status ko'rish
sudo systemctl start postgresql  # yoqish
```

---

## Kredensialar (.env da saqlangan)

| Parametr       | Qiymat                |
|----------------|-----------------------|
| DB User        | ithub_user            |
| DB Password    | IthubSecure2026       |
| DB Name        | ithub_db              |
| DB Host        | localhost:5432        |
| API Port       | 8000                  |
| Frontend Port  | 5173                  |
