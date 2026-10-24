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

Assessment updates (2026-10-24): new tests can omit `dueAt` and stay open until
admin, Support Teacher, or the assigned teacher chooses “Yakunlash”. Each attempt
still has its own time limit. Closure grades saved answers for all running attempts
and preserves results for students and staff. Reopening keeps earlier results and
removes any legacy assignment deadline. Existing explicitly dated tests retain
their dates until reopened. Apply migration `20261024a_manual_test_close` first.
An older backend must not be restored while assignments with NULL `due_at` exist;
both the schema downgrade and release rollback script guard against this.
`VITE_SPACE_URL` optionally changes this origin in the CRM frontend build. All public
attempt credentials are HttpOnly cookies; contact details and answers are never cached.
The source bundle is imported through the CRM interface after deployment; existing
courses and live group assignments are not silently replaced.

The exam warning update requires additive migration `20261024b_exam_warnings`.
It records up to 200 typed browser signals per attempt with stable event IDs and
server receipt timestamps. Retry requests are idempotent and cannot erase history;
old scalar warning counts remain readable. Staff reports and CSV show categories,
and scoped attempt review shows the timeline. Warnings never change scores or
finish attempts. Clipboard contents and browsing URLs are not collected.
The application can roll back to the manual-close release while retaining this
column. Schema downgrade refuses to discard populated warning history.

The 2026-10-29 account update uses `GET /space/admin/account-groups` for the
SPACE account and QR selectors. It returns all active groups for admin/support
teacher and only the current teacher's active groups for teachers. Loading,
empty and retry states are visible; the old invalid `page_size=200` request is
removed. CRM route permissions and navigation now expose Minar Space to teachers.
Teachers may list their current group members' existing accounts and create
missing accounts through `POST /space/admin/accounts/bulk`. Group ownership is
checked on the server; transfers and teacher reassignment revoke access. Existing
passwords are never reset by bulk creation. Single-account administration, password
reset, course changes, account blocking and QR issuance retain staff permissions.
