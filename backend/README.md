# Backend setup

### Quick start
```bash
# from backend directory
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn main:app --reload
```

- `alembic upgrade head` – applies migrations to create tables.
- `python seed.py` – inserts the 36 lessons if the table is empty.
- `uvicorn main:app --reload` – starts the API (CORS enabled for localhost:5173).

