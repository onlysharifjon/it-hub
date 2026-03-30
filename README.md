# IT Hub

Full-stack course methodology app using FastAPI, Alembic, SQLite, and React (Vite).

## Backend quick start
```bash
poetry lock
poetry install
poetry run python -m alembic -c backend/alembic.ini upgrade head
poetry run python -m backend.seed
poetry run uvicorn backend.main:app --reload
```

## Frontend quick start
```bash
cd frontend
npm install
npm run dev
```

