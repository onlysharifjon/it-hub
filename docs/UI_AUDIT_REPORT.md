# IT Hub — LMS/CRM: Complete Codebase & UI/UX Audit

Prepared for: a future AI/design agent tasked with redesigning the UI **without opening the codebase**. Everything needed to understand structure, data flow, and current visual/UX state is below.

Server context: production instance lives at `crm.minaracademy.uz`, frontend built to `/var/www/it-hub/frontend/dist`, backend FastAPI app served by pm2 process `it_hub_api` on `127.0.0.1:8001`, reverse-proxied by nginx with `/api/` prefix stripped before hitting the backend.

---

# 1. CRM Overview

**What kind of CRM this is:** A vertically-integrated **LMS + CRM + back-office ERP** for a coding-bootcamp-style education business ("Minar Academy" / "IT Hub", teaching Foundation → Frontend → Backend programming tracks). It is not a generic CRM — it fuses:

- A **sales CRM** (lead pipeline, kanban, call-center workflow, referral tracking)
- A **student information system / LMS** (students, groups, attendance, grades, homework, certificates)
- **Billing/finance** (tariffs, payments, debt tracking, salary calculation, expenses, P&L)
- **Staff management** (users, roles, employee discipline/warnings, Telegram bot administration)
- A **parent portal backend** (parent accounts consumed by a separate mobile app, not this web app)

**Main business purpose:** Run a coding school's entire operational loop — capture a lead → convert to a demo/trial student → enroll into a paid group → track attendance & payments monthly → pay teachers based on attendance-driven formulas → issue certificates → manage staff discipline — all in one internal tool.

**Target users (7 roles, from `backend/models.py` `UserRole` enum):**
| DB value | Uzbek label (UI) | Role summary |
|---|---|---|
| `admin` | Admin | Superadmin — full access, finance, salary, users, bot admin |
| `support_teacher` | Support Teacher | Curriculum editor ("metodist" in code comments) — lessons CRUD, students/groups |
| `teacher` | O'qituvchi | Classroom teacher — own groups only, attendance, grading, coins, own salary |
| `hunter` | Hunter | Sales/enrollment closer — leads, students, groups, payments, parents, expenses |
| `sales` | Sales | Lead-gen / referral role — leads + students/groups, no finance |
| `call_center` | Call Center | Lead qualification — leads, students/groups, feedback inbox, notifications |
| `audit` | Audit | Internal-discipline officer — issues warnings/fines to staff, no other access |

**Main workflow (happy path):**
1. A lead arrives (manually entered by hunter/sales/call_center, via a public intake form `#intake/<slug>`, or via a Facebook Lead Ads webhook) → lands in the **Leads** kanban.
2. Call center / hunter calls, moves the lead through pipeline stages (customizable, default: Yangi → Qo'ng'iroq qilindi → Qayta qo'ng'iroq → Keladi → Demo → To'landi / Rad etildi).
3. Lead is converted into a **Student** (often first as a "demo" student who hasn't attended yet).
4. Student is attached to a **Group** (with a **Tariff** = monthly price).
5. Teacher takes daily **Attendance** (also via camera face-recognition auto check-in, and via a "Today's Attendance" quick-mark screen).
6. Hunter/admin records **Payments** monthly; the system computes expected vs paid vs debt per student per month, applying vacations, special discounts, and advance balance.
7. Teacher salaries are **auto-calculated** monthly from a formula (fixed base + per-student-per-lesson share) with per-month manual override capability.
8. Admin reviews company-wide **Dashboard/Finance** (income, teacher salary cost, external expenses, net profit) and exports Excel reports.
9. Teachers issue **grades**, **coin rewards**, **feedback comments** (visible to parents), and generate **certificates** on course completion.
10. **Audit** role issues formal warnings/fines to staff for rule violations, delivered via a Telegram bot.

**Key CRM processes:** lead capture (manual/public-form/Facebook webhook) → pipeline management (kanban + list + analytics) → shared "pool" lead claiming between reps → reminders/callbacks → referral-source performance tracking (drag-and-pan "funnel board") → conversion analytics.

---

# 2. Tech Stack

- **Frontend framework:** React 18.2 (function components + hooks only, no class components), bootstrapped with **Vite 5.1** (`vite.config.js`, `vite build` → `dist/`).
- **Routing:** **None.** No `react-router` or any router library in `package.json`. Navigation is a hand-rolled system: `window.location.hash` (e.g. `#leads`, `#group_detail`) is read/written directly in `App.jsx`, and a big `activePage` state variable conditionally renders one of ~24 top-level components. Back/forward browser buttons work only because of a manual `hashchange` listener.
- **State management:** **None (no Redux/Zustand/Recoil/Jotai/MobX).** Pure React `useState`/`useEffect`/prop-drilling. One React Context exists: `ThemeContext.jsx` (theme name only: light/dark/ocean, persisted to `localStorage`). Selected group/student for detail views are persisted ad-hoc to `sessionStorage` (`selectedGroup`, `selectedStudent`, `groupDetailOrigin`) so browser refresh doesn't lose the drill-down.
- **Backend framework:** **FastAPI** (Python), single 6,903-line `main.py` containing all 194 route handlers directly (no routers/blueprints split out). SQLAlchemy ORM (`models.py`, 849 lines, ~35 tables). Pydantic v1-style schemas (`schemas.py`, 1,479 lines, `regex=` validator syntax confirms Pydantic 1.x).
- **Database:** **SQLite** (`DATABASE_URL=sqlite:////var/www/it-hub/data/ithub.db`), via `alembic` migrations (`backend/alembic/`).
- **API architecture:** REST-ish JSON over HTTP, single FastAPI app, **Bearer JWT** auth (`python-jose`), 12-hour token expiry by default. No GraphQL, no websockets (chat/notification screens poll on intervals — e.g. ChatBot.jsx polls every 5–15s, Sidebar feedback badge every 60s).
- **UI component libraries:** **None** (no MUI, Ant Design, Chakra, Radix, shadcn). Every button/modal/table/badge/dropdown is a hand-built `<div>`/`<button>` styled via one global stylesheet.
- **CSS framework:** **None** (no Tailwind/Bootstrap). One hand-written global stylesheet `styles.css` (3,205 lines, ~631 class selectors) using CSS custom properties for a light/dark/"ocean" 3-theme system, plus **heavy use of React inline `style={{...}}`** in many newer components (see Design System Audit §16 and Problem #1).
- **Icons:** FontAwesome (`@fortawesome/react-fontawesome` + `free-solid-svg-icons`/`free-regular-svg-icons`/`free-brands-svg-icons`), used as `<FontAwesomeIcon icon={faX} />` everywhere. No custom icon set.
- **Fonts:** **Two font systems are loaded simultaneously** — Google Fonts CDN `Inter` (imported at the top of `styles.css` via `@import url(...)`) *and* self-hosted `@fontsource-variable/geist` + `geist-mono` (imported in `main.jsx` with a comment claiming "tabular figures... for numeric/tabular data"). Only `'Inter'` is ever referenced in a `font-family` declaration — the Geist fonts are loaded but **never used** anywhere in the codebase (verified: zero `font-family` reference to `Geist` in styles.css or inline styles). See Problem #2.
- **Toasts/notifications (UI feedback):** `react-hot-toast` (`<Toaster position="top-right" />` mounted once in `App.jsx`), used pervasively for success/error feedback on every mutation.
- **Authentication system:** Custom JWT bearer auth. `POST /auth/login` returns `{access_token, token_type}`; token stored in `localStorage` (key `token`) and manually attached as `Authorization: Bearer <token>` header in every `fetch` call inside `api.js`. `GET /auth/me` fetches the current user + role on app load. Login screen (`Login.jsx`) also handles two special 403 error shapes: `blocked` (account manually disabled with reason+contact) and `expired` (account past its `expires_at` date) — both render a dedicated "can't sign in" panel instead of a generic error.
- **File uploads:** Plain `multipart/form-data` `fetch` calls (avatar, student photo, student face-photo for camera recognition, certificate PDF) — bypass the shared `request()` JSON helper in `api.js` and duplicate the auth-header/error-handling logic 5 times.
- **File structure:**
  ```
  /var/www/it-hub/
    backend/
      main.py          (6,903 lines — ALL 194 routes + auth + business logic)
      models.py        (849 lines — ~35 SQLAlchemy tables)
      schemas.py        (1,479 lines — Pydantic request/response models)
      database.py, security.py, core_calc.py (salary/payment math), bot_client.py, facebook_leads.py
      alembic/          (DB migrations)
    frontend/
      src/
        App.jsx          (352 lines — shell, hash-routing, role-gating table)
        main.jsx          (React root + font imports)
        ThemeContext.jsx  (light/dark/ocean theme state)
        api.js            (636 lines — every frontend→backend call, no client library)
        styles.css        (3,205 lines — the entire design system)
        components/       (42 .jsx files, ~13,000 lines total — one file per "page" or shared widget)
      vite.config.js, package.json
    bot/                  (separate Telegram bot codebase, own DB — administered from BotAdmin.jsx/ChatBot.jsx)
    camera/               (face-recognition attendance service)
  ```
  There is **no `pages/` vs `components/` split** — page-level screens (Leads, Students, Dashboard...) and tiny shared widgets (Pagination, ProgressBar, DateRangePicker) live in the same flat `components/` directory.

---

# 3. Sitemap

Navigation is not URL-route-based; each node below is a `activePage` hash value (`#<key>`) mapped in `App.jsx`. Indentation shows conceptual grouping (matches Sidebar section labels), not actual URL nesting — there is no nesting.

```
(auth gate)
├── Login (#, shown when logged out)
├── Public Intake Form (#intake/<slug> — no auth, public lead-capture page)
└── App shell (authenticated, role-gated)
    ├── Metodika (Curriculum)
    │   └── Lessons (#lessons) — category tabs: Foundation / Frontend / Backend
    ├── Narxlar (Hunter-only shortcut)
    │   └── Payments (#payments)
    ├── Mening panelim (Teacher-only)
    │   └── Teacher Dashboard (#teacher_dashboard)
    ├── CRM
    │   ├── Leads (#leads)
    │   ├── Notifications (#notifications)  — actually "student visit log" (keldi/ketdi), not a generic notification center
    │   ├── Chatbot (#chatbot)              — Telegram inbox viewer
    │   ├── Izohlar / Feedback Inbox (#feedbacks)
    │   ├── Ota-onalar / Parents (#parents) — parent-account admin for the mobile app
    │   └── Xarajatlar / Expenses (#expenses) — duplicated entry point (also under Moliya)
    ├── Akademik (Academic)
    │   └── Academic (#academic) — tabbed: Grades / Coins / Feedback / Certificates / Events
    ├── Davomat (Attendance)
    │   └── Today's Attendance (#today_attendance)
    ├── Audit
    │   ├── Employees (#employees) — staff directory + Telegram linking
    │   └── Warnings (#audit_warnings) — discipline log
    ├── Mening (My)
    │   └── My Warnings (#my_warnings) — non-admin/audit staff see only their own
    ├── LMS
    │   ├── Students (#students) → Student Detail (#student_detail)
    │   └── Groups (#groups) → Group Detail (#group_detail)
    └── Moliya (Finance, admin-only)
        ├── Finance (#finance)
        ├── Payments (#payments) — same screen as Hunter's "Narxlar" entry
        ├── Tariffs (#tariffs)
        ├── Courses (#courses)
        ├── Special (#special) — per-student ad-hoc discounts
        ├── Teacher Salaries (#teacher_salaries) — read-only company-wide view
        ├── Salary (#salary) — editable payroll for ALL staff
        ├── Expenses (#expenses) — same screen as CRM's entry
        ├── Dashboard (#dashboard)
        └── Boshqaruv (Management)
            ├── Users (#users)
            └── Bot Admin (#bot_admin)
```

Two pages are reachable from two different sidebar sections but are literally the same component/state (`Payments` under both "Narxlar" for hunter and "Moliya" for admin; `Expenses` under both "CRM" for hunter and "Moliya" for admin) — this is intentional per-role convenience, not a bug, but worth flagging for an IA (information architecture) redesign.

---

# 4. Pages

Every entry below: PAGE NAME / activePage KEY (no real route) / PURPOSE / MAIN COMPONENTS / USER ACTIONS / DATA SOURCES (endpoint — method).

### PAGE: Login
KEY: shown when `!isAuthed`
Purpose: Authenticate; also surfaces account-blocked / account-expired states.
Components: split-screen layout (`lp-left` branding panel, `lp-right` form), password visibility toggle, spinner button.
Actions: submit login form; "← Orqaga" from block panel.
Data: `POST /auth/login`.

### PAGE: Public Intake Form
KEY: `#intake/<slug>` (bypasses auth entirely, rendered before the `isAuthed` check)
Purpose: External marketing landing form for lead capture, shareable link generated in Leads → "Formalar".
Components: brand header, dynamic form (name/phone/course interest/parent phone/notes), success/not-found states.
Actions: submit application.
Data: `GET /public/intake/{slug}`, `POST /public/intake/{slug}`.

### PAGE: Lessons (Curriculum)
KEY: `#lessons`
Purpose: CRUD the canonical lesson-plan library per track (Foundation/Frontend/Backend), used elsewhere (Group Detail "today's lesson", Homework auto-fill).
Components: `Sidebar` category switch (Foundation/Frontend/Backend tabs live IN the sidebar, not the page), `LessonList` (reorderable list w/ ▲▼ buttons), `LessonDetail` (edit form: section/guide/homework/extra notes), `AddLessonModal`, `AuditLogPanel` (change-history drawer), `ProgressBar` (% of lessons with guide+homework filled in).
Actions (support_teacher/admin only — teacher/others read-only): add lesson, edit fields, reorder (▲▼), delete, view audit history filtered by date range.
Data: `GET/POST/PUT/DELETE /lessons`, `PUT /lessons/reorder`, `GET /audit-logs?...`, `GET /audit-logs/lesson/{id}`.

### PAGE: Leads (CRM core)
KEY: `#leads`
Purpose: Full sales pipeline — see §7 for full workflow detail.
Components: `NotificationBell`, kanban board (drag-and-drop columns), `ListView` (table), `Analytics` view (funnel/source/referral charts + `FunnelBoard` pannable canvas + `CommentStats`), `LeadDrawer` (detail side panel w/ timeline+reminders), `StageManager` (admin pipeline-stage editor), `IntakeFormManager` (admin public-form manager), Add Lead modal.
Actions: add lead, drag/click to change stage, claim/release shared-pool leads, share a lead back to pool, delete, add/complete reminders, set callback datetime, search (`/` keyboard shortcut), filter by source/pool/"today", switch Board/List/Analytics view (arrow-key accessible tabs), manage pipeline stages (add/reorder/recolor/delete, admin), manage public intake forms (admin).
Data: `GET/POST /leads`, `PATCH /leads/{id}/status`, `PATCH /leads/{id}/stage`, `DELETE /leads/{id}`, `GET /leads/stats`, `GET /leads/{id}/activities`, `POST /leads/{id}/claim|release|share`, `GET/POST/PUT/DELETE /lead-stages`, `PUT /lead-stages/reorder`, `GET/POST/PUT/DELETE /lead-sources`, `GET /leads/analytics`, `GET/POST/PATCH/DELETE /reminders`, `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`, `GET/POST/PUT/DELETE /intake-forms`, `GET /leads/comment-stats`.

### PAGE: Students (list)
KEY: `#students`
Purpose: Manage the student roster in three states via tabs: Demo (not yet attended) / Active / Archived.
Components: tab bar, search + `DateFilter`, `data-table` with 11 columns, `Pagination`, per-row "davomat" (camera attendance) modal, `VacationModal`, `AttachGroupModal` (promote demo→active by assigning a group), telegram-delivery test button per row.
Actions: add student (or add demo student depending on tab), open full detail, view camera-attendance history (7/14/30/90-day filter), toggle active/inactive, mark/unmark demo, archive/unarchive, attach demo student to a group, mark vacation (hunter/admin only, clicking the payment-status cell), test Telegram delivery.
Data: `GET/POST/PUT /students`, `POST /students/{id}/archive|unarchive`, `POST /students/{id}/telegram-check`, `GET /students/{id}/camera-attendance`, `GET/POST/DELETE /students/{id}/vacations`, `GET /groups`, `POST /groups/{id}/students`.

### PAGE: Student Detail
KEY: `#student_detail` (requires `selectedStudent` in sessionStorage; falls back to list if missing — e.g. after a hard refresh)
Purpose: Full profile + tabbed sub-views for one student.
Components: left sidebar (`StudentAvatar` w/ upload, contact info card, groups badge list, demo-attach card, quick-actions card), right main panel tabbed: Ma'lumotlar (info edit form) / To'lov (payment summary + recent payments) / Davomat (camera attendance table) / Ta'til (vacation, hunter/admin only).
Actions: edit profile fields + save, upload photo, toggle active/demo/archived, attach to group (if demo), test Telegram delivery, add/delete vacation ranges.
Data: `GET/PUT /students/{id}`, `POST /students/{id}/photo`, `POST /students/{id}/archive|unarchive`, `GET /students/{id}/camera-attendance`, `GET /students/{id}/payments/summary`, `GET/POST/DELETE /students/{id}/vacations`, `GET /groups`, `POST /groups/{id}/students`, `POST /students/{id}/telegram-check`.
Note: a `RecordPaymentModal` component exists inline in `Students.jsx` (imports `createPayment`, `fetchStudentPaymentSummary`, icons `faWallet`/`faXmark`/`faCircleCheck` — **none of which are imported at the top of the file**, meaning this modal is unreachable dead code / a latent runtime crash if ever triggered). Flagged in UI/UX Problems §17.

### PAGE: Groups (list)
KEY: `#groups`
Purpose: Manage class groups (cohorts).
Components: filter toolbar (status tabs Faol/Arxiv/Hammasi, day-of-week filter, `DateFilter`), card grid (`group-card` w/ progress bar), create/edit modal (tariff-driven pricing), roster modal (add/remove students inline w/ tariff assignment), `Pagination`.
Actions: create group, edit, archive/unarchive (w/ confirm), open detail, quick roster add/remove from the list-page modal (separate from full Group Detail).
Data: `GET/POST/PUT /groups`, `GET /groups/{id}`, `POST/DELETE /groups/{id}/students(/{student_id})`, `GET /teachers`, `GET /students`, `GET /tariffs`.

### PAGE: Group Detail
KEY: `#group_detail` (requires `selectedGroup` in sessionStorage; "Orqaga" returns to whichever page it was opened from — tracked via `groupDetailOrigin`: groups / teacher_dashboard / today_attendance)
Purpose: The most complex single screen — full attendance grid, camera log, homework, certificates for one group.
Components: left sidebar (teacher card, monthly progress bar, "today's lesson" card w/ homework-send button, monthly stats, per-student summary list, hunter-only per-student tariff list), right main panel tabbed Yo'qlama (attendance)/Kamera (camera log); attendance is a full month-grid table (`attendance-table`) with click-to-cycle cells (present→absent→unmarked); homework-send modal; certificate-generation modal + `GroupCertificates` (separate full-screen printable certificate designer, see §9).
Actions: switch month/year, add/delete a lesson date (respecting the group's weekly schedule), click any cell to cycle attendance state, send homework to the group's Telegram chat, generate/view/print/edit certificates for all members, switch attendance/camera tabs.
Data: `GET/POST/DELETE /groups/{id}/attendance(/{date})`, `GET /groups/{id}` , `GET /groups/{id}/next-lesson`, `GET/POST /groups/{id}/homeworks`, `GET /groups/{id}/camera-attendance`, `GET/POST /groups/{id}/certificates`, `POST /groups/{id}/certificates/generate`, `PUT /groups/{id}/certificates`.

### PAGE: Payments
KEY: `#payments`
Purpose: Record/view/void payments; dedicated Debtors view; Excel export; printable receipts.
Components: KPI row (4 cards: total debt, debtor count, paid-this-month, expected-this-month), List/Debtors view toggle, month/year filter + `DateFilter`, `data-table`, `Pagination`, payment create/edit modal (auto-computes "expected/paid/remaining" as you pick student+group+month), "Sales" attribution toggle button inside the modal, quick-pay-in-full button from the Debtors table.
Actions: add payment, edit (admin only), delete/void (admin only, "un-pays" the student), quick-pay full remaining balance from Debtors list, download Excel, print receipt (opens a receipt URL in a new tab using a short-lived download token).
Data: `GET/POST/PUT/DELETE /payments`, `GET /payments/expected`, `GET /students/{id}/payments/summary`, `GET /stats/export/excel`, `GET /payments/{id}/receipt`, `GET /auth/download-token`.

### PAGE: Dashboard (admin)
KEY: `#dashboard`
Purpose: Company-wide KPI overview + monthly P&L + inline expense management + annual bar chart + full monthly history table.
Components: KPI cards (students, groups, this-month income w/ trend arrow, last-month income), P&L card row (income/teacher salary/external expenses/total expenses/net profit, two cards are clickable shortcuts to Teacher Salaries / Expenses pages), inline expense table+modal for the selected month, custom hand-drawn bar chart (`div`-based bars, not a charting library) for the selected year, full reversed-chronological monthly stats table.
Actions: change year, add/edit/delete an expense inline, download Excel, click P&L cards to navigate to related pages.
Data: `GET /stats/overview`, `GET/POST/PUT/DELETE /expenses`, `GET /stats/export/excel`.

### PAGE: Teacher Salaries (admin, read-only)
KEY: `#teacher_salaries`
Purpose: Company-wide breakdown of what every teacher is owed this month, drillable to student level.
Components: KPI row, expandable per-teacher cards → expandable per-group rows → per-student attendance/share table.
Data: `GET /stats/teacher-salaries`.

### PAGE: Salary (admin, editable payroll for ALL staff, not just teachers)
KEY: `#salary`
Purpose: Set/override monthly salary for every staff member (any role), mark "stajirovka" (internship = 0 pay), view teacher formula breakdown, revert an override back to auto-formula.
Components: KPI row (total salary/total paid/remaining) + progress bar, `data-table` with inline-edit-in-place amount cell, breakdown modal (teacher only).
Actions: edit salary amount inline, mark internship, revert to auto-calculated, view calculation breakdown.
Data: `GET /salary`, `PUT /salary/{user_id}`, `DELETE /salary/{user_id}/override`, `GET /salary/{user_id}/breakdown`.

### PAGE: Expenses
KEY: `#expenses` (shared entry for hunter and admin; hunter is read-only — `canManage = currentUser.role !== 'hunter'`)
Purpose: Log non-payroll/payroll-labeled operating expenses.
Components: month/year toolbar, `data-table` w/ footer total, create/edit modal with a "category" switch (Other / Staff salary → conditionally shows a staff picker).
Data: `GET/POST/PUT/DELETE /expenses`, `GET /expenses/staff-options`.

### PAGE: Tariffs (admin)
KEY: `#tariffs`
Purpose: CRUD monthly pricing plans consumed when assigning students to groups.
Data: `GET/POST/PUT/DELETE /tariffs`.

### PAGE: Courses (admin)
KEY: `#courses`
Purpose: CRUD course catalog entries (name, total lesson count, duration) used as an optional Group attribute.
Data: `GET/POST/PUT/DELETE /courses`.

### PAGE: Finance (admin)
KEY: `#finance`
Purpose: Per-group monthly collection-rate report — expected vs actual per active group, expandable to see unpaid (or all) students per group with attendance and per-student due amount.
Components: KPI row, collection-rate progress bar, expandable group cards, "show all vs unpaid-only" toggle per group.
Data: `GET /finance/monthly`, `GET /stats/export/excel`.

### PAGE: Discounts
KEY: not wired into any Sidebar button (component `Discounts.jsx` exists and `App.jsx` renders it at `#discounts`, but **no `onNavigate('discounts')` call exists anywhere in `Sidebar.jsx`** — this page is only reachable by manually typing `#discounts` in the browser address bar). CRUD for named percentage discounts.
Data: `GET/POST/PUT/DELETE /discounts`. **Note:** no route in `main.py` actually implements `/discounts` — grepped the full 194-route list, there is no `@app.get("/discounts"...)` anywhere. **This page's API calls will 404 in production.** Confirmed dead/broken feature.

### PAGE: Special (admin)
KEY: `#special`
Purpose: Per-student ad-hoc discounts that directly affect billing math (unlike the broken generic "Discounts" page): free-month / flat-monthly / one-time-amount.
Data: `GET/POST/PATCH/DELETE /special-discounts`, `GET /students`, `GET /groups`.

### PAGE: Teacher Dashboard
KEY: `#teacher_dashboard` (teacher role's home page)
Purpose: A teacher's personal cockpit — their groups, their salary calculation, their certificate-generation queue, student search.
Components: student-name search-as-you-type dropdown (jumps straight into a group), 3 KPI cards, tab bar (Guruhlarim/Maosh hisobi/Sertifikatlar), day-of-week filter, expandable group/salary breakdown cards, certificate list + generate modal + `GroupCertificates` viewer.
Data: `GET /teacher/dashboard`, `GET /salary/me`, `GET /salary/{id}/breakdown`, `GET /teacher/certificates`, `GET /groups/{id}/certificates`, `POST /groups/{id}/certificates/generate`.
Note: entirely styled with **inline `style={{}}` objects** (110 occurrences, the highest of any file) — completely bypasses `styles.css` and the theme system (hardcoded hex like `#111827`, `#6b7280`, `#eef2ff`). **Does not respect dark/ocean theme at all** — a teacher who switches to dark mode gets a jarring white dashboard while the rest of the app (sidebar, other pages) goes dark. Major finding, see Problem #1.

### PAGE: Today's Attendance
KEY: `#today_attendance`
Purpose: Fast daily roll-call across all of today's (or any admin-picked date's) scheduled groups; separate from Group Detail's full monthly grid.
Components: date picker (admin only; teacher locked to today), holiday banner + holiday-management modal (superadmin only), card grid of today's groups (shows "done"/"pending" badge), tap-in attendance screen (list of students, tap-to-toggle present/absent, "mark all" shortcuts).
Data: `GET /attendance/today`, `GET /groups/{id}/attendance`, `POST /groups/{id}/attendance/{date}`, `GET/POST/DELETE /holidays`.

### PAGE: Academic
KEY: `#academic`
Purpose: 5-tab hub: Grades, Coins (a gamified reward-point system), Feedback (teacher comments visible to parents), Certificates (simple PDF-link records, distinct from the group certificate designer), Events (academy-wide events shown to parents).
Components: tab bar, student filter dropdown, coin-wallet balance widget with monthly auto-refill note, per-tab table, per-tab create/edit modal, PDF upload button (certificates tab), coin leaderboard (top 10, medal emoji for top 3).
Actions vary per tab: add/edit/delete grade; give/deduct coins (deduct = admin only) + cancel a coin transaction (own or admin); add/edit/delete feedback; add/edit/delete certificate + upload PDF; add/edit/delete/toggle-visibility event (admin only).
Data: `GET /academic/options`, `GET/POST/PATCH/DELETE /grades`, `GET/POST/DELETE /coins/give|deduct|transactions|totals` (`/coins/summary`, `/coins/give`, `/coins/deduct`, `/coins/transactions`, `/coins/totals`, `DELETE /coins/transactions/{id}`), `GET/POST/PATCH/DELETE /teacher-feedbacks`, `POST /certificates/upload`, `GET/POST/PATCH/DELETE /certificates`, `GET/POST/PATCH/DELETE /events`.

### PAGE: Feedback Inbox
KEY: `#feedbacks` (admin + call_center)
Purpose: Triage queue for teacher comments about students that need parent follow-up (distinct from the Academic tab's raw feedback CRUD — this is a status workflow: new → resolved / no_answer).
Data: `GET /teacher-feedbacks`, `PATCH /teacher-feedbacks/{id}/status`.

### PAGE: Notifications (misleadingly named — actually "Student Visit Log")
KEY: `#notifications`
Purpose: Manually log a student's physical arrival/departure at the center and push a Telegram notification to their parent; shows today's visit history.
Components: searchable student table with photo-upload-per-row, Keldi/Ketdi (arrived/left) action buttons, today's-history table.
Data: `GET /students`, `GET/POST /visits`, `POST /students/{id}/photo`.
Note: this is unrelated to the `NotificationBell` dropdown inside the Leads page (`GET /notifications`) — **two completely different features share the Uzbek/English word "Notifications"**, one is a sidebar page (visit log) and one is a bell icon inside Leads (system notifications: new lead assigned, reminder due, etc.). Naming collision flagged in Problem list.

### PAGE: ChatBot (Telegram inbox viewer)
KEY: `#chatbot` (hunter + admin)
Purpose: Read-only viewer of all Telegram bot conversations (students/staff/unknown), for verifying automated message delivery.
Components: two-pane layout — chat list (search, live-updating badges) + message thread (day dividers, delivery-status icons), polls every 5–15s.
Data: `GET /bot/chats`, `GET /bot/chats/{id}/messages`.

### PAGE: Parents
KEY: `#parents` (hunter + admin manage; both can broadcast)
Purpose: Create/manage parent login accounts for a separate mobile app; link/unlink children; reset passwords; broadcast Telegram messages to all parents.
Components: search, `data-table`, create-account modal (multi-select children checklist), one-time credentials-reveal modal, link-child modal, broadcast modal.
Data: `GET/POST/PATCH /parents`, `POST /parents/{id}/reset-password`, `POST/DELETE /parents/{id}/children(/{student_id})`, `POST /parents/broadcast`, `GET /students`.

### PAGE: Users (admin — staff accounts, distinct from Parents)
KEY: `#users`
Purpose: CRUD internal staff logins/roles, block/unblock, permanent delete, Telegram broadcast to staff.
Components: search, `data-table` with colored role pills + status badge (active/blocked/expired/inactive), create/edit modal, block modal (reason+contact required), permanent-delete confirm modal (typed-name-style double confirm via plain `confirm()`), broadcast modal.
Data: `GET/POST/PUT /users`, `POST /users/{id}/block|unblock`, `DELETE /users/{id}/permanent`, `POST /users/broadcast`.
Note: uses the **unstyled `.form-input`/`.form-label`** class set — see Design System Audit / Problem #3.

### PAGE: Employees (audit + admin)
KEY: `#employees`
Purpose: Staff directory scoped to the Audit workflow — link a staff member's Telegram chat ID (for warning delivery) and launch the warning modal.
Data: `GET /staff-options`, `PATCH /staff-options/{id}/telegram`, `GET /discipline-codes`.

### PAGE: Audit Warnings
KEY: `#audit_warnings` (audit + admin)
Purpose: Full log of formal warnings/fines issued to staff; resend failed Telegram deliveries; admin can cancel a warning.
Data: `GET /staff-warnings`, `POST /staff-warnings`, `POST /staff-warnings/{id}/resend|cancel`.

### PAGE: My Warnings
KEY: `#my_warnings` (every non-admin/audit role)
Purpose: Self-service view of warnings issued to the logged-in user.
Data: `GET /staff-warnings/mine`.

### PAGE: Bot Admin (admin only)
KEY: `#bot_admin`
Purpose: Administer the separate Telegram bot's own database (employees/roles/settings/admin-tier/investor broadcast automation) — note this operates on `bot.db`, a different datastore from the main app's users table.
Components: 5-tab hub: Employees (assign bot "roles" to Telegram users), Roles (CRUD custom bot roles, mark as "parent role"), Settings (default parent chat ID), Admin/CEO (promote/demote bot admins, generate one-time admin invite links), Investors (configure/trigger automated daily investor stats broadcasts + new-student-enrolled pings).
Data: `GET /bot/employees`, `GET/POST /bot/roles`, `PATCH /bot/roles/{id}/toggle`, `POST /bot/employees/{id}/role`, `POST /bot/employees/{id}/admin`, `GET/PUT /bot/settings/{key}`, `POST /bot/investor/send-now`, `POST /bot/invite-links`.

---

# 5. Navigation Structure

The sidebar (`Sidebar.jsx`, 523 lines) is entirely role-conditional — sections and buttons are wrapped in JS boolean checks, not a declarative config, so understanding "who sees what" requires reading the JSX. Reconstructed here:

| Sidebar section | Visible to | Buttons |
|---|---|---|
| **Metodika** | everyone except hunter/sales/call_center/audit | Dars rejalari (Lessons) → expands a Foundation/Frontend/Backend sub-list |
| **Narxlar** | hunter only | To'lovlar (Payments) |
| **Mening panelim** | teacher only | Mening guruhlarim (Teacher Dashboard) |
| **CRM** | hunter, sales, call_center, admin | Lidlar (Leads) · Notifications · Chatbot (hunter/admin only) · Izohlar/Feedback (call_center/admin only, with a live unread-count red badge) · Ota-onalar/Parents (hunter/admin only) · Xarajatlar/Expenses (hunter only) |
| **Akademik** | everyone except call_center/sales/audit/hunter | Baholar va izohlar (Academic) |
| **Davomat** | everyone except audit | Bugungi darslar (Today's Attendance) |
| **Audit** | audit, admin | Xodimlar (Employees) · Ogohlantirishlar (Audit Warnings) |
| **Mening** | everyone except audit/admin | Ogohlantirishlarim (My Warnings) |
| **LMS** | support_teacher, hunter, sales, call_center (i.e. everyone with `hasCrmAccess` or is metodist) | Talabalar (Students) · Guruhlar (Groups) |
| **Moliya** | admin only | Moliya (Finance) · To'lovlar (Payments) · Tariflar · Kurslar · Special · O'qituvchi maoshi (Teacher Salaries) · Ish haqi (Salary) · Xarajatlar (Expenses) · Dashboard |
| **Boshqaruv** | admin only | Foydalanuvchilar (Users) · Bot boshqaruvi (Bot Admin) |

Fixed footer (all users): avatar (click to open file picker + inline "edit profile" pencil → modal with name + password-change fields), theme switcher (3 dots: light/dark/ocean), Chiqish (logout).

The **"Discounts"** page (`#discounts`) is never linked from any sidebar button — dead/orphaned navigation, see §4.

A `PAGE_ACCESS` allow-list also exists in `App.jsx` (duplicating the Sidebar's visibility logic in a second place) that redirects a user to their role's default landing page if they land on a hash they're not permitted to see (stale bookmark, typed URL, etc.) — e.g. teacher → `teacher_dashboard`, hunter → `payments`, sales/call_center → `leads`, audit → `employees`, everyone else → `lessons`. This means **role-based access control is duplicated in two separate hand-maintained JS objects** (`Sidebar.jsx`'s many boolean flags + `App.jsx`'s `PAGE_ACCESS`/`DEFAULT_PAGE_BY_ROLE` maps) that must be kept in sync manually — a real maintenance risk, not just a redesign concern.

---

# 6. Dashboard Analysis

(admin-only screen, `#dashboard`, backed by `GET /stats/overview` + inline expense CRUD)

**What the admin sees, top to bottom:**
1. **Header row:** page title + year `<select>` (current year ±2) + "Excel" export button.
2. **KPI grid (4 cards, `.kpi-grid`):**
   - "Jami talabalar" (total students) with sub-line "Faol: N" (active count)
   - "Guruhlar" (total groups) with sub-line "Faol: N"
   - "Bu oy tushum" (this-month income, `.highlight` styled card) with a colored trend indicator (▲/▼ + % vs last month)
   - "O'tgan oy tushum" (last-month income, plain number)
3. **"Bu oy moliyaviy natija" (This month's P&L) — 5-card row**, each with a colored top border and colored value text:
   - Umumiy tushum (total income, green)
   - O'qituvchi maoshi ↗ (teacher salary total, blue, **clickable → navigates to Teacher Salaries**)
   - Tashqi xarajatlar ↗ (external expenses total, amber, **clickable → navigates to Expenses**)
   - Umumiy chiqim (total expenses = teacher salary + external, red)
   - Sof foyda (net profit, green if positive/red if negative, background tint changes too, largest/boldest number on the page)
4. **"Tashqi xarajatlar" (external expenses) card:** month/year selector + "Qo'shish" button, inline editable table (name/amount/actions), footer row with the month's total. Fully functional CRUD embedded directly in the dashboard (not just a summary — this *is* one of the two places you can manage expenses, the other being the standalone Expenses page).
5. **Annual bar chart** (`.bar-chart`, hand-built with `<div>` height percentages, not a charting library): one bar per month of the selected year, current month highlighted (`.bar-current` class), value label above each bar in "Nk" (thousands) shorthand, hover title shows full income + net profit.
6. **Full monthly history table** (reverse-chronological): Oy / Tushum / O'qt. maoshi / Tashqi xarajat / Jami chiqim / Sof foyda / To'lovlar-count — 7 columns, color-coded per column type matching the P&L cards above.

No filters beyond year; no per-group or per-course breakdown on this screen (that granularity lives on the separate Finance page). No loading skeletons — a single centered "Yuklanmoqda..." text replaces the whole page while loading.

---

# 7. Leads Module (full workflow)

**Lead statuses (legacy enum, `backend/models.py LeadStatus`):** `new` → `called` → `will_come` / `callback` → `enrolled` / `rejected`. **However** the UI does **not** primarily use this fixed enum — it uses a fully custom, admin-configurable **pipeline of `LeadStage` records** (name/color/icon/order/`kind` ∈ {lead, won, lost}), kept loosely in sync with `status` on the backend. Default seeded stages (from `LeadStage` comments/`DEFAULT_STAGES` in `main.py`): Yangi (new) → Qo'ng'iroq qilindi (called) → Qayta qo'ng'iroq (callback, 1hr) → Keladi (will_come) → Demo → To'landi (enrolled, `kind=won`) → Rad etildi (rejected, `kind=lost`).

**Lead sources (`LeadSource` table, admin-managed, not hardcoded):** examples seeded: Instagram, Telegram, Walk-in (default), Website, Referral, Qo'ng'iroq, Boshqa. A source can be flagged `is_campaign` and can carry a `referrer_id` (staff member auto-credited when leads from that source convert — powers the "Referral funnel" analytics).

**Filters/search:** free-text search (name/phone, debounced 300ms + `/` keyboard shortcut focuses it + Enter forces immediate search), source dropdown, "Umumiy havza" (shared pool = unclaimed leads) toggle, "Bugun" (today, only for hunter/call_center — leads with a callback due today) toggle. Active filters render as removable chips with a "Tozalash" (clear all) button.

**Views:** Board (Kanban, default) / Ro'yxat (List/table) / Analitika (Analytics) — a 3-way tab strip that's keyboard-navigable (arrow keys) and ARIA-tabbed (the *only* component in the whole app with real `role="tab"`/`aria-selected` wiring).

**Kanban board:** one column per active (non-archived) pipeline stage, drag-and-drop cards between columns (native HTML5 DnD, `canMove`-gated by role), each card shows name, phone, shared/claimed badges, course/source/interested-group tags, owner name (role-gated visibility), callback time OR created time, a 2-line-clamped notes preview, a 2-line-clamped "next reminder" preview, and (if in the shared pool) a "Band qilish" (claim) button with an inline spinner state. Empty columns show an inbox icon + hint text. A full skeleton-loading state mirrors the kanban structure (the only skeleton loader in the entire app — every other page just shows "Yuklanmoqda...").

**List view:** table with # / Name / Phone / Source / Stage badge / Time-or-note / (Hunter column, role-gated) / Actions (open, delete-if-permitted). Clicking a row opens the same drawer as a kanban card click.

**Lead detail drawer** (slide-over panel, full focus-trap + Escape-to-close — the only place besides the Add Lead modal with real accessibility keyboard handling): phone + tap-to-call link, tag row (course/source/interested group/claimed-by/created-by), rich fields (DOB, 2 parent phones) if present, Claim/Release buttons, **stage-picker as a grid of colored pill buttons** (not a dropdown), a callback datetime input, notes (read-only display), a full Reminders sub-section (list + inline add form + mark-done), and a full Tarix (activity timeline, read-only, auto-generated server-side on every stage change).

**Actions available:** create lead (modal with 8 fields: name*, phone*, course interest, source, DOB, interested group, 2 parent phones, notes), move stage (drag or click in drawer), claim/release/share a pool lead, delete (hunter/sales/admin only), add/complete reminders, set callback time.

**Modals/drawers:** Add Lead modal · Lead Drawer (side panel) · Stage Manager modal (admin: reorder via ▲▼ buttons, recolor via a 14-swatch picker, set kind, delete) · Intake Form Manager modal (admin: create public form links, copy-to-clipboard, toggle active, delete, shows submission counts) · full-screen **Funnel Board** (a custom pannable/zoomable canvas — pointer-drag nodes, ctrl+wheel or pinch to zoom, wheel to pan, positions persisted to `localStorage`, click a node to open a side panel listing the matching leads) reachable from Analytics → a referrer's "To'liq sxema" button.

**Analytics tab:** 4 top-line tiles (total/won/lost/conversion%) → stage-distribution horizontal bar list → source-conversion table (rate pill colored green ≥30%, else amber) → **Comment Stats** panel (total comments, first/last comment date, busiest month, monthly bar chart, per-author leaderboard table) → **Referral** section per referring staff member: funnel chip row (5 stages: Kelgan/Bekor qilindi/Kutilmoqda/Kelmoqchi/To'landi) + monthly dual-bar chart (leads vs paid) + "To'liq sxema" button opening the Funnel Board.

---

# 8. Students Module

**List** (`#students`): 3-tab state model (Demo / Faol / Arxiv) rather than filter checkboxes — architecturally, "demo" and "archived" are just boolean flags on the same `Student` row, but the UI treats them as three mutually-exclusive views with separate empty-states and separate available row-actions per tab. Search (2-char minimum before firing, or empty to reset), `DateFilter` (created-date presets), server-side pagination (20/page). Columns: # / Full name / Phone / Parent (father+mother name+phone combined into one cell) / Telegram (badge + a "send test message" button that flips badge color amber on failure) / Groups (badge chips) / Payment-status (clickable to open Vacation modal, for hunter/admin) / Created / Updated / Status badge / Actions (view, attendance-history, tab-specific: mark-demo+toggle-active+archive for active tab, attach-to-group+unmark-demo for demo tab, unarchive for archived tab).

**Student Detail** (`#student_detail`): left sidebar = avatar+photo-upload, contact card, groups badge list, (demo only) group-attach card, quick-actions card (demo toggle, active toggle, archive toggle). Right main = 4-tab panel: Ma'lumotlar (editable info form, all fields from `StudentCreate`/`StudentUpdate` schema: full_name*, phone1*, father/mother name+phone, telegram_user_id, notes), To'lov (this-month payment summary: owed/paid/advance/debt + recent-payments list), Davomat (camera attendance table, 4 day-range filters), Ta'til (vacation CRUD, hunter/admin only).

**Forms:** Add Student modal (10 fields incl. Telegram ID flagged "*muhim*" = important, since it's the delivery channel for all automated parent notifications), Student Detail's inline edit form (same field set minus advance/demo, those are admin-only via a separate endpoint field not exposed in any form UI), Vacation modal (start/end date + reason, with client-side date-order validation), Attach-to-Group modal (single group `<select>`).

---

# 9. Groups Module

**List** (`#groups`): card grid (not a table) — each `.group-card` shows name, course/stage badge, active/archived status badge, teacher name, price, schedule, student count badge, and a **progress bar** (lessons completed / total, color escalates blue→amber→red as it nears 100%, plus a "N dars qoldi ⚠" warning under 5 remaining or "Tugadi ✓" at completion). Filters: status tabs (Faol/Arxiv/Hammasi), day-of-week filter (Barchasi/Juft kunlar/Toq kunlar — "even days"/"odd days", a peculiar twice-a-week scheduling convention specific to this school), `DateFilter`, pagination. Card actions (stop-propagation'd from the card's own click-to-open): Talabalar (opens a lightweight roster modal, separate from full Group Detail), Tahrir (edit), Arxivlash/Arxivdan chiqarish (archive toggle, with a confirm warning that archived groups vanish from finance/salary/debt reports).

**Group creation/edit modal:** name*, stage (Foundation/Fullstack — note: only 2 of the 4 stage values defined in `STAGE_LABELS`/`STAGE_COLORS` are actually selectable in this dropdown; Frontend/Backend stages exist in styling and backend data but have no UI path to be *set* on a new group, likely legacy from an early curriculum restructure), teacher, **Tarif*** (tariff dropdown auto-fills course_price, price itself is never manually typed), schedule (Juft/Toq kunlar dropdown), lesson time, start date, Telegram chat ID (for homework auto-send).

**Teacher assignment:** single `teacher_id` dropdown pulling from `GET /teachers` (all users with role=teacher) inside the same create/edit modal — no separate "assign teacher" flow.

**Student assignment:** two separate UIs exist for the same operation (add/remove a `GroupStudent` row with a tariff): (1) the lightweight roster modal on the Groups list page, (2) implicitly via Student Detail's "attach to group" card for demo students. Group Detail itself (the full page) does **not** have an add/remove-student UI — that's arguably a gap, since the richest group view has no roster management, only attendance/homework/certs.

**Group Detail page:** see full breakdown in §4. Key point: it's the single richest screen in the app — attendance grid, camera log tab, "today's lesson from curriculum" card with one-click homework send, and a full certificate-generation/print workflow (`GroupCertificates.jsx`, see below).

---

# 10. Attendance Module

Three separate attendance surfaces exist, each solving a different use case:

1. **Group Detail's monthly grid** (`GroupDetail.jsx`, tab "Yo'qlama"): a spreadsheet-like table, one row per student, one column per **calendar day of the selected month**. Columns for days that aren't lesson days (per the group's weekly schedule) render as non-interactive greyed cells; columns for actual lesson dates are clickable and cycle present(✓)/absent(✗)/unmarked(–) on click. A "Dars qo'shish" (add lesson date) control validates the picked date against the group's weekly schedule before allowing save. Each lesson-date column header has a delete-date button (removes all attendance rows for that date, confirm-gated). A legend explains the 3 cell states + the "scheduled day" highlight color. Right-side stat cards show monthly completion %, remaining lessons, and average attendance %.

2. **Today's Attendance** (`TodayAttendance.jsx`, `#today_attendance`): a fast daily-roll-call UI, not tied to the current calendar month grid — shows only groups scheduled for the selected date (admin can pick any date; teacher locked to today), each as a card with a "Bajarildi"/"Kutilmoqda" (done/pending) badge. Tapping a card opens a full-bleed tap-list (not a grid) where every student is one big colored row you tap to flip present/absent, plus "mark all present/absent" shortcuts and a live present/absent counter. Admin (superadmin specifically — `isSuperAdmin`, i.e. `role==='admin'`) also manages **Holidays** here (a modal: name + date range, deleted holidays list) that surface as a banner warning on the selected date if it falls inside a holiday range.

3. **Camera attendance** (read-only, face-recognition-driven, populated by an external `camera/` service hitting `POST /camera/checkin`): surfaced as a tab inside Group Detail ("Kamera davomati"), inside Student Detail ("Davomat" tab), and inside the Students list (per-row modal) — always the same shape: a 4-range-filter (7/14/30/90 days, or 1-day for the group version) table of arrived/left events with date/day-name/time/status-badge.

**Actions:** toggle a single cell (click-cycle), bulk-mark-all in Today's Attendance, add/delete a lesson date, manage holidays (superadmin).

---

# 11. Payments/Finance Module

This is really **6 distinct sub-areas** sharing money-related data:

- **Payments** (`#payments`): the transactional ledger — see §4 for full detail. Central concept: for a given (student, group, month, year), the system computes `expected` (tariff price, adjusted for vacations/special-discounts via `core_calc.py`), `paid` (sum of Payment rows), `remaining`, and a `status` of paid/partial. A `via_sales` boolean flags a payment as sales-role-attributed (feeds referral-conversion stats). Debtors sub-view sorts by debt descending and offers one-click "To'liq to'lash" (pay-in-full).
- **Debt management:** no dedicated page — debt is a derived field (`payment_status`: paid/partial/debtor/none, `debt` amount) computed server-side and surfaced in the Students list, Student Detail, Payments' Debtors view, and Finance page.
- **Finance** (`#finance`): per-group monthly collection health (expected/actual/deficit), expandable to unpaid-or-all student lists per group with per-student attendance-vs-due breakdown.
- **Discounts:** `Discounts.jsx` (generic named % discounts) is **orphaned/broken** — not linked in Sidebar and its backend routes don't exist (404 in production, confirmed by absence in the 194-route grep). `Special.jsx` (per-student ad-hoc discounts: free-month/monthly-flat/one-time) is the actually-functional discount mechanism and **does** directly affect payment math.
- **Reports:** Excel export (`GET /stats/export/excel`, month/year params) available from Dashboard/Finance/Payments. Printable payment receipts (`GET /payments/{id}/receipt`, opens as HTML in a new tab, short-lived download-token auth to avoid putting the long-lived bearer token in a URL).
- **Salary payroll:** covered under Users & Roles-adjacent but functionally a finance concern — `Salary.jsx` (editable, all staff), `TeacherSalaries.jsx` (read-only, teacher formula drill-down), `TeacherDashboard.jsx`'s own "Maosh hisobi" tab (self-service version of the same formula breakdown for the logged-in teacher).

**Payment formula summary (from UI copy, `core_calc.py` not read in full but formula strings appear verbatim in 3 components):** teacher salary = fixed base (5,000,000 so'm) **+** a per-student-per-lesson share, where each group's 50,000 so'm "pool" is divided by that month's held-lesson-count to get a per-lesson rate, multiplied by how many lessons each student actually attended.

---

# 12. Users & Roles

**Role list (7):** admin, support_teacher, teacher, hunter, sales, call_center, audit — see the table in §1 for descriptions. Stored as a plain string enum on `User.role` (not a separate permissions table — **no granular permission system**, access is 100% role-name-based, hardcoded into `Sidebar.jsx` and `App.jsx`'s `PAGE_ACCESS` map, and independently re-checked server-side per endpoint in `main.py` — three separate places encode "who can do X").

**Role hierarchy / access summary:**
- **admin** — unrestricted; only role with Finance section, Users, Bot Admin, Dashboard, Salary editing, Discounts/Special/Courses/Tariffs.
- **support_teacher** ("metodist") — Lessons CRUD, Students/Groups (LMS), Academic, Attendance; no CRM, no finance.
- **teacher** — read-only Lessons, own Groups only (via Teacher Dashboard + Group Detail with teacher-scoped checks), own salary, coins, Academic (grading own students), Attendance for own groups.
- **hunter** — the "do-everything sales closer" role: Leads, Students/Groups, Payments, Expenses, Parents, Chatbot, Attendance; notably **also has finance visibility** (Payments, Expenses) that sales/call_center don't.
- **sales** — Leads + Students/Groups only, explicitly **no finance** (comment in `Sidebar.jsx`: "moliya yo'q").
- **call_center** — Leads, Students/Groups, Feedback Inbox, Notifications (visit log), Attendance; no Chatbot, no Parents, no finance.
- **audit** — completely separate track: Employees + Warnings only, cannot see Lessons/Students/Groups/CRM/Attendance/Academic at all.

**Users page** (admin, `#users`) manages **staff** accounts: username, full name, password, role dropdown (all 7), expiry date (optional — "cheksiz"/unlimited if blank), Telegram chat ID (for audit-warning delivery), block (reason+contact, freeform text, shown to the user on their login screen), unblock, permanent delete (hard-deletes the user row; a footnote clarifies related records like payments/leads are NOT deleted, just their "who did this" backup is archived server-side to a file), and a Telegram broadcast-to-all-staff tool.

**Parents** (hunter/admin, `#parents`) is a **completely separate account system** for the external parent mobile app — different table (`Parent`, not `User`), different auth (implied separate JWT/refresh-token flow given `ParentRefreshToken` table, though no parent-login UI exists in this web app since parents use the mobile app), auto-generated username (defaults to phone) and password (auto-generated, shown once).

---

# 13. Forms

Every distinct form in the app, with fields and validation source (`schemas.py` Pydantic constraints where applicable):

1. **Login** — username*, password*. No client validation beyond `required`.
2. **Public Intake** — full_name* (≥2 chars), phone* (≥7 chars), course_interest (select), parent_phone, notes. Client checks name/phone length before submit; server re-validates via `PublicLeadSubmit`.
3. **Profile edit** (Sidebar avatar-pencil modal) — full_name, current_password, new password (≥8 chars, client-checked), confirm password (must match, client-checked). `ProfileUpdate` schema server-side.
4. **Add Lesson** — lesson_number* (positive int, uniqueness checked client-side against existing numbers), title* (≥1 char), section. `LessonCreate` schema.
5. **Lesson edit (inline)** — section, guide, homework, extra_notes — all optional freeform textareas.
6. **Add/Edit Lead** — full_name* (2–200 chars), phone* (7–30 chars), course_interest, source_id, date_of_birth, parent_phone, parent2_phone, interested_group_id, notes. `LeadCreate` schema.
7. **Lead stage move (drawer)** — stage selection (pill grid) + optional callback datetime.
8. **Reminder create** — due_at* (datetime), body, kind (fixed to "call" in UI though schema allows call/visit/other), assigned_to_id (not exposed in UI — always self).
9. **Lead Stage create/edit** (admin) — name* (1–80 chars), color (swatch picker, 14 options), kind (lead/won/lost select), is_archived (implicit via delete... actually there's no archive toggle in the UI, only hard delete).
10. **Intake Form create** (admin) — name* (1–150), title, description, source_id.
11. **Add/Edit Student** — full_name* (2–200), phone1* (7–20), father_name/phone, mother_name/phone, telegram_user_id (flagged important), notes. `StudentCreate`/`StudentUpdate`.
12. **Vacation** (student) — start_date*, end_date* (must be ≥ start, client + server `@validator`), reason.
13. **Attach-to-Group** — group_id* (select).
14. **Add/Edit Group** — name* (2–200), stage (select, only 2 of 4 options exposed), teacher_id, tariff_id* (drives course_price), schedule (Juft/Toq kunlar select), lesson_time (HH:MM regex-validated server-side), start_date, telegram_chat_id.
15. **Homework send** (Group Detail) — text* (freeform, min 2 chars server-side), auto-linked to the curriculum's "next lesson" if available.
16. **Certificate generate** (Group Detail / Teacher Dashboard) — course_label, issue_date (freeform string, not a date picker — placeholder shows a specific format "03.09.2026"), signer_name (defaults to "Sharifjon Mo'minov"), signer_title (fixed "CEO").
17. **Certificate inline edit** (`GroupCertificates.jsx`) — every field (student name, cert number, course label, issue date, signer name) is a `contentEditable` div directly on the printable certificate artwork, saved on blur — an unusual and fairly elegant WYSIWYG pattern, but with zero visual "editing mode" affordance (no border/highlight to signal editability beyond a subtle bottom-border on the name field only).
18. **Add/Edit Payment** — student_id* (locked once editing), group_id* (locked once editing), amount* (>0), month*, year* (≥2020), notes, via_sales toggle. Live "expected/paid/remaining" preview computed via a side-effect API call as fields change.
19. **Add/Edit Expense** (both Dashboard-inline and standalone Expenses page — two separate implementations of essentially the same form) — name*, amount* (>0), category (Other/Staff-salary select), staff_id (conditional, required if category=salary).
20. **Add/Edit Course** — name* (2–200), description, total_lessons* (≥1), duration_months (≥1).
21. **Add/Edit Tariff** — name* (2–200), price* (>0), description.
22. **Add/Edit Discount** (orphaned/broken page) — name*, percent* (1–100), description.
23. **Add Special Discount** — student_id*, group_id (optional = "all groups"), kind* (one_time/monthly/free_month select, conditionally reveals amount and/or month+year fields), reason.
24. **Salary inline edit** — a single numeric input replacing the display cell.
25. **Add/Edit User** — username* (create only), full_name, password (≥8 chars, optional on edit = "leave blank to keep"), role* (7-option select), expires_at, telegram_chat_id.
26. **Block User** — reason* (≥3 chars), contact* (≥3 chars).
27. **Broadcast** (Users / Parents — two near-identical implementations) — text* (1–4000 chars textarea).
28. **Add/Edit Parent Account** — full_name* (2–200), phone* (7–30), username (optional, defaults to phone), password (optional, ≥6 chars, defaults to auto-generated), student_ids* (multi-select checklist, ≥1 required).
29. **Grade** — student_id* (cascades from a group_id select), subject* (1–200), score* (≥0), max_score (default 100), exam_type (exam/test/quiz/project select), exam_date, comment.
30. **Coin give/deduct** — student_id* (cascades from group), amount* (1–1000 give / 1–100000 deduct), reason.
31. **Feedback (teacher comment)** — student_id* (cascades from group), comment* (≥2 chars).
32. **Certificate (simple, Academic tab)** — student_id*, title* (2–300), file_url* (2–500, via PDF-upload button OR manual URL paste), issued_at.
33. **Event** — title* (2–300), description, event_date* + event_time (split into two inputs, joined on submit), location.
34. **Staff Warning** (`StaffWarningModal.jsx`, shared by Audit Warnings + Employees pages) — staff_id*, mode toggle (Kodeksdan/freeform), discipline_code_id* (grouped `<optgroup>` by severity: gray/yellow/red) **or** severity*+reason* (freeform).
35. **Telegram link** (Employees) — telegram_chat_id (freeform text with instructions to have the staff member DM the bot `/idyubor`).
36. **Bot Role create** — name* (1–64), is_parent checkbox.
37. **Bot Settings** — single freeform text value per setting key (default_parent_chat_id, investor_chat_id, etc.) — no schema/typed form, just raw key-value text inputs.
38. **Bot Admin promote/invite-link** — employee select + tier select (admin/superadmin).
39. **Holiday** — name* (2–300), start_date*, end_date* (must be ≥ start).
40. **Attendance save** — not a traditional form; a click-driven state machine (see §10).

---

# 14. Tables

Every distinct data table (`.data-table` class unless noted):

1. **Lessons list** — not a table, a card-list (`LessonList.jsx`) with reorder arrows, no sort/filter beyond the sidebar category tabs.
2. **Audit Log panel** — list-style (not `<table>`), filterable by `DateFilter`, no pagination (fixed page_size 100), no column sort.
3. **Leads List view** — # / Ism Familiya / Telefon / Manba / Bosqich / Vaqt-Izoh / (Hunter, role-gated) / Amallar. No column sort, no client pagination (all leads loaded at once — could be a scale concern), server-side search+source filter only.
4. **Students list** — 11 columns (see §8). Search + date-range filter, server pagination (20/page), no column sorting.
5. **Groups** — rendered as cards, not a table.
6. **Group Detail attendance grid** — dynamic column-per-day, described in §10, no pagination (whole month always rendered), no sort (row order = server order).
7. **Group Detail student summary** (sidebar list) — not a `<table>`, styled divs.
8. **Group roster modal table** (Groups list) — # / Name / Phone / Tariff / Joined / Remove-action. No sort/filter/pagination.
9. **Payments list** — 9 columns (§4), month/year+date-range filter, server pagination (25/page), no sort.
10. **Payments Debtors view** — 7 columns, sorted server-side by debt descending, no pagination (all debtors for the month loaded at once), no client filter beyond the shared month/year picker.
11. **Dashboard expenses (inline)** — 3 columns + footer total, no filter beyond month/year, no pagination.
12. **Dashboard monthly history** — 7 columns, full year always shown, no pagination, no sort (fixed reverse-chronological).
13. **Finance per-group breakdown** — expandable, no pagination, toggle between "unpaid only" / "all".
14. **Teacher Salaries** — nested expandable (teacher→group→student), no pagination, no sort.
15. **Salary (editable)** — 6 columns, inline-edit cell, no pagination, no sort.
16. **Expenses standalone** — 6–7 columns (role-conditional actions column), month/year filter, footer total, no pagination, no sort.
17. **Tariffs** — 6 columns, no filter/sort/pagination.
18. **Courses** — 6 columns, no filter/sort/pagination.
19. **Discounts** (broken page) — 5 columns.
20. **Special discounts** — 8 columns, no filter/sort/pagination.
21. **Academic → Grades tab** — 9 columns, filtered by student dropdown only.
22. **Academic → Coins tab** — 8 columns + separate leaderboard table (top 10, medal icons for top 3).
23. **Academic → Feedback tab** — 7 columns.
24. **Academic → Certificates tab** — 7 columns.
25. **Academic → Events tab** — 7 columns (6 for non-admin, actions column hidden).
26. **Feedback Inbox** — not a table, a card-list with status tabs (New/No-answer/Resolved/All).
27. **Notifications (visit log) main table** — 5 columns (photo/name/telegram/last-status/actions), search only.
28. **Notifications today-history table** — 5 columns, no filter (always today).
29. **ChatBot chat list** — not a `<table>`, a card-list, live-search.
30. **Parents** — 7 columns (6 for non-managers), search, no pagination/sort.
31. **Users** — 7 columns, client-side search filter only (all users loaded), no pagination/sort.
32. **Employees (audit)** — 6 columns, no filter/pagination/sort.
33. **Audit Warnings** — 8 columns, filterable by staff dropdown, no pagination/sort.
34. **My Warnings** — 6 columns, no filter.
35. **Bot Admin → Employees tab** — 5 columns.
36. **Bot Admin → Roles tab** — 5 columns.
37. **Bot Admin → Admins tab** — 4 columns.
38. **Today's Attendance groups grid** — cards, not a table.
39. **Today's Attendance tap-list** — styled div rows, not a table.
40. **Student Detail camera-attendance table** — 4 columns, 4-way day-range filter.
41. **Student Detail recent-payments** — styled list, not `<table>`.
42. **Salary breakdown modal table** — 6 columns.
43. **Teacher Dashboard salary breakdown table** — 3 columns, inline-styled (not `.data-table`).

**Cross-cutting observation:** a generic `Pagination.jsx` component exists (page-window with ellipses, first/prev/next/last buttons, "X–Y / Z ta" count label) but is only wired into **4 of ~35 tabular views** (Students, Groups, Payments-list, — that's it). Every other table that could grow large (Users, Leads-list, Debtors, Warnings, Parents) loads everything client-side with no pagination and no column sorting anywhere in the entire app.

---

# 15. Modals & Drawers

**Full-screen/overlay drawers (side panel):** Lead Drawer (`Leads.jsx`), Funnel Board (`Leads.jsx`, full-screen pannable canvas, not a modal), Group Certificates viewer (`GroupCertificates.jsx`, full-screen printable designer).

**Standard centered `.modal` dialogs** (all share the same `.modal-overlay`/`.modal-header`/`.modal-body`/`.modal-footer` structure, click-outside-to-close, ✕ button, no ARIA `role="dialog"`/`aria-modal` except the Leads drawer and Add-Lead modal which use the custom `useFocusTrap` hook):
- Profile edit (Sidebar)
- Add Lesson
- Add/Edit Lead
- Stage Manager (admin)
- Intake Form Manager (admin)
- Add/Edit Student
- Vacation (uses a plain `window.confirm()` for delete, not a modal)
- Attach-to-Group
- Add/Edit Group
- Group roster ("Talabalar") — a `.modal-lg` variant
- Homework send
- Certificate generate (settings)
- Add/Edit Payment
- Add/Edit Expense (two independent implementations — Dashboard inline + standalone page)
- Add/Edit Course
- Add/Edit Tariff
- Add/Edit Discount
- Add Special Discount
- Salary breakdown (uses raw inline `style={{...}}` for its overlay/box instead of the `.modal`/`.modal-overlay` classes — a one-off reimplementation)
- Add/Edit User
- Block User
- Permanent Delete User (danger-styled footer button)
- Broadcast (Users + Parents, near-duplicate implementations)
- Add/Edit Parent Account
- One-time Credentials Reveal (Parents) — copy-to-clipboard buttons per field + "copy all"
- Link Child (Parents)
- Grade / Feedback / Certificate / Event / Coin (Academic — one shared modal shell, content switches by active tab)
- Staff Warning (`StaffWarningModal.jsx`, shared component instantiated from 2 pages: Audit Warnings and Employees)
- Telegram Link (Employees)
- Bot Role create
- Holiday manage (Today's Attendance)
- Certificate settings (Teacher Dashboard — near-duplicate of Group Detail's version)

**Confirmation dialogs:** the app uses the **native browser `window.confirm()`** (not a styled modal) for essentially every destructive action — delete lesson, delete lead, archive student/group, delete payment, delete tariff/course/discount, delete vacation/holiday, revert salary override, mark internship, cancel coin transaction, permanent-delete user (this last one arguably deserves a real double-confirmation modal given it's irreversible, but gets the same plain browser `confirm()` as toggling a toast). This is a consistent pattern across the whole app (not a one-off bug) but a jarring, unstyled, un-brandable UX moment on every single destructive action — flagged in Problems.

---

# 16. Design System Audit

**Colors:** Token system defined once in `:root` (`styles.css` lines 6–41): `--bg #f5f5f5`, `--surface #fff`, `--surface-2 #fafafa`, `--primary #0a0a0a` (near-black, used for primary buttons/active nav — **not a brand color**, just ink-black), `--text #0a0a0a`, `--text-2 #333`, `--muted #737373`/`--muted-2 #a3a3a3`, `--border #e8e8e8`/`--border-2 #d4d4d4`, semantic `--success #16a34a`/`--danger #dc2626`/`--warning #d97706` each with a paired `-bg` tint. A parallel **dark theme** (`[data-theme="dark"]`, from line 2835) and **"ocean" theme** (`[data-theme="ocean"]`, from line 2913, a blue/slate palette) redefine the same variable names. **However**, huge swaths of the app never reference these variables at all: the entire Login page (`.lp-*` classes) hardcodes its own literal colors (`#0a0a0a`, `#e5e7eb`, `#fafafa`, `#fef2f2`/`#fecaca`/`#dc2626` for errors) completely independent of the token system or the theme switcher (Login predates the theme toggle and was never retrofitted — logging in always looks identical regardless of the user's saved theme preference, then the app "snaps" to their theme immediately after auth). `TeacherDashboard.jsx`, `Salary.jsx`'s breakdown modal, and most `Academic.jsx` inline styles also hardcode hex values (`#111827`, `#6b7280`, `#16a34a`, `#dc2626`, etc.) rather than using the CSS variables, silently breaking dark/ocean mode on those screens. Stage/status color-coding is duplicated per-file as local JS objects (`STAGE_COLORS` in Groups.jsx, GroupDetail.jsx, TeacherSalaries.jsx, TeacherDashboard.jsx — 4 separate near-identical copies with different key sets: Groups.jsx's has `foundation`/`fullstack`/`frontend`/`backend` while others vary) instead of one shared source of truth.

**Typography:** Base font is `'Inter'` (Google Fonts CDN), applied globally via `body { font-family: 'Inter', system-ui, -apple-system, sans-serif; }`. A second font system (`@fontsource-variable/geist` + `geist-mono`, self-hosted) is imported in `main.jsx` but **never referenced by any `font-family` rule anywhere** — pure dead weight, doubling font-load cost for zero visual benefit. No defined type scale (no `--font-size-*` tokens) — font sizes are freehand literals scattered everywhere (`11px`, `12px`, `12.5px`, `13px`, `13.5px`, `14px`, `15px` for body text alone across different components), making "what size is body text" a component-by-component archaeology exercise rather than a single answer.

**Spacing:** No spacing scale/tokens (no `--space-1`, `--space-2`, etc.) — every `padding`/`margin`/`gap` is a literal pixel value chosen ad hoc per component. Common values cluster around 4/6/8/10/12/14/16/18/20/24px but with no enforced rhythm; the same visual gap is sometimes 8px and sometimes 10px between structurally similar elements in different files.

**Buttons:** Core system is `.button` (solid black primary, `.secondary` = bordered white, `.small` size variant, `.danger` = red) + `.btn-icon` (icon-only, transparent, hover-tinted) + `.btn-sm` (bordered small, a near-duplicate of `.button.secondary.small` with slightly different padding/border) — **three overlapping small-button systems** (`.button.small`, `.btn-sm`, and ad hoc inline-styled buttons in TeacherDashboard.jsx's `navBtn`/`TabBtn`/`DayFilterBtn` helper functions) doing visually similar jobs with different exact metrics. The Login page adds a *fourth* button system (`.lp-btn`/`.lp-btn-secondary`) with its own hardcoded colors/radius, and `GroupCertificates.jsx` adds a *fifth* (`.mcert-btn` + `.secondary`/`.green` modifiers) scoped to its own `<style>` tag.

**Inputs:** Two parallel, non-interoperable systems: (a) `.field`/`.field-sm` (properly tokenized, used by ~22 of the 42 components) vs (b) `.form-input`/`.form-label`/`.form-group` (used by **BotAdmin.jsx, Expenses.jsx, Parents.jsx, Salary.jsx, Users.jsx, Dashboard.jsx** — 6 files) which **have zero matching CSS rules anywhere in `styles.css`** — confirmed via full-file grep, no partial match either. Every text input, label, and form-row spacing in those 6 files (which include core admin screens: user management, expense entry, parent-account creation, payroll, and the dashboard's inline expense modal) renders with **raw unstyled browser defaults** — no border-radius, no focus ring, no consistent padding/font, visually breaking from the rest of the app. This is the single largest concrete design-system defect found (elaborated in Problem #3/Recommendations).

**Cards:** No single `.card` base class — `.kpi-card`, `.group-card`, `.chart-card`, `.info-card`, `.panel-card`, `.today-group-card` are each independently defined with overlapping but not identical padding/radius/shadow/hover-transform rules (e.g. `.group-card` and `.kpi-card` both get a `translateY(-2px)` hover-lift with slightly different shadow values defined in two disconnected places in the file, lines 140–144 and 1376–1464).

**Tables:** One shared `.data-table` base (border-collapse, hover row-highlight, consistent header/cell padding) is used fairly consistently — this is one of the more disciplined parts of the system. Exceptions: the Group Detail attendance grid (`.attendance-table`) and Today's Attendance tap-list are bespoke, unrelated markup/classes.

**Badges:** `.badge` (generic neutral pill) + `.status-badge` (`.active`/`.inactive` semantic pill) exist as shared classes, but the vast majority of *colored* badges (payment status, lead stage, warning severity, role pills, coin amounts) are done via **per-instance inline `style={{background, color}}`** rather than a shared badge-variant system — e.g. role-colored pills are redefined as a local `ROLE_COLORS` object in both `Users.jsx` and (a differently-keyed) `ROLE_LABELS` in `Sidebar.jsx`/`Salary.jsx`/`Employees.jsx`/`AuditWarnings.jsx` — 4+ independent copies of "what color/label does each role get."

**Modals:** Consistent core (`.modal-overlay`/`.modal`/`.modal-header`/`.modal-body`/`.modal-footer`, `scaleIn`/`fadeIn` entrance animation) used by the large majority of dialogs — genuinely one of the better-unified pieces of the system. Exceptions: Salary breakdown modal (fully inline-styled, bypasses the shared classes entirely) and `GroupCertificates.jsx` (intentionally, it's a full-bleed print-designer, not a form dialog, so a self-contained style block is defensible there).

**Sidebar:** Always-black (`#0a0a0a`, hardcoded not tokenized) regardless of theme — a deliberate "always-dark sidebar" choice (confirmed by dedicated `[data-theme="ocean"] .sidebar` overrides existing to slightly re-tint it), consistent across the app, fixed 256px width (`--sidebar-w`), collapses to an off-canvas drawer under 768px with a hamburger toggle + scrim overlay.

**Navigation:** Sidebar nav items (`.nav-page-btn`) are functional and reasonably consistent, but section grouping is done via a plain uppercase label (`.nav-section-label`) with no collapse/expand affordance except the one special-cased "Dars rejalari" (Lessons) category sub-list, which is the only expandable/collapsible nav group in an otherwise flat, ever-growing list — for the `admin` role this produces a **single unbroken scroll of ~19 nav buttons** across "Moliya" + "Boshqaruv" alone (plus everything above), a genuine information-scent/wayfinding problem noted in Problems.

---

# 17. UI/UX Problems

Minimum 30 concrete findings, each naming the exact file/component/class where it occurs.

1. **`TeacherDashboard.jsx` (110 inline `style={{}}` blocks, zero classes from `styles.css`) is completely invisible to the theme system** — hardcoded hex colors (`#111827`, `#6b7280`, `#eef2ff`, `#f0fdf4`, etc.) mean a teacher who switches to dark/ocean mode gets a jarring pure-white dashboard while the sidebar and every other page around it goes dark. This is the app's most-used non-admin landing page (`DEFAULT_PAGE_BY_ROLE.teacher`).
2. **Two font families loaded, only one used.** `main.jsx` imports `@fontsource-variable/geist` + `geist-mono` (self-hosted, with a comment claiming it's used "for numeric/tabular data") while `styles.css` declares `font-family: 'Inter'` globally and Geist is referenced by zero `font-family` rules anywhere in the codebase (verified by full-repo grep). Pure wasted bandwidth/paint time on every page load.
3. **`.form-input`/`.form-label`/`.form-group` classes are used in 6 files (`BotAdmin.jsx`, `Expenses.jsx`, `Parents.jsx`, `Salary.jsx`, `Users.jsx`, `Dashboard.jsx`) but have zero matching CSS rules anywhere in `styles.css`.** Every form field in these files (staff account creation, expense entry, parent-account creation, payroll editing, the dashboard's expense modal) renders with raw unstyled browser-default inputs/labels — no border, no radius, no focus ring, no font consistency with the rest of the app.
4. **`Discounts.jsx` is an orphaned dead page.** No Sidebar button ever calls `onNavigate('discounts')`; the component is only reachable by manually editing the URL hash to `#discounts`. Worse, its backend calls (`fetchDiscounts`/`createDiscount`/etc. → `/discounts`) have **no matching route in `main.py`** (confirmed via full 194-route grep) — visiting it and trying to load or save data will 404/error.
5. **A `RecordPaymentModal` component defined inside `Students.jsx`** (lines ~556+) references `createPayment`, `fetchStudentPaymentSummary`, and icons `faWallet`/`faXmark`/`faCircleCheck` that are **not imported** anywhere in the file's import statements — this would throw a `ReferenceError` if ever rendered. It appears to be dead/unwired code (no visible call site renders it), but it's a landmine if someone wires it up later without checking imports.
6. **Role-based access control is defined independently in 3 places** that must be hand-kept in sync: `Sidebar.jsx`'s many `isX`/`hasCrmAccess` boolean checks, `App.jsx`'s `PAGE_ACCESS` + `DEFAULT_PAGE_BY_ROLE` maps, and server-side per-endpoint checks in `main.py`. A new role or a new page added to only one of the three will silently break navigation or expose/hide the wrong content.
7. **Role→label and role→color mappings are copy-pasted independently in at least 4 files** (`Sidebar.jsx`, `Users.jsx`, `Salary.jsx`, `Employees.jsx`, `AuditWarnings.jsx`) as local `ROLE_LABELS`/`ROLE_COLORS` objects — a role rename requires editing 5 files and is guaranteed to drift.
8. **Stage/course color maps (`STAGE_COLORS`) are independently redefined in `Groups.jsx`, `GroupDetail.jsx`, `TeacherSalaries.jsx`, and `TeacherDashboard.jsx`** with inconsistent key sets — e.g. `Groups.jsx` includes both `foundation` and `fullstack` mapped to the *same* purple, while `TeacherDashboard.jsx`'s copy uses slightly different hex values for the same semantic color.
9. **Every destructive action in the entire app uses the native unstyled `window.confirm()`** (delete lesson/lead/tariff/course/discount/vacation/holiday, archive student/group, revert salary, permanent-delete a user) instead of a branded confirmation modal — including the genuinely irreversible "permanent delete user" action, which gets the exact same low-ceremony browser dialog as a routine "delete this vacation entry."
10. **"Notifications" is used as the name for two unrelated features**: the sidebar page `#notifications` (`Notifications.jsx`, actually a student arrival/departure visit-log) and the bell-icon dropdown inside the Leads page (`NotificationBell` in `Leads.jsx`, actual system notifications: new lead assigned, reminder due). A user asking "where are my notifications" has two equally-named, functionally unrelated destinations.
11. **Payments and Expenses each have two separate sidebar entry points** (Payments under both "Narxlar" for hunter and "Moliya" for admin; Expenses under both "CRM" for hunter and "Moliya" for admin) rendering the exact same component/state — not itself a bug, but the duplication isn't visually distinguished, so it's unclear to a user whether these are the same page or different views.
12. **No pagination on the large majority of tables** (~31 of ~35 tabular views, see §14) — Users, Leads List view, Payments Debtors, Warnings, Parents, Employees, Bot Admin tabs, Salary, Teacher Salaries, Special Discounts, Academic's 5 tabs, and more all load every row client-side with no page-size cap. This will degrade badly as the school's student/lead/payment history grows (already ~35 tables of transactional data).
13. **No column sorting anywhere in the entire app** — not even on the few paginated tables. Every table's row order is whatever the backend query returns.
14. **`GroupDetail.jsx`'s Add Group modal only exposes 2 of the 4 defined course stages** (`STAGE_OPTIONS = [foundation, fullstack]`) even though `frontend`/`backend` are fully modeled in `STAGE_LABELS`/`STAGE_COLORS`/`STAGE_TOTAL_LESSONS` (in both frontend and `schemas.py`) — there is no UI path to create a new Frontend or Backend stage group, only to view legacy ones that already have that stage value in the database.
15. **The search-input has a literal duplicate CSS declaration** — `.search-input` in `styles.css` (~line 1258–1270) sets `width: 220px` and then, 4 lines later in the same rule block, `width: 260px` — the second silently wins, but it's a copy-paste leftover signaling the CSS isn't being kept clean.
16. **Only 8 `@media` breakpoints exist in a 3,205-line stylesheet** for what is used as a full admin back-office (kanban boards, wide multi-column attendance grids, dense data tables) — most complex screens (Leads kanban, the Group Detail attendance grid, Finance/Salary tables, the Funnel Board canvas) have **no responsive handling at all** and will overflow or become unusable below ~1024px without relying on generic horizontal scroll.
17. **Near-zero accessibility attributes outside the Leads module.** `grep -rc "aria-"` across all 42 components returns non-zero for only 4 files (`Leads.jsx`: 16 occurrences, plus 3 trivial SVG-icon files with a single `aria-hidden`). Every other page's icon-only buttons (`.btn-icon`, `.btn-sm`, pagination arrows, modal close ✕ buttons) have no `aria-label`, and no modal outside Leads' `Add Lead`/drawer sets `role="dialog"`/`aria-modal`/focus-trap — a screen-reader user cannot identify what most icon buttons do or that a modal has opened.
18. **`alt=""` (or any `alt` attribute) appears only twice in the entire codebase** despite numerous `<img>` usages (user avatars in `Sidebar.jsx`, student photos in `Students.jsx`/`StudentDetail.jsx`/`Notifications.jsx`, the `StudentAvatar` helper) — images are effectively invisible to screen readers.
19. **Three to five overlapping small-button systems coexist**: `.button.small`, `.btn-sm`, ad hoc inline-styled buttons (`TeacherDashboard.jsx`'s `navBtn`/`TabBtn`/`DayFilterBtn`), the Login page's `.lp-btn`/`.lp-btn-secondary`, and `GroupCertificates.jsx`'s scoped `.mcert-btn` — each with its own exact padding/radius/font-weight, none visually identical despite serving the same "secondary small action" role.
20. **Two independent Add/Edit Expense modal implementations** exist (`Dashboard.jsx`'s inline version and the standalone `Expenses.jsx` page) with slightly different field sets (Dashboard's version has no category/staff-salary conditional field, Expenses.jsx's does) — editing an expense's category requires navigating to the standalone page even if you found it via the Dashboard.
21. **Two independent Broadcast-message modal implementations** (`Users.jsx` "Telegram orqali xabar" and `Parents.jsx` "Telegram orqali xabar") are near-identical copy-pasted code with only the target audience and API call differing.
22. **The Salary breakdown modal (`Salary.jsx`) bypasses the shared `.modal`/`.modal-overlay` classes entirely**, using raw inline `style={{position:'fixed', inset:0, ...}}` — it's visually close but not pixel-identical to every other modal in the app (different max-width logic, different padding, no shared entrance animation).
23. **Certificate inline editing (`GroupCertificates.jsx`) uses `contentEditable` divs with almost no affordance signaling editability** — only the student-name field gets a bottom border; the issue-date, signer-name, and cert-number fields look like static text until a user discovers by trial-and-error that they're clickable/editable.
24. **The hand-rolled `#hash`-based router has no true 404/not-found handling** — an unrecognized hash value simply renders nothing inside `.page-anim` (none of the `activePage === 'x'` conditions match), producing a silently blank content area rather than any error or redirect.
25. **Sidebar has only one collapsible nav group** ("Dars rejalari"/Lessons' category sub-list); every other section is a permanently-expanded flat list. For the `admin` role this produces an unbroken ~19-button scroll across the CRM+Akademik+Davomat+Moliya+Boshqaruv sections with no collapse/search/favorite mechanism — a wayfinding problem that will worsen as more admin features are added.
26. **The Login page (`.lp-*` classes) is visually and structurally disconnected from the rest of the design system** — its own color literals, its own button system, its own border-radius values (10px/8px/4px vs the token `--radius`/`--radius-sm`/`--radius-lg` used everywhere else), and it never reflects the user's saved theme preference (always renders in a fixed light-ish palette regardless of `localStorage.theme`).
27. **`Dashboard.jsx`'s hand-drawn bar chart** (`div`-based height percentages) and **`TeacherDashboard.jsx`'s/`Leads.jsx`'s Analytics bar charts** are three separately implemented, non-shared bar-chart components with different markup, different label formatting (`k`-suffix vs raw numbers), and different color logic — no shared charting primitive exists despite the app needing bar charts in at least 4 places (Dashboard, Leads Analytics ×2, referral funnel monthly history).
28. **The `FunnelBoard` (Leads → Analytics → referrer → "To'liq sxema") is a fully custom pan/zoom canvas with draggable nodes**, a UI pattern used nowhere else in the app and requiring its own bespoke pointer-event math (~150 lines) — a disproportionate amount of one-off complexity for a single, rarely-used analytics drill-down, and its interaction model (drag empty space to pan vs drag a node to move vs click-without-drag to open a panel, `ctrl`+wheel to zoom) has no onboarding/hint beyond one line of small gray text in the header.
29. **Empty/loading states are inconsistent across the app.** Some pages show a proper icon+title+subtitle empty state (Leads kanban empty column, Leads "no results" board state, Today's Attendance "no groups" state uses a 📅 emoji rather than a FontAwesome icon like everywhere else), others show a bare `<div className="muted center">Yuklanmoqda...</div>` text string, and the Leads kanban is the *only* place with a true skeleton loader — every other page's loading state is an abrupt text swap with no skeleton/placeholder shape.
30. **Numeric formatting is inconsistent**: some components use `Number(n).toLocaleString()` with no locale argument (default locale, comma-grouped), others explicitly use `.toLocaleString('uz-UZ')` (space-grouped per Uzbek convention) — e.g. `Tariffs.jsx`/`Discounts.jsx` use bare `.toLocaleString()` while `Students.jsx`/`Payments.jsx` use `.toLocaleString('uz-UZ')`, so money amounts are formatted with commas in some tables and spaces in others within the same app.
31. **Date formatting is similarly inconsistent** — some components hand-roll `YYYY-MM-DD` via manual padStart string concatenation (`DateRangePicker.jsx`, `api.js`'s `tashkentToday()`), others use `toLocaleDateString('uz-UZ', {...})` with varying option sets (`day:'2-digit'` vs `day:'numeric'`, with/without weekday), and there's no single shared date-formatting utility despite dates appearing in nearly every table in the app.
32. **`Payments.jsx`'s inline "Sales" attribution toggle button** changes both its background color AND its disabled state based on a computed `alreadyCredited` flag with a title-only (hover tooltip) explanation of why it's disabled — a state with real business consequence (referral-stat crediting is one-time and irreversible per the code comments in `models.py`) is explained only via a hover tooltip, invisible on touch devices.
33. **No unsaved-changes warning anywhere** — every edit modal (Student, Group, Lead, User, Payment, etc.) can be dismissed via the ✕/overlay-click/Escape with in-progress edits silently discarded, with no confirmation, across the entire app.
34. **The mobile/small-screen experience is untested-feeling**: `.mobile-topbar`/`.menu-toggle`/`.sidebar-overlay` exist for a hamburger-drawer pattern, but complex data-dense screens (attendance grids, kanban boards, wide tables like Payments/Users/Salary) have no distinct mobile layout — they rely on generic table/grid overflow scrolling, which is a poor experience for genuinely wide grids like the Group Detail attendance table (one column per calendar day, up to 31 columns).
35. **Toast notifications are the only mutation-feedback mechanism app-wide** (react-hot-toast, top-right) — there is no inline field-level validation feedback in most forms (errors surface only as a toast after clicking Save, requiring the user to re-scan the whole form to find which field was wrong), except Lesson add (`AddLessonModal.jsx`) and Login, which do show inline `.error` divs.

---

# 18. Component Inventory

**Page-level / feature components** (one per top-level sidebar destination, in `components/`): `Lessons`, `Leads`, `Students`, `StudentDetail`, `Groups`, `GroupDetail`, `Payments`, `Dashboard`, `Finance`, `Tariffs`, `Courses`, `Discounts` (orphaned), `Special`, `Salary`, `TeacherSalaries`, `TeacherDashboard`, `Expenses`, `Academic`, `FeedbackInbox`, `Notifications`, `ChatBot`, `Parents`, `Users`, `Employees`, `AuditWarnings`, `MyWarnings`, `BotAdmin`, `TodayAttendance`, `PublicIntake`, `Login`.

**Shared/reusable widgets:**
- `Pagination` — page-window control w/ ellipses, used in Students/Groups/Payments only.
- `ProgressBar` — single generic `<div>` fill bar, used only in Lessons (curriculum completion %); every *other* progress bar in the app (group course progress, salary payment %, finance collection %) is a bespoke inline-styled div, not this shared component.
- `DateFilter` + `DateRangePicker` — a genuinely well-factored pair: preset buttons (Barchasi/Bugun/7 kun/Bu oy) + a custom two-click calendar range picker with hover-preview, used consistently across Students/Groups/Payments/AuditLogPanel.
- `MinaretLogo` — theme-aware animated SVG mark (8-pointed star logo), used in Sidebar brand + Login + Public Intake.
- `MinarWatermark` — large background watermark SVG version of the same mark, used once as a subtle background layer behind all page content (`.content-watermark` in `App.jsx`).
- `AddLessonModal`, `LessonList`, `LessonDetail`, `AuditLogPanel` — Lessons-page-specific sub-components.
- `StaffWarningModal` — genuinely shared, instantiated from both Audit Warnings and Employees pages.
- `GroupCertificates` — genuinely shared, instantiated from both Group Detail and Teacher Dashboard.
- `NotificationBell`, `ListView`, `LeadDrawer`, `StageManager`, `FunnelBoard`, `Analytics`, `CommentStats`, `IntakeFormManager` — all defined *inside* `Leads.jsx` as local functions rather than separate files (the file is 1,510 lines and contains 9 component definitions).
- `KpiCard`, `InfoChip`, `TabBtn`, `DayFilterBtn` — local helper components defined inside `TeacherDashboard.jsx` only, not reused elsewhere despite equivalent needs existing in Dashboard.jsx/Finance.jsx/Salary.jsx (which each redefine their own KPI-card markup inline instead).
- `RecordPaymentModal`, `VacationModal`, `AttachGroupModal`, `PayStatus`, `StudentAvatar` — local helpers defined inside `Students.jsx`/`StudentDetail.jsx`.
- `SkeletonCard`, `SkeletonColumn`, `KanbanSkeleton` — local to `Leads.jsx`, the only skeleton-loading implementation in the app.
- `Star8Corner`, `CertificateCard` — local to `GroupCertificates.jsx`.
- `EmployeesTab`, `RolesTab`, `SettingsTab`, `AdminsTab`, `InvestorsTab` — local tab-content components inside `BotAdmin.jsx`.

**Truly cross-cutting primitives that exist only as CSS classes (not components):** `.button`/`.btn-icon`/`.btn-sm` (buttons), `.field`/`.field-sm` (inputs — note the separate, unstyled `.form-input` family), `.modal*` (dialogs), `.data-table` (tables), `.badge`/`.status-badge` (pills), `.kpi-card`/`.info-card`/`.panel-card`/`.chart-card`/`.group-card` (cards — 5 non-unified variants), `.toolbar`/`.search-wrap` (filter bars), `.tab-bar`/`.tab-btn` (tabs).

---

# 19. Design System Audit — Summary Table

| Category | Status | Key values / notes |
|---|---|---|
| Colors | Tokenized (3 themes) but **widely bypassed** by hardcoded hex in Login, TeacherDashboard, and per-file role/stage color maps | `--primary:#0a0a0a`, `--success:#16a34a`, `--danger:#dc2626`, `--warning:#d97706` |
| Typography | Single font declared (`Inter`) but a second unused font system is also loaded; no type scale, freehand font-sizes | Body text ranges 11–15px across files with no naming |
| Spacing | No spacing scale/tokens; all literal pixels | Common values 4/6/8/10/12/16/20/24px, inconsistent choice between visually-equivalent cases |
| Buttons | Token-based core (`.button`) but 3–5 parallel small-button implementations | `.button`, `.btn-icon`, `.btn-sm`, `.lp-btn`, `.mcert-btn`, ad hoc inline styles |
| Inputs | **Split system**: `.field`/`.field-sm` (styled, ~22 files) vs `.form-input`/`.form-label`/`.form-group` (6 files, **zero CSS, renders unstyled**) | Biggest concrete defect in the whole audit |
| Cards | 5 independently-defined near-duplicate card classes | `.kpi-card`, `.group-card`, `.chart-card`, `.info-card`, `.panel-card` |
| Tables | Reasonably unified (`.data-table`) | No pagination on ~31/35 tables, no sorting anywhere |
| Badges | Shared base classes exist but most color variants are per-instance inline styles | Role/stage/status colors redefined in 4+ separate JS objects |
| Modals | Well-unified core, 2 notable exceptions (Salary breakdown, GroupCertificates by design) | `.modal-overlay`/`.modal`/`.modal-header/body/footer` |
| Sidebar | Consistent, hardcoded-black regardless of theme (deliberate) | Fixed 256px, off-canvas <768px, only 1 collapsible group out of ~11 sections |
| Navigation | Flat, ever-growing list per role, no search/favorites/collapse (except Lessons) | Admin sees ~19 unbroken nav buttons |

---

# 20. UX Problems — see §17 (35 findings) for the itemized list; this section intentionally left as a pointer per the requested structure.

---

# 21. Recommendations

Prioritized, each tied to the findings above.

**P0 — Correctness/breakage (fix before any visual redesign, since redesigning broken things wastes effort):**
1. Fix or formally remove `Discounts.jsx` (Problem #4) — either implement the missing `/discounts` backend routes or delete the orphaned page/nav-dead-code entirely; `Special.jsx` already covers the real discount use case.
2. Remove or properly wire the dead `RecordPaymentModal` in `Students.jsx` (Problem #5) before it's accidentally activated and crashes on missing imports.
3. Style `.form-input`/`.form-label`/`.form-group` (Problem #3) or, better, migrate those 6 files to the existing `.field` system — this alone will visually fix 6 of the app's most-used admin screens with zero new design work, since `.field` already exists and is battle-tested.

**P1 — Foundational design-system work (do first in any redesign, everything else builds on this):**
4. Establish one real design-token set: a type scale, a spacing scale, and a single canonical set of card/button/badge components — then migrate the 5 card variants, 3–5 button variants, and per-file color-map duplications (role colors, stage colors) onto it. This directly fixes Problems #1, #7, #8, #19, #22, #27.
5. Decide on and load exactly one font family; drop the unused Geist import (Problem #2) or actually adopt it for numeric/tabular columns as originally intended (money amounts, attendance counts) since Geist Mono's tabular figures would be a genuine improvement for the many money/count-heavy tables in this app.
6. Retrofit the Login page onto the shared token system so it respects the saved theme and shares the real button/input components (Problem #26) — currently the first thing every user sees is off-system.
7. Fix `TeacherDashboard.jsx` specifically — it's the highest-traffic page for the `teacher` role and the worst offender for inline-style/theme-breakage (Problem #1); rebuilding it on shared components would fix both the theme bug and give the codebase its first shared `KpiCard`/`TabBtn`/`InfoChip` set that other pages (Dashboard, Finance, Salary) could then also adopt instead of re-implementing KPI cards locally.

**P2 — Systemic UX gaps:**
8. Add pagination + sorting to the ~31 un-paginated tables (Problem #12/#13), prioritizing Users, Leads List, Payments Debtors, and Warnings since those are admin/audit-facing screens most likely to grow large.
9. Replace `window.confirm()` for destructive actions with a real confirmation modal component, with extra friction (e.g. type-to-confirm) specifically for the irreversible "permanent delete user" action (Problem #9).
10. Add real accessibility basics app-wide: `aria-label` on all icon-only buttons, `alt` text on all images, `role="dialog"`/`aria-modal`/focus-trap on all modals — Leads.jsx already has the pattern (`useFocusTrap` hook) ready to extract and reuse everywhere (Problems #17/#18).
11. Consolidate the two Broadcast modals and two Expense modals into one shared component each (Problems #20/#21).
12. Introduce one shared date-formatting and one shared number-formatting utility and sweep the codebase to use them consistently (Problems #30/#31).
13. Rename one of the two "Notifications" features to remove the naming collision (Problem #10) — e.g. rename the visit-log page to "Kelish-ketish" (Arrivals) since that's what it actually tracks.
14. Add a real empty/loading-state system (icon + title + subtitle + optional CTA, plus a skeleton variant) and apply it everywhere, extracted from the one good example already in `Leads.jsx`'s kanban states (Problem #29).

**P3 — Longer-term structural suggestions (flag for discussion, not pure execution):**
15. Consider a real router (`react-router`) — the hand-rolled hash system works but has no 404 handling (Problem #24), duplicates access-control logic across two files (Problem #6), and makes deep-linking to detail views (student/group) fragile (relies on `sessionStorage`, breaks on a fresh tab/shared link).
16. Consider a lightweight shared charting primitive (even a small wrapper around SVG bars) to replace the 3 independently-implemented bar charts (Problem #27) and give the app one consistent chart visual language.
17. Consider whether the Funnel Board's bespoke pan/zoom canvas (Problem #28) is worth its complexity/maintenance cost relative to how often it's actually used — a simpler static Sankey-style funnel diagram might serve the same "referral conversion" storytelling need with far less code and a gentler learning curve for users.
18. Revisit the sidebar's flat, ever-growing nav-list architecture (Problem #25) before adding more admin features — consider collapsible sections, a command-palette/search (the Leads page already has a `/`-to-focus-search pattern that could generalize), or role-scoped landing dashboards that reduce reliance on deep sidebar scanning.
