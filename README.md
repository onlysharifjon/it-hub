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


## SPACE learning assessments (2026-10-22)

`backend/minar/academy.py` adds the student `/space/academy` and staff
`/space/admin/academy` APIs. The additive Alembic revision is `20261022a_academy`.
Apply migrations before starting the updated API and worker. Existing CRM students,
groups, sessions and SPACE wallet remain the source of truth.

CRM → SPACE ta’lim → Testlar va kutubxona contains:

- Library preview and idempotent import: 77 MyWebsite topics, 924 questions, 77 bilingual
  study materials and 24 AI Creator slide decks. Source bundle contains curriculum only,
  no student lists or database exports. Imports are drafts; admin/support teacher can
  edit and publish. Teachers can read, present slides and assign published material.
- Group tests and public entry tests: randomized questions/options, per-attempt snapshots,
  server deadlines, autosave, limited retakes, scheduled opening and revocable public links.
- Scoped results, answer review, question difficulty, common incorrect options, student
  risk list, daily totals and CSV. Detailed answer snapshots load on demand. Question/risk
  analysis covers the latest 1,000 attempts; daily metrics cover all attempts that day.
- Guest test results can be explicitly linked to CRM leads by admin/support teacher.
  Student and teacher permissions are checked on the backend.

The existing `backend.worker` minute reminder scheduler delivers internal test notices,
once-only reminders after three hours and a staff digest after 20:00 Tashkent time.
No Telegram/email credentials or external message sending are introduced.

Student reward rules use the existing append-only ledger: first successful (80%+) topic
assessment +5 coins, fixing a mistake with three correct answers +2 coins once, and up
to 10 daily bonus answers at +1 coin each. Bonus questions come from topics with a
completed test. Tab visibility warnings are advisory and never deduct points.

Public test URL: `https://space.minaracademy.uz/?entry=TOKEN`.
`VITE_SPACE_URL` optionally changes this origin in the CRM frontend build. All public
attempt credentials are HttpOnly cookies; contact details and answers are never cached.
The source bundle is imported through the CRM interface after deployment; existing
courses and live group assignments are not silently replaced.
