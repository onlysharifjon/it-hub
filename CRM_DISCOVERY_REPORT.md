# IT Hub CRM — Product Discovery Report

Prepared for: a senior product designer redesigning this CRM's entire UI **without reading the codebase**. This document is fully self-contained — every fact needed to design against is below, sourced directly from the running production code (`/var/www/it-hub` on the app server, live at `crm.minaracademy.uz`).

A companion engineering-focused document, `UI_AUDIT_REPORT.md`, exists in the same directory with more granular file-by-file component notes; this report is the product/design-facing counterpart and does not assume you've read it.

---

# Section 1 — Product Overview

**What this CRM is used for:** It is the single internal operating system for **Minar Academy / IT Hub**, a coding-bootcamp-style programming school (tracks: Foundation → Frontend → Backend). It is not a generic CRM — one app fuses five systems that would be separate SaaS products anywhere else:

1. A **sales CRM** — lead capture, pipeline/kanban, call-center qualification, referral-source tracking.
2. A **student information system (SIS/LMS)** — student roster, class groups, attendance, grading, homework delivery, certificates.
3. **Billing & finance** — pricing tariffs, monthly payment tracking, debt/collections, P&L, teacher payroll.
4. **Staff management** — internal user accounts/roles, an internal-discipline ("audit") warning/fine system delivered over Telegram.
5. A **parent-facing backend** — accounts consumed by a separate mobile app (parents never use this web app directly).

**Business domain:** Private education / bootcamp operations. Everything in the product exists to serve one operational loop, described below.

**Primary user types:** Internal staff only, in 7 distinct roles (Section 2). There is no student- or parent-facing UI in this application — students/parents are *data* managed by staff, not users of this product. (Parents get a companion mobile app, out of scope here; students get nothing directly.)

**User workflow, start to finish (the "happy path" a lead travels through the whole system):**

1. A **lead** arrives — entered manually by a Hunter/Sales/Call-center rep, submitted via a public marketing landing page (`/intake/<slug>`, no login required), or pushed in automatically from a Facebook Lead Ads webhook.
2. The lead lands in the **Leads** pipeline (kanban board). Call-center or Hunter staff call the person and drag/click the card through pipeline stages.
3. A promising lead becomes a **Student** — usually first flagged "demo" (hasn't attended a real class yet).
4. The student is attached to a **Group** (a cohort with a schedule and a **Tariff** = the monthly price).
5. The teacher marks daily **Attendance** for their groups (manually via a tap-to-toggle grid, or automatically via a face-recognition camera check-in service).
6. Hunter/Admin record **Payments** each month; the system computes what's owed vs. paid vs. still owing per student per month (accounting for vacations and any special per-student discounts).
7. **Teacher salaries** are auto-calculated monthly from a formula (fixed base pay + a per-student-attended-lesson share), editable by Admin if an override is needed.
8. Admin reviews the whole business on the **Dashboard** (income, teacher payroll cost, external expenses, net profit) and can export any period to Excel.
9. Along the way, teachers record **grades**, hand out gamified **"coin" rewards**, leave **feedback comments** visible to parents (via the mobile app), and generate printable **certificates** on course completion.
10. The **Audit** role — a role unique to this business, essentially internal HR/discipline — issues formal warnings or fines to any staff member for rule violations, delivered automatically over Telegram.

**Key CRM processes to internalize before redesigning:**
- Lead capture is 3-channeled (manual entry / public form / Facebook webhook) but converges on one pipeline.
- Leads can sit in a **shared pool** (unclaimed) that any eligible rep can "claim" — a scarce-resource/first-come workflow, not a simple assignment model.
- The pipeline stages are **admin-configurable** (not a fixed hardcoded enum) — an admin can rename, recolor, reorder, and add/remove stages live.
- Money math (expected/paid/debt) is **computed, not stored** — it's derived server-side from tariff price × vacations × special discounts, recalculated on the fly wherever it's shown (Students list, Student Detail, Payments, Finance).
- Teacher pay is **formula-driven, not flat** — it directly depends on attendance data recorded elsewhere in the app, so Attendance and Finance are causally linked even though they're separate sections.

---

# Section 2 — Role System

**All 7 roles, verbatim from the backend's `UserRole` enum** (`backend/models.py`) with the exact permission logic pulled from the backend's own access-guard functions (`backend/main.py`, functions named `require_*`) and the frontend's own access-control table (`frontend/src/App.jsx`'s `PAGE_ACCESS` constant — this is the authoritative, machine-enforced list, not an approximation):

| Role (DB value) | UI label | One-line summary |
|---|---|---|
| `admin` | Admin | Superadmin. Every page, all finance, payroll, user management, bot administration. |
| `support_teacher` | Metodist / Support Teacher | Curriculum owner — full lesson-plan CRUD, plus LMS (students/groups) and grading. No CRM, no finance. |
| `teacher` | O'qituvchi (Teacher) | Classroom teacher. Own groups only. Own salary, own attendance, own grading. Read-only on curriculum. |
| `hunter` | Hunter | The "does everything sales-adjacent" role: leads, students/groups, **and** payments/expenses/parents/chatbot — the only non-admin role with real finance visibility. |
| `sales` | Sales | Lead generation / referral-focused. Leads + students/groups. Explicitly **no finance** (the code itself comments "moliya yo'q" = "no finance"). |
| `call_center` | Call Center | Lead qualification by phone. Leads + students/groups + the feedback-parent-followup inbox. No finance, no chatbot, no parents access. |
| `audit` | Audit | A completely separate track from everything else: internal staff discipline only (issuing warnings/fines). Cannot see leads, students, groups, attendance, academic, or finance at all. |

### Role × Page Access Matrix

This table is the literal, authoritative access-control list enforced by the app (both frontend gate and backend re-check it independently per endpoint). ✅ = full access, 🟡 = partial/conditional access (see note), ⬛ = not visible/not permitted.

| Page | Admin | Metodist | Teacher | Hunter | Sales | Call Center | Audit |
|---|---|---|---|---|---|---|---|
| Lessons (curriculum) | ✅ edit | ✅ edit | 🟡 view-only | ⬛ | ⬛ | ⬛ | ⬛ |
| Leads | ✅ | ⬛ | ⬛ | ✅ | ✅ | ✅ | ⬛ |
| Students / Groups (list+detail) | ✅ | ✅ | 🟡 group detail only (own groups) | ✅ | ✅ | ✅ | ⬛ |
| Today's Attendance | ✅ | ✅ | ✅ (own groups, locked to today) | ✅ | ✅ | ✅ | ⬛ |
| Academic (grades/coins/feedback/certs/events) | ✅ | ✅ | ✅ | ⬛ | ⬛ | ⬛ | ⬛ |
| Payments | ✅ | ⬛ | ⬛ | ✅ | ⬛ | ⬛ | ⬛ |
| Expenses | ✅ (manage) | ⬛ | ⬛ | 🟡 view-only | ⬛ | ⬛ | ⬛ |
| Finance / Dashboard / Tariffs / Courses / Special discounts | ✅ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ |
| Teacher Salaries / Salary (payroll) | ✅ | ⬛ | 🟡 own salary only (Teacher Dashboard) | ⬛ | ⬛ | ⬛ | ⬛ |
| Users (staff accounts) / Bot Admin | ✅ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ |
| Chatbot (Telegram inbox viewer) | ✅ | ⬛ | ⬛ | ✅ | ⬛ | ⬛ | ⬛ |
| Parents (mobile-app accounts) | ✅ | ⬛ | ⬛ | ✅ | ⬛ | ⬛ | ⬛ |
| Feedback Inbox (parent-followup triage) | ✅ | ⬛ | ⬛ | ⬛ | ⬛ | ✅ | ⬛ |
| Notifications (student visit log) | ✅ | ⬛ | ⬛ | ✅ | ✅ | ✅ | ⬛ |
| Employees / Audit Warnings | ✅ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ | ✅ |
| My Warnings (self-service) | ⬛ (uses Audit Warnings instead) | ✅ | ✅ | ✅ | ✅ | ✅ | ⬛ (uses Audit Warnings instead) |
| Teacher Dashboard (home) | ⬛ | ⬛ | ✅ (this is Teacher's home page) | ⬛ | ⬛ | ⬛ | ⬛ |

**Each role's default landing page on login** (where they're sent immediately after auth): Admin → Lessons, Metodist → Lessons, Teacher → Teacher Dashboard, Hunter → Payments, Sales → Leads, Call Center → Leads, Audit → Employees.

**Each role's main daily workflow, in practice:**
- **Admin:** Oversight and exception-handling across everything; the only role that touches money at the company level (P&L, payroll) and manages the system itself (users, bot).
- **Metodist:** Owns and maintains the curriculum library; secondarily handles student/group admin.
- **Teacher:** Lands on their personal dashboard → picks a group → takes attendance / sends homework / grades work → checks their own pay calculation.
- **Hunter:** The busiest single-person role — chases leads, enrolls students, records payments, tracks expenses, manages parent accounts, all in one day.
- **Sales:** Pure lead-generation and referral-source management, no downstream money responsibility.
- **Call Center:** Phone-qualifies inbound leads, triages parent-facing feedback follow-ups.
- **Audit:** Entirely separate concern — reviews staff conduct, issues formal warnings/fines via Telegram, unrelated to the academic/sales operation.

**Important structural note for the redesign:** access control is currently defined in **three separate hand-maintained places** that must be kept manually in sync (frontend sidebar visibility logic, a frontend page-access table, and independent backend endpoint guards). This isn't a visual-design concern, but it means: **when designing new pages/roles, plan for a single declarative permissions source** — today, a new role or page added in only one of the three places silently breaks either navigation or security. A redesign is a natural opportunity to collapse this into one config.

---

# Section 3 — Complete Sitemap

There are no real URL routes today (see Section 16/17 for why) — every "page" is a named view-key the app switches between. Below, each page's real access list (pulled from the authoritative `PAGE_ACCESS` table, Section 2) is given directly.

| Page | View key | Purpose | Roles with access |
|---|---|---|---|
| Login | (shown when logged out) | Authenticate; also shows account-blocked/expired states | Everyone (pre-auth) |
| Public Intake Form | `/intake/<slug>` | Public marketing lead-capture form, no login | Public (no auth) |
| Lessons | `lessons` | Curriculum library CRUD, organized by track | Admin, Metodist, Teacher (view-only) |
| Leads | `leads` | Sales pipeline: kanban/list/analytics | Admin, Hunter, Sales, Call Center |
| Students (list) | `students` | Roster: Demo / Active / Archived tabs | Admin, Metodist, Hunter, Sales, Call Center |
| Student Detail | `student_detail` | Full student profile, 4 tabs | Admin, Metodist, Hunter, Sales, Call Center |
| Groups (list) | `groups` | Class/cohort management | Admin, Metodist, Hunter, Sales, Call Center |
| Group Detail | `group_detail` | Attendance grid, camera log, homework, certificates for one group | Admin, Metodist, Hunter, Sales, Call Center, **and Teacher** (own group only) |
| Payments | `payments` | Payment ledger + Debtors view | Admin, Hunter |
| Dashboard | `dashboard` | Company-wide KPIs, P&L, annual chart | Admin only |
| Teacher Salaries | `teacher_salaries` | Company-wide payroll drill-down (read-only) | Admin only |
| Salary | `salary` | Editable payroll for all staff | Admin only |
| Expenses | `expenses` | Operating-expense ledger | Admin (manage), Hunter (view-only) |
| Tariffs | `tariffs` | Pricing-plan CRUD | Admin only |
| Courses | `courses` | Course-catalog CRUD | Admin only |
| Finance | `finance` | Per-group collection-rate report | Admin only |
| Discounts | `discounts` | **Orphaned/dead page** — see Section 17 finding | Admin only (in theory; unreachable in practice) |
| Special | `special` | Per-student ad-hoc discounts (the real, working discount mechanism) | Admin only |
| Teacher Dashboard | `teacher_dashboard` | Teacher's personal home page | Teacher only |
| Today's Attendance | `today_attendance` | Fast daily roll-call across groups | Admin, Metodist, Teacher, Hunter, Sales, Call Center |
| Academic | `academic` | Grades / Coins / Feedback / Certificates / Events, tabbed | Admin, Metodist, Teacher |
| Feedback Inbox | `feedbacks` | Parent-followup triage queue | Admin, Call Center |
| Notifications | `notifications` | Student arrival/departure visit log (misleadingly named — see Section 17) | Admin, Hunter, Sales, Call Center |
| ChatBot | `chatbot` | Read-only Telegram conversation viewer | Admin, Hunter |
| Parents | `parents` | Parent-account management for the mobile app | Admin, Hunter |
| Users | `users` | Internal staff account CRUD | Admin only |
| Employees | `employees` | Staff directory (Telegram-linking for warnings) | Admin, Audit |
| Audit Warnings | `audit_warnings` | Formal staff warning/fine log | Admin, Audit |
| My Warnings | `my_warnings` | Self-service view of own warnings | Metodist, Teacher, Hunter, Sales, Call Center |
| Bot Admin | `bot_admin` | Administer the separate Telegram bot's own database | Admin only |

---

# Section 4 — Sidebar Structure

The sidebar is grouped into labeled sections; every section and button is conditionally shown per-role (there is no user-facing customization — the sidebar contents are entirely determined by role). Icons are all FontAwesome solid-style glyphs; there is no custom icon set.

| Section label | Visible to | Items (icon → label → destination) |
|---|---|---|
| **Metodika** (Curriculum) | Everyone except Hunter/Sales/Call Center/Audit | Dars rejalari (Lessons) — expands into a **Foundation / Frontend / Backend** sub-list (the only collapsible/expandable nav group in the entire sidebar) |
| **Narxlar** (Pricing) | Hunter only | To'lovlar (Payments) — a Hunter-specific shortcut label for the same Payments page Admin also reaches via "Moliya" |
| **Mening panelim** (My Dashboard) | Teacher only | Mening guruhlarim (Teacher Dashboard) |
| **CRM** | Hunter, Sales, Call Center, Admin | Lidlar (Leads) · Notifications (visit log) · Chatbot (Hunter/Admin only) · Izohlar/Feedback (Call Center/Admin only — carries a live unread-count red badge) · Ota-onalar/Parents (Hunter/Admin only) · Xarajatlar/Expenses (Hunter only) |
| **Akademik** (Academic) | Everyone except Call Center/Sales/Audit/Hunter | Baholar va izohlar (Academic) |
| **Davomat** (Attendance) | Everyone except Audit | Bugungi darslar (Today's Attendance) |
| **Audit** | Audit, Admin | Xodimlar (Employees) · Ogohlantirishlar (Audit Warnings) |
| **Mening** (Mine) | Everyone except Audit/Admin | Ogohlantirishlarim (My Warnings) |
| **LMS** | Metodist, Hunter, Sales, Call Center | Talabalar (Students) · Guruhlar (Groups) |
| **Moliya** (Finance) | Admin only | Moliya (Finance) · To'lovlar (Payments — same page as Hunter's "Narxlar" entry) · Tariflar (Tariffs) · Kurslar (Courses) · Special (per-student discounts) · O'qituvchi maoshi (Teacher Salaries) · Ish haqi (Salary) · Xarajatlar (Expenses — same page as CRM section's entry) · Dashboard |
| **Boshqaruv** (Administration) | Admin only | Foydalanuvchilar (Users) · Bot boshqaruvi (Bot Admin) |

**Fixed footer, all users:** avatar (click → file picker for photo upload; pencil icon → "edit profile" modal with name + password-change fields) · theme switcher (3-dot control: light / dark / "ocean") · Chiqish (Logout).

**Grouping note for redesign:** grouping is currently by *department metaphor* (Metodika, CRM, Akademik, Moliya...) rather than by *task frequency* or *user mental model* — for the Admin role specifically, this produces one long, permanently-expanded, ungrouped-feeling scroll of roughly 19 nav buttons across the CRM + Akademik + Davomat + Moliya + Boshqaruv sections, with no search, no favorites, no collapse (except the one Lessons sub-list). This is one of the highest-value redesign opportunities — see Section 18.

**Two pages are deliberately duplicate-listed** under two different section labels for two different roles (Payments: "Narxlar" for Hunter / "Moliya" for Admin; Expenses: "CRM" for Hunter / "Moliya" for Admin) — this is intentional per-role convenience today, but the visual sidebar gives no signal that these are literally the same screen, which could confuse a new designer auditing screenshots.

---

# Section 5 — Dashboard Analysis

There is **no shared "Dashboard" concept across roles** — confirmed directly in code: `Dashboard.jsx` and `TeacherDashboard.jsx` contain **zero internal role-conditional branches**; each is a single, separate, hardcoded component gated entirely by the page-access table. There are exactly **two** distinct dashboard experiences in the whole app (not "one dashboard with role variants"):

### 5.1 — Admin Dashboard (`dashboard`, Admin only)

The company's real home screen. Top to bottom:
1. **Header:** page title + a year `<select>` (current year ±2) + an "Excel" export button.
2. **KPI row, 4 cards:** Jami talabalar (total students, with an "Faol: N" active-count subline) · Guruhlar (total groups, same subline pattern) · Bu oy tushum (this month's income, visually highlighted, with a colored ▲/▼ trend arrow vs. last month) · O'tgan oy tushum (last month's income, plain).
3. **"This month's P&L," 5 cards in a row, each color-coded:** Umumiy tushum (total income, green) · O'qituvchi maoshi (teacher payroll total, blue, **clickable — jumps to Teacher Salaries**) · Tashqi xarajatlar (external expenses, amber, **clickable — jumps to Expenses**) · Umumiy chiqim (total expenses, red) · Sof foyda (net profit, green/red depending on sign, the single largest/boldest number on the page).
4. **Inline expense management card:** month/year picker + "Add" button + a fully editable table (name/amount/actions) with a footer total — this is a complete, working expense CRUD embedded directly in the dashboard, not just a summary (the standalone Expenses page duplicates this capability).
5. **A hand-drawn annual bar chart** (plain `<div>` height percentages — no charting library is used anywhere in this app): one bar per month, current month highlighted, value shown in "Nk" thousands-shorthand, hover reveals full income + net profit.
6. **Full monthly history table**, reverse-chronological: Month / Income / Teacher payroll / External expenses / Total expenses / Net profit / Payment count — 7 columns, color-coded to match the P&L cards above.

No filters exist beyond the year selector. No per-group or per-course breakdown lives here (that granularity is on the separate Finance page). Loading state is a single centered "Loading..." text replacing the entire page — no skeleton.

### 5.2 — Teacher Dashboard (`teacher_dashboard`, Teacher only — this role's home page)

A teacher's personal cockpit, structurally unrelated to the Admin dashboard (different component, different visual language entirely — see Section 16 for why this matters to the redesign):
- **Student search-as-you-type** — typing a name jumps directly into that student's group.
- **3 KPI cards** (own groups, own students, own this-month pay — exact card set determined by the teacher's own data).
- **Tab bar:** "Guruhlarim" (My Groups) / "Maosh hisobi" (Salary Calculation) / "Sertifikatlar" (Certificates).
- **Day-of-week filter** (the school's twice-weekly scheduling convention — "even days" / "odd days").
- **Expandable group cards** showing per-group salary breakdown.
- **Certificate list + a generate-certificate modal** feeding into the same certificate-viewer/print component used in Group Detail.

**Redesign-critical fact:** this page is currently built almost entirely from ad hoc inline styling rather than the shared design system, meaning it visually does **not** match the rest of the app and does not respond to the theme switcher at all (further detail in Section 16). Since this is the single most-visited page for the Teacher role, it should be treated as a first-class, ground-up redesign target rather than a "polish pass."

There is no Manager or Student dashboard — those roles/concepts don't exist in this product (see Section 2's 7-role list; there is no "Manager" role, and students are data, not users).

---

# Section 6 — Leads / CRM Module

### Data model
- **Statuses (legacy, backend enum):** `new → called → will_come/callback → enrolled/rejected`. However the *actual UI* does not drive off this fixed enum — it drives off an **admin-configurable pipeline of named stages** (each stage has a name, color, icon, sort order, and a `kind` of "lead"/"won"/"lost"). Default seeded pipeline: Yangi (New) → Qo'ng'iroq qilindi (Called) → Qayta qo'ng'iroq (Callback, 1hr) → Keladi (Will come) → Demo → To'landi (Paid/Enrolled, `kind=won`) → Rad etildi (Rejected, `kind=lost`).
- **Sources:** also admin-managed, not hardcoded — seeded examples: Instagram, Telegram, Walk-in (default), Website, Referral, Phone call, Other. A source can be flagged as a paid "campaign" and can carry a linked staff member who gets auto-credited when leads from that source convert (this powers referral performance analytics).

### Fields on a lead
Full name*, phone*, course interest, source, date of birth, interested group, two parent-phone fields, freeform notes.

### Filters & search
Free-text search on name/phone (debounced, with a `/` keyboard shortcut to focus it), source dropdown, "shared pool" toggle (unclaimed leads only), a "today" toggle (Hunter/Call Center only — leads with a callback due today). Active filters render as removable chips with a "clear all" action.

### Three views (tab strip: Board / List / Analytics)
- **Board (Kanban, default):** one column per active pipeline stage, native drag-and-drop cards. Each card shows name, phone, shared/claimed badges, course/source/interested-group tags, the owning rep's name (visibility itself is role-gated), a callback time or creation time, a truncated notes preview, a truncated next-reminder preview, and — if the lead is in the shared pool — a "Claim" button. This is the only screen in the app with a genuine skeleton-loading state (every other page just swaps in a "Loading..." text).
- **List:** a plain table — #, Name, Phone, Source, Stage badge, Time-or-note, (Hunter column, role-gated), Actions.
- **Analytics:** top-line tiles (total / won / lost / conversion %) → a stage-distribution bar list → a source-conversion table (rate shown as a colored pill) → a "Comment Stats" panel (activity volume over time, per-rep leaderboard) → a per-referrer section with a 5-stage funnel-chip row and a link into a full-screen, pannable/zoomable "Funnel Board" canvas.

### The lead detail drawer
Opens as a slide-over panel from any card/row click. Shows: tap-to-call phone link, a tag row (course/source/interested-group/claimed-by/created-by), any rich fields present (DOB, parent phones), Claim/Release buttons, a **stage-picker rendered as a grid of colored pill buttons** (not a dropdown — worth noting for the redesign, since this is a distinctive, already-good interaction pattern), a callback-datetime input, read-only notes display, a full reminders sub-section (list + inline add + mark-done), and a read-only activity timeline that's auto-generated server-side on every stage change.

### The lead lifecycle — as a narrative journey

1. **Birth.** A lead is born one of three ways: (a) a rep manually clicks "Add Lead" and fills the 8-field form; (b) a prospective student fills out the public marketing form at a shareable `/intake/<slug>` URL — a bare, brand-minimal page (logo + form, no app chrome since it's pre-auth) that immediately shows a "Thank you, we'll be in touch" success state; (c) Facebook Lead Ads pushes one in automatically via a webhook, with zero human action.
2. **Entering the pool (sometimes).** Depending on how it was created/assigned, a lead may sit unclaimed in the **shared pool** — visible to every eligible rep but owned by no one. Any Hunter/Sales/Call-center rep can hit "Band qilish" (Claim) directly from its kanban card, which is a single click with an inline loading spinner, instantly making them the owner. A rep can later "release" a lead back to the pool, or explicitly "share" it back if they decide someone else should take it.
3. **First contact.** Call Center (primarily) or Hunter calls the number. If they reach the person, they drag the card from "Yangi" (New) to "Qo'ng'iroq qilindi" (Called) — either by physically dragging it on the kanban board, or by opening the drawer and clicking the target stage pill.
4. **Qualification loop.** If the person needs a callback, the rep sets a callback datetime in the drawer and the card moves to "Qayta qo'ng'iroq" (Callback); the card then surfaces prominently in the rep's "today" filter once that callback time arrives. Every stage transition — drag or drawer-click — silently appends an entry to the lead's activity timeline; the rep never manually logs "I called them," it's implicit in the stage move itself. Reps can also leave freeform notes and set reminders (visible in the drawer's dedicated reminders sub-section) independent of stage changes — e.g. "call back after they discuss with spouse."
5. **Commitment.** Once the person agrees to visit, the card moves to "Keladi" (Will come), and often next to "Demo" once they've attended a trial class in person.
6. **Resolution — one of two endings:**
   - **Won:** the rep moves the card to "To'landi" (Paid/Enrolled — a `kind=won` stage). This is a *manual* stage move; conversion to an actual Student record is a **separate, unlinked action** performed on the Students page (an admin/rep manually creates a new Student and, implicitly, treats the lead as closed — there is no automated "convert lead → student" button that carries lead fields across). This is a real workflow gap worth flagging for the redesign: the pipeline visually promises a clean handoff into the student system that doesn't actually exist as a single action today.
   - **Lost:** the rep moves the card to "Rad etildi" (Rejected — a `kind=lost` stage), typically with a note explaining why. Lost leads remain visible/filterable but drop out of active pipeline counts.
7. **Aftermath (analytics).** Every won/lost lead feeds the Analytics tab's conversion-rate and per-source performance numbers, and — if the lead came from a tracked referral source — feeds the referrer's personal funnel chip-row and monthly dual-bar chart, viewable in full via the Funnel Board.

### Admin-only pipeline configuration
A **Stage Manager modal** lets an admin add/reorder (▲▼)/recolor (14-swatch picker)/set the won-lost-lead "kind" of/delete pipeline stages live — this directly reshapes the kanban board for everyone, immediately. An **Intake Form Manager modal** lets an admin create new public-facing landing-page links (name/title/description/source), copy the shareable URL, toggle active/inactive, and see submission counts per form.

---

# Section 7 — Student Module

**Student list** (`students`): three mutually-exclusive tab views — Demo (hasn't attended yet) / Faol (Active) / Arxiv (Archived). Architecturally these are just two boolean flags on one row (`is_demo`, `is_archived`), but the UI presents them as three distinct destinations with separate empty-states and separate available row-actions. Search (2-character minimum), a date-range filter, server-side pagination (20/page). Columns: #, full name, phone, parent info (father+mother name+phone combined into one cell), Telegram status (badge + a "send test message" button), group badges, payment-status (clickable, opens the Vacation modal for Hunter/Admin), created date, updated date, status badge, and a tab-specific actions column.

**Student creation:** an "Add Student" modal, 10 fields — full name*, phone1*, father name/phone, mother name/phone, Telegram user ID (flagged as important since it's the only channel for automated parent notifications), notes.

**Student profile (Student Detail, `student_detail`):** a two-column layout. Left rail: avatar with photo-upload, contact-info card, group-membership badges, (demo students only) a group-attach card, a quick-actions card (toggle demo/active/archived). Right main panel, 4 tabs:
- **Ma'lumotlar (Info):** the editable profile form (same field set as creation).
- **To'lov (Payment):** this month's owed/paid/advance/debt summary + a recent-payments list.
- **Davomat (Attendance):** a camera-attendance table with 4 date-range presets (7/14/30/90 days).
- **Ta'til (Vacation):** vacation-date-range CRUD (Hunter/Admin only) — vacations exclude those days from what the student owes.

**Student editing:** the same info form as creation, minus two admin-only fields (advance balance, demo flag) which are only settable via other UI (the quick-actions card / a separate endpoint).

**Student status flow:** Demo → (attach to a group) → Active → (optionally) Archived, and the reverse (unarchive) is always available. Archiving a student removes them from active finance/attendance reporting without deleting their history.

---

# Section 8 — Teacher Module

There is no single "Teacher" section in the sitemap — a teacher's experience is assembled from several pages gated to their role:

- **Teacher Dashboard** (`teacher_dashboard`) — their home page, fully described in Section 5.2. This is the closest thing to a "teacher profile" screen — it's where they see their own groups, own pay, and own certificate queue, rather than a dedicated profile page.
- **Group Detail** (`group_detail`) — teachers get access here scoped to *their own groups only* (both frontend-gated via page access and re-checked server-side). This is where they actually run class: take attendance, send homework, generate certificates.
- **Schedule:** there's no dedicated calendar/schedule screen — a teacher's "schedule" is implicit in which groups they're assigned to and each group's day-of-week/time fields (visible on the group card and in Group Detail).
- **Attendance:** Today's Attendance (`today_attendance`, locked to today's date for teachers, unlike Admin who can pick any date) is the fast daily roll-call; Group Detail's monthly grid is the fuller historical view.
- **Salary connection:** the "Maosh hisobi" tab of Teacher Dashboard shows their own formula breakdown (`GET /salary/me`) — this is a read-only, self-service mirror of what Admin sees company-wide on the Salary and Teacher Salaries pages. The underlying formula: a fixed base salary plus a per-student-per-lesson share, where each group's fixed monthly "pool" amount is divided by that month's actual lesson count to yield a per-lesson rate, multiplied by how many lessons each student attended. This means **a teacher's pay is directly, causally driven by the attendance data they themselves record** — an important product fact for any redesign emphasizing that connection (e.g. surfacing "your attendance-marking directly affects this number" more clearly than today's disconnected pages do).

Teachers do not appear as full CRUD-manageable entities on their own dedicated page from their own perspective — from an Admin's perspective, teachers are just Users with `role=teacher`, managed on the Users page like any other staff account, and separately assigned to groups via each Group's edit form (a single teacher-select dropdown, no dedicated "assign teacher" flow).

---

# Section 9 — Finance Module

Money-related functionality is spread across **six distinct sub-areas**, all reading/writing overlapping data:

1. **Payments** (`payments`) — the transactional ledger. For any (student, group, month, year) combination, the backend computes `expected` (tariff price, adjusted for vacation days and any special discounts), `paid` (sum of recorded payments), `remaining`, and a status of paid/partial. A "via Sales" toggle flags a payment as sales-role-attributed for referral-conversion stats (this is a one-time, irreversible flag per the underlying data model). List view has a KPI row (total debt, debtor count, this-month paid, this-month expected), a List/Debtors toggle, Excel export, and printable receipts (opened via a short-lived, single-purpose download token rather than the normal long-lived auth token, for URL-safety).
   - **Form:** student* (locked once editing), group* (locked once editing), amount* (>0), month*, year* (≥2020), notes, "via Sales" toggle. A live expected/paid/remaining preview recalculates as fields change.
   - **Table (List):** 9 columns, month/year + date-range filter, server pagination (25/page), no column sorting.
   - **Table (Debtors):** 7 columns, server-sorted by debt descending, no pagination (loads all debtors for the selected month at once), a one-click "pay in full" action per row.
2. **Debt management** — there's no dedicated "debt" page; debt is a *derived* value (payment_status + debt amount, computed server-side) surfacing in four different places: Students list, Student Detail, Payments' Debtors view, and Finance. This is a deliberate architecture (single source of truth) but means a redesign needs one consistent "debt" visual treatment usable across all four contexts.
3. **Finance** (`finance`, Admin only) — a per-group monthly collection-rate report: expected vs. actual per active group, expandable to see unpaid-only or all students per group with attendance-vs-amount-due detail. This is the only place with per-group financial granularity (Dashboard is company-wide, Payments is per-transaction).
4. **Discounts** — two systems exist, only one works: `Discounts.jsx` (generic named percentage discounts) is **completely broken/orphaned** — unreachable from any menu and its backend routes don't exist in production (confirmed 404). `Special.jsx` (per-student ad-hoc discounts: free-month / flat-monthly-reduction / one-time-amount) is the real, functioning mechanism that actually affects the payment math.
5. **Reports:** Excel export (available from Dashboard, Finance, and Payments, parameterized by month/year) and printable HTML payment receipts are the entire reporting/export surface — no PDF report generation, no scheduled reports, no email delivery of reports.
6. **Payroll/Salary** — `Salary.jsx` (Admin, editable, covers **every staff role**, not just teachers — includes an "internship" flag that zeroes pay, and an inline-editable amount cell that can override the auto-calculated formula per person per month) and `TeacherSalaries.jsx` (Admin, read-only, drills from company total → per-teacher → per-group → per-student attendance share, for teachers specifically). Both share the same underlying formula described in Section 8.

**Forms in this module:** Add/Edit Payment (above), Add/Edit Expense (name*, amount* >0, category Other/Staff-salary select — with a conditional staff-picker field when category=salary; note two separate implementations of this exact form exist, one inline on Dashboard and one on the standalone Expenses page, with slightly different field sets), Add/Edit Tariff (name*, price* >0, description), Add/Edit Course (name*, description, total lessons* ≥1, duration in months ≥1), Add Special Discount (student*, group — optional, blank means "all groups", kind* one-time/monthly/free-month with conditional amount/month fields, reason), Salary inline-edit (single numeric field replacing a table cell).

**Tables in this module:** Payments List (9 cols), Payments Debtors (7 cols), Dashboard's inline Expenses (3 cols + total), Dashboard's monthly history (7 cols), Finance's per-group breakdown (expandable), Teacher Salaries (nested expandable), Salary (6 cols, inline-edit), standalone Expenses (6–7 cols), Tariffs (6 cols), Courses (6 cols), Special discounts (8 cols). None of these have column sorting; only Dashboard/Finance/Payments have any pagination at all, and even there it's inconsistent.

---

# Section 10 — Attendance Module

Attendance is handled by **three separate, purpose-specific surfaces** rather than one screen — a deliberate design decision worth preserving conceptually in a redesign, even if the visual execution changes:

1. **Group Detail's monthly grid** (`group_detail`, "Yo'qlama" tab) — a full spreadsheet: one row per student, one column per calendar day of the selected month. Non-lesson-day columns render greyed/non-interactive; lesson-day columns are click-to-cycle (present ✓ → absent ✗ → unmarked –). A "Dars qo'shish" (add lesson date) control validates the chosen date against the group's weekly schedule before allowing it. Each date column header has a delete action (removes all attendance for that date, with a confirmation). Side stat cards show monthly completion %, remaining lesson count, and average attendance %.
2. **Today's Attendance** (`today_attendance`) — the fast daily version, decoupled from any specific month view. Shows cards for every group scheduled on the selected date (Admin can pick any date; Teacher is locked to today), each tagged "Done"/"Pending." Tapping a card opens a full-bleed tap-list — every student is one large tappable row that flips present/absent, plus "mark all present/all absent" shortcuts and a live running counter. Admin-only: a Holidays manager (name + date range) that surfaces as a warning banner if the selected date falls inside one.
3. **Camera attendance** (read-only) — populated automatically by a separate face-recognition service (`camera/` — hits a `POST /camera/checkin` endpoint). Surfaced identically (a 4-range date filter: 7/14/30/90 days) in three places: Group Detail's "Kamera" tab, Student Detail's "Davomat" tab, and a per-row modal on the Students list.

**Reports:** attendance data itself doesn't have a standalone reporting page — it's consumed downstream by the Salary/Teacher Salaries pages (as the input to the pay formula) and by Finance (attendance-vs-amount-due per student).

**Forms:** none in the traditional sense — attendance-marking is a click-driven state toggle, not a form submission. The only true forms in this module are Add-Lesson-Date and Manage-Holiday (name*, start date*, end date* ≥ start).

---

# Section 11 — Reporting & Analytics

**This is honestly the thinnest part of the product, and that thinness is itself an important finding for the redesign brief.** Concretely, verified in code:

- **No charting library exists anywhere in the project** (confirmed: `package.json` has no chart/graph dependency of any kind — no Recharts, Chart.js, D3, Victory, Nivo, or similar). Every "chart" in the app is a hand-built set of `<div>` elements with CSS height/width percentages simulating bars. There are **three separately implemented, non-shared bar-chart components** doing this (Dashboard's annual chart, Leads Analytics' two internal charts), each with its own markup, its own number-formatting conventions, and its own color logic.
- **No export beyond Excel and browser-print.** The only data-export mechanism in the entire app is one Excel-download endpoint (available from Dashboard/Finance/Payments, parameterized by month/year) and the browser's native `window.print()` (used only for certificate printing). There is no CSV export, no PDF report generation, no scheduled/emailed reports, no data-export from Leads, Students, or any other module.
- **"Analytics" formally exists only inside the Leads module** (the third tab of the Leads page — conversion rate, source performance, comment activity, referral funnel). No other module (Students, Attendance, Finance) has an equivalent analytics view; their "analytics" is really just the raw tables and the Dashboard's KPI cards.
- **No saved views, no custom report builder, no dashboards-per-user** — every "report" a user sees is a fixed, hardcoded screen; there is no way for any role to build or save a custom view of the data.

**Implication for the redesign brief:** if "better reporting/analytics" matters to the business, this is close to a greenfield opportunity rather than a "polish the existing charts" task — there is genuinely very little to preserve here beyond the *content* (which numbers matter: income, debt, conversion rate, attendance rate, payroll cost) since the *presentation* layer is minimal hand-rolled HTML/CSS with no reusable charting foundation.

---

# Section 12 — Table Inventory

Every distinct data table in the app (43 total), with columns/filters/sort/pagination behavior. (`.data-table` is the shared CSS class where noted; several "tables" are actually card-lists or custom grids, flagged as such.)

1. **Lessons list** — not a table, a reorderable card-list (▲▼ arrows), filtered only by the sidebar's category tabs.
2. **Audit Log panel** (Lessons) — list-style, date-range filterable, fixed page size 100, no sort.
3. **Leads List view** — # / Name / Phone / Source / Stage badge / Time-or-note / (Hunter, role-gated) / Actions. No sort, no client pagination (all leads load at once — a real scale risk as lead volume grows).
4. **Students list** — 11 columns (Section 7). Search + date filter, server pagination (20/page), no sort.
5. **Groups** — card grid, not a table.
6. **Group Detail attendance grid** — dynamic column-per-day, no pagination (full month always renders), no sort.
7. **Group Detail student summary** — styled list, not a `<table>`.
8. **Group roster modal** — # / Name / Phone / Tariff / Joined / Remove. No sort/filter/pagination.
9. **Payments list** — 9 columns, month/year + date-range filter, server pagination (25/page), no sort.
10. **Payments Debtors** — 7 columns, server-sorted by debt descending, no pagination.
11. **Dashboard inline expenses** — 3 columns + footer total, month/year filter only.
12. **Dashboard monthly history** — 7 columns, full year, fixed reverse-chronological order.
13. **Finance per-group breakdown** — expandable, unpaid-only/all toggle, no pagination.
14. **Teacher Salaries** — nested expandable (teacher → group → student), no pagination/sort.
15. **Salary** — 6 columns, inline-edit cell, no pagination/sort.
16. **Expenses (standalone)** — 6–7 columns (role-conditional actions), month/year filter, footer total, no pagination/sort.
17. **Tariffs** — 6 columns, no filter/sort/pagination.
18. **Courses** — 6 columns, no filter/sort/pagination.
19. **Discounts** (broken/orphaned page) — 5 columns.
20. **Special discounts** — 8 columns, no filter/sort/pagination.
21. **Academic → Grades tab** — 9 columns, filtered by student dropdown.
22. **Academic → Coins tab** — 8 columns + a separate top-10 leaderboard table.
23. **Academic → Feedback tab** — 7 columns.
24. **Academic → Certificates tab** — 7 columns.
25. **Academic → Events tab** — 7 columns (6 for non-admin — actions column hidden).
26. **Feedback Inbox** — card-list with status tabs (New/No-answer/Resolved/All), not a table.
27. **Notifications main table** — 5 columns (photo/name/telegram/status/actions), search only.
28. **Notifications today-history** — 5 columns, always today, no filter.
29. **ChatBot chat list** — card-list, live search, not a table.
30. **Parents** — 7 columns (6 for non-managers), search only.
31. **Users** — 7 columns, client-side search only (all users loaded at once).
32. **Employees (audit)** — 6 columns, no filter/sort/pagination.
33. **Audit Warnings** — 8 columns, filterable by staff dropdown, no pagination.
34. **My Warnings** — 6 columns, no filter.
35. **Bot Admin → Employees tab** — 5 columns.
36. **Bot Admin → Roles tab** — 5 columns.
37. **Bot Admin → Admins tab** — 4 columns.
38. **Today's Attendance groups grid** — cards, not a table.
39. **Today's Attendance tap-list** — styled div rows, not a table.
40. **Student Detail camera-attendance** — 4 columns, 4-way date-range filter.
41. **Student Detail recent-payments** — styled list, not a `<table>`.
42. **Salary breakdown modal** — 6 columns.
43. **Teacher Dashboard salary breakdown** — 3 columns.

**Cross-cutting fact for the redesign:** a generic reusable pagination component exists but is wired into only 4 of these 43 views (Students, Groups, Payments-list). Roughly 31 of 43 tabular views load their entire dataset client-side with zero pagination and zero column sorting anywhere in the app — this is a systemic pattern, not scattered inconsistency, and any redesign that introduces a new shared table component should make pagination + sorting the default rather than opt-in.

---

# Section 13 — Form Inventory

Every distinct form (40 total), field-by-field:

1. **Login** — username*, password*.
2. **Public Intake** — full name* (≥2 chars), phone* (≥7 chars), course interest (select), parent phone, notes.
3. **Profile edit** — full name, current password, new password (≥8 chars), confirm password (must match).
4. **Add Lesson** — lesson number* (positive int, unique), title* (≥1 char), section.
5. **Lesson edit (inline)** — section, guide, homework, extra notes (all optional freeform).
6. **Add/Edit Lead** — full name* (2–200), phone* (7–30), course interest, source, DOB, parent phone ×2, interested group, notes.
7. **Lead stage move** — stage selection (pill grid) + optional callback datetime.
8. **Reminder create** — due datetime*, body, kind (fixed to "call" in the UI).
9. **Lead Stage create/edit** (admin) — name* (1–80), color (14-swatch picker), kind (lead/won/lost).
10. **Intake Form create** (admin) — name* (1–150), title, description, source.
11. **Add/Edit Student** — full name* (2–200), phone1* (7–20), father/mother name+phone, Telegram ID (flagged important), notes.
12. **Vacation** — start date*, end date* (must be ≥ start), reason.
13. **Attach-to-Group** — group* (select).
14. **Add/Edit Group** — name* (2–200), stage (select — only 2 of 4 defined stages are actually selectable, a known gap), teacher, tariff* (auto-fills price), schedule (even/odd days), lesson time, start date, Telegram chat ID.
15. **Homework send** — text* (≥2 chars), auto-linked to the curriculum's next lesson.
16. **Certificate generate** — course label, issue date (freeform text, not a date picker), signer name (defaults to the CEO's name), signer title (fixed "CEO").
17. **Certificate inline edit** — a WYSIWYG pattern: every field is directly editable text on the printable certificate artwork itself, saved on blur (no separate form UI at all — worth preserving as a pattern, though its "this is editable" affordance needs work, see Section 17).
18. **Add/Edit Payment** — student* (locked once editing), group* (locked once editing), amount* (>0), month*, year* (≥2020), notes, "via Sales" toggle.
19. **Add/Edit Expense** — name*, amount* (>0), category (Other/Staff-salary), staff (conditional).
20. **Add/Edit Course** — name* (2–200), description, total lessons* (≥1), duration in months (≥1).
21. **Add/Edit Tariff** — name* (2–200), price* (>0), description.
22. **Add/Edit Discount** (broken/orphaned page) — name*, percent* (1–100), description.
23. **Add Special Discount** — student*, group (optional = all groups), kind* (select, conditionally reveals amount/month fields), reason.
24. **Salary inline edit** — a single numeric input.
25. **Add/Edit User** — username* (create-only), full name, password (≥8 chars, optional on edit), role* (7-option select), expiry date, Telegram chat ID.
26. **Block User** — reason* (≥3 chars), contact* (≥3 chars).
27. **Broadcast message** (two near-duplicate implementations: Users, Parents) — text* (1–4000 chars).
28. **Add/Edit Parent Account** — full name* (2–200), phone* (7–30), username (optional, defaults to phone), password (optional, ≥6 chars, auto-generated if blank), children (multi-select, ≥1 required).
29. **Grade** — student* (cascades from group), subject* (1–200), score* (≥0), max score (default 100), exam type (select), exam date, comment.
30. **Coin give/deduct** — student* (cascades from group), amount* (1–1000 give / 1–100000 deduct), reason.
31. **Feedback (teacher comment)** — student* (cascades from group), comment* (≥2 chars).
32. **Certificate (simple, Academic tab)** — student*, title* (2–300), file URL* (via upload or manual paste), issue date.
33. **Event** — title* (2–300), description, event date* + event time, location.
34. **Staff Warning** — staff*, mode toggle (from-codebook / freeform), discipline code* (severity-grouped) OR severity*+reason* (freeform).
35. **Telegram link** (Employees) — Telegram chat ID (freeform, with instructions).
36. **Bot Role create** — name* (1–64), "is parent role" checkbox.
37. **Bot Settings** — freeform key-value text pairs, no typed schema.
38. **Bot Admin promote/invite-link** — employee select + tier select.
39. **Holiday** — name* (2–300), start date*, end date* (≥ start).
40. **Attendance save** — not a traditional form; a click-driven state cycle (see Section 10).

---

# Section 14 — Modal Inventory

**Full-screen/overlay panels (not centered dialogs):** the Lead Drawer (slide-over side panel), the Funnel Board (full-screen pannable/zoomable canvas), the Group Certificates viewer (full-screen printable certificate designer).

**Standard centered dialogs (~35 of them):**
1. Profile edit — trigger: sidebar avatar pencil icon.
2. Add Lesson — trigger: Lessons page "Add" button.
3. Add/Edit Lead — trigger: Leads "Add Lead" button or row edit.
4. Stage Manager — trigger: Leads admin "manage stages" button.
5. Intake Form Manager — trigger: Leads admin "manage forms" button.
6. Add/Edit Student — trigger: Students "Add" button or row edit.
7. Vacation — trigger: Student Detail "Ta'til" tab / Students list payment-status cell.
8. Attach-to-Group — trigger: demo student's "attach" action.
9. Add/Edit Group — trigger: Groups "Add" button or card edit.
10. Group roster ("Talabalar") — trigger: group card's roster button.
11. Homework send — trigger: Group Detail's homework-send button.
12. Certificate generate (settings) — trigger: Group Detail / Teacher Dashboard certificate button.
13. Add/Edit Payment — trigger: Payments "Add" button or row edit.
14. Add/Edit Expense (Dashboard-inline variant) — trigger: Dashboard's expense table "Add"/edit.
15. Add/Edit Expense (standalone variant) — trigger: Expenses page "Add"/edit.
16. Add/Edit Course — trigger: Courses "Add" button.
17. Add/Edit Tariff — trigger: Tariffs "Add" button.
18. Add/Edit Discount — trigger: the orphaned Discounts page (unreachable in practice).
19. Add Special Discount — trigger: Special page "Add" button.
20. Salary breakdown — trigger: Salary page's per-row breakdown action.
21. Add/Edit User — trigger: Users "Add" button or row edit.
22. Block User — trigger: Users row "block" action.
23. Permanent Delete User — trigger: Users row "delete" action (danger-styled footer).
24. Broadcast (Users) — trigger: Users page broadcast button.
25. Broadcast (Parents) — trigger: Parents page broadcast button.
26. Add/Edit Parent Account — trigger: Parents "Add" button or row edit.
27. One-time Credentials Reveal — trigger: automatically shown right after creating a Parent account.
28. Link Child — trigger: Parents row "link child" action.
29. Grade/Feedback/Certificate/Event/Coin (Academic) — one shared modal shell whose content switches by the active tab; trigger: each tab's "Add" button.
30. Staff Warning — trigger: Audit Warnings or Employees page's "issue warning" action (same shared component, two entry points).
31. Telegram Link — trigger: Employees row's "link Telegram" action.
32. Bot Role create — trigger: Bot Admin's Roles tab "Add" button.
33. Holiday manage — trigger: Today's Attendance admin-only "Holidays" button.
34. Certificate settings (Teacher Dashboard variant) — trigger: Teacher Dashboard's certificate button (a near-duplicate of #12).

**Confirmation dialogs:** the app uses the browser's native, unstyled `window.confirm()` for **every single destructive action app-wide** — delete lesson/lead/tariff/course/discount/vacation/holiday, archive student/group, delete/void a payment, revert a salary override, cancel a coin transaction, and permanent-delete a user. This is a consistent, deliberate pattern (not a one-off oversight), but it means the single most consequential action in the app (permanently deleting a staff account) gets the exact same low-ceremony system dialog as toggling a minor setting — a clear redesign target (see Section 18).

---

# Section 15 — Component Inventory

**Page-level components** (one per sidebar destination): Lessons, Leads, Students, StudentDetail, Groups, GroupDetail, Payments, Dashboard, Finance, Tariffs, Courses, Discounts (orphaned), Special, Salary, TeacherSalaries, TeacherDashboard, Expenses, Academic, FeedbackInbox, Notifications, ChatBot, Parents, Users, Employees, AuditWarnings, MyWarnings, BotAdmin, TodayAttendance, PublicIntake, Login — 30 page-level files total.

**Genuinely reusable shared components:**
- **Pagination** — page-window control with ellipses and a count label; used in only 3 of the app's 43 tabular views (Students, Groups, Payments-list).
- **ProgressBar** — a single generic fill-bar; used only for curriculum-completion %. Every *other* progress bar in the app (group course progress, salary payment %, finance collection rate) is a bespoke inline-styled div rather than reusing this component.
- **DateFilter + DateRangePicker** — a well-built pair: preset buttons (All/Today/7 days/This month) plus a custom two-click calendar range-picker with hover preview. Used consistently across Students/Groups/Payments/Audit Log — this is one of the app's better-executed shared patterns, worth preserving.
- **MinaretLogo** — the theme-aware animated brand mark (an 8-pointed star), used in the Sidebar, Login, and Public Intake.
- **MinarWatermark** — a large background watermark version of the same mark, layered subtly behind all page content.
- **StaffWarningModal** — genuinely shared between Audit Warnings and Employees.
- **GroupCertificates** — genuinely shared between Group Detail and Teacher Dashboard.

**Locally-scoped "components" that are really only used in one place** (worth flagging because a redesign's shared component library should extract and generalize these, since equivalent needs recur elsewhere but currently get re-implemented locally each time): NotificationBell, ListView, LeadDrawer, StageManager, FunnelBoard, Analytics, CommentStats, IntakeFormManager (all defined inside Leads.jsx), KpiCard/InfoChip/TabBtn/DayFilterBtn (defined inside TeacherDashboard.jsx only — despite Dashboard.jsx, Finance.jsx, and Salary.jsx all needing equivalent KPI-card markup and each reimplementing it separately), RecordPaymentModal/VacationModal/AttachGroupModal/StudentAvatar (inside Students.jsx/StudentDetail.jsx), SkeletonCard/SkeletonColumn/KanbanSkeleton (inside Leads.jsx — the only skeleton-loading implementation anywhere in the app), EmployeesTab/RolesTab/SettingsTab/AdminsTab/InvestorsTab (inside BotAdmin.jsx).

**Primitives that exist only as CSS classes, not as components:** buttons, inputs, modals, tables, badges, cards, toolbars, tabs — see Section 16 for the full design-token audit. The practical implication: a component library rebuild has almost no existing React component layer to migrate — it's effectively a from-scratch build guided by these CSS class names as a naming/behavior reference, not a refactor of existing components.

---

# Section 16 — Design System Audit

All values below are pulled directly from the live `styles.css` (3,205 lines, the single global stylesheet — there is no CSS framework, no component library, and no design-token build tooling of any kind in this project).

**Colors:** A token system is defined once (`:root`, top of file): `--bg #f5f5f5`, `--surface #fff`, `--surface-2 #fafafa`, `--primary #0a0a0a` (near-black — this is **ink black used as the primary action color, not a brand hue**; there is no distinct brand color in the token system today), `--text #0a0a0a`, `--text-2 #333`, `--muted #737373` / `--muted-2 #a3a3a3`, `--border #e8e8e8` / `--border-2 #d4d4d4`, and semantic colors `--success #16a34a`, `--danger #dc2626`, `--warning #d97706` (each paired with a lighter `-bg` tint variant). A parallel **dark theme** and a third **"ocean" theme** (a blue/slate palette) redefine the same variable names under `[data-theme="dark"]` / `[data-theme="ocean"]` selectors — the token *architecture* is genuinely sound (three real themes, one variable set). The problem is coverage: the entire Login page, most of Teacher Dashboard, and several per-file "role color" / "stage color" JS lookup objects hardcode their own literal hex values completely outside this token system, so those specific screens don't participate in the theme switcher at all (see Section 17 findings #1 and #26).

**Typography:** One font family is actually used: `'Inter'` (loaded from Google Fonts CDN), applied globally. A second, self-hosted font family (`Geist` + `Geist Mono`) is loaded on every page load but is referenced by **zero** `font-family` rules anywhere in the codebase — pure dead weight today, though Geist Mono's tabular figures would be a genuinely good fit for this app's many money/count-heavy tables if actually adopted. There is **no defined type scale** — font sizes are freehand literals chosen per component; body text alone ranges across at least six different pixel values (11px/12px/12.5px/13px/13.5px/14px/15px) with no naming convention distinguishing "this is body text" from "this is a caption."

**Spacing:** No spacing scale/tokens exist — every padding/margin/gap is a literal pixel value chosen ad hoc. Common values cluster around 4/6/8/10/12/14/16/18/20/24px, but the same visually-equivalent gap between structurally similar elements is inconsistently 8px in one component and 10px in another.

**Buttons:** A reasonably solid core system exists (`.button` = solid black primary, `.secondary` = bordered white, `.small` size variant, `.danger` = red) alongside an icon-only variant (`.btn-icon`). However, **3 to 5 parallel "small button" implementations coexist** doing visually similar jobs with different exact metrics: `.button.small`, a separate `.btn-sm` class, ad hoc inline-styled buttons inside Teacher Dashboard, the Login page's own `.lp-btn`/`.lp-btn-secondary` system, and the certificate designer's own scoped `.mcert-btn` system.

**Inputs:** This is **the single largest concrete defect found in the whole system**: two parallel, non-interoperable input systems exist. `.field`/`.field-sm` is properly tokenized and used across roughly 22 of the app's 42 components. But `.form-input`/`.form-label`/`.form-group` — used in **6 files: Users, Salary, Expenses, Parents, BotAdmin, and Dashboard's inline expense modal** — has **zero matching CSS rules anywhere in the 3,205-line stylesheet** (confirmed by exhaustive grep, no partial match either). Every text input and label on those six pages — which include core admin workflows: staff account creation, payroll editing, expense entry, and parent-account creation — currently renders as a raw, unstyled browser-default input: no border-radius, no focus ring, no font consistency with the rest of the app. **This is a functional bug hiding as a design problem** and should be flagged early in any redesign scoping conversation.

**Cards:** No single base `.card` class exists — `.kpi-card`, `.group-card`, `.chart-card`, `.info-card`, and `.panel-card` are five independently defined, near-duplicate classes with overlapping but not identical padding/radius/shadow/hover-lift behavior.

**Tables:** One shared `.data-table` base class (consistent header/cell padding, hover row-highlight) is used fairly disciplined across the app — this is one of the stronger, more consistent parts of the current system and a reasonable pattern to build the redesign's table component on top of conceptually, even while replacing the visuals.

**Badges:** Generic `.badge` and semantic `.status-badge` (active/inactive) classes exist, but the large majority of *colored* badges (payment status, lead stage, warning severity, staff role) are done via **per-instance inline styles** rather than a shared badge-variant system, with role-color and stage-color lookup tables independently copy-pasted across at least four different files.

**Modals:** The best-unified part of the system — a consistent `.modal-overlay`/`.modal-header`/`.modal-body`/`.modal-footer` structure with a shared entrance animation is used by the large majority of the ~35 modals. Two notable exceptions bypass it entirely (the Salary breakdown modal, and the certificate designer, which is intentionally a full-bleed print surface rather than a form dialog).

**Sidebar:** Always rendered black regardless of active theme (a deliberate design choice, not a bug — there are dedicated theme-specific override rules that slightly re-tint it rather than leave it broken). Fixed 256px width, collapses to an off-canvas drawer with a hamburger toggle under 768px.

**Navigation:** Nav buttons themselves are visually consistent, but section grouping uses a plain uppercase label with no collapse affordance except the one special-cased Lessons category sub-list — for the Admin role this produces a single unbroken scroll of roughly 19 nav buttons with no search, favorites, or collapsibility (Section 4 covers this in detail — it's one of the top redesign priorities, see Section 18).

---

# Section 17 — UX Problems

Specific, code-cited findings (each names the exact file/class/component where it occurs) — extending, not just repeating, the prior engineering audit's list.

1. **Teacher Dashboard (the Teacher role's home page) is invisible to the theme system.** It's built from ~110 inline `style={{}}` blocks with hardcoded hex colors rather than the shared CSS classes — a teacher who switches to dark/ocean mode sees a jarring pure-white dashboard while the sidebar and every surrounding page goes dark. This is the single highest-traffic non-admin page in the app.
2. **Two font families load on every page; only one is ever used**, doubling font-load cost for zero visual benefit (Geist/Geist Mono imported in `main.jsx`, never referenced in any `font-family` rule).
3. **Six core admin screens (Users, Salary, Expenses, Parents, BotAdmin, Dashboard's expense modal) use a CSS class set — `.form-input`/`.form-label`/`.form-group` — that has zero matching rules in the stylesheet.** Every input on these pages renders as a raw unstyled browser default. This is functionally a bug, not just a polish gap, and should be fixed or explicitly absorbed into redesign scope early.
4. **The Discounts page is completely dead** — unreachable from any navigation, and its backend API routes don't exist in production (confirmed 404). A redesign should not spend any design effort here; `Special.jsx` is the real, working discount mechanism.
5. **A "Record Payment" modal defined inside Students.jsx references functions/icons that are never imported** — dead code today, but a landmine if wired up later without review.
6. **Role-based access control is defined in three separate hand-maintained places** (frontend sidebar logic, frontend page-access table, backend endpoint guards) that must be kept in sync manually — not a visual issue, but directly relevant to redesign scoping, since adding new roles/pages during a redesign risks the same drift unless consolidated.
7. **Role-name-to-color and role-name-to-label mappings are independently copy-pasted in at least four files** — a role rename today requires editing five places and is guaranteed to drift eventually.
8. **The lead-to-student conversion has no actual "convert" action** — moving a lead's pipeline stage to "Paid/Enrolled" is purely cosmetic on the Leads page; creating the actual Student record is a separate, disconnected manual action on a different page with no field carry-over. This is a genuine workflow gap, not just a visual one, and is a strong candidate for the redesign to actually fix functionally (a real "Convert to Student" action that pre-fills the new student form from the lead's data).
9. **Every destructive action app-wide uses the same unstyled native browser confirm dialog** — including the genuinely irreversible "permanently delete a staff account," which gets no more ceremony than deleting a minor vacation entry.
10. **"Notifications" names two unrelated features** — the sidebar page (actually a student arrival/departure visit log) and a bell-icon dropdown inside Leads (actual system notifications). A user looking for "my notifications" has two equally-named, functionally unrelated destinations — a naming/IA fix, ideally addressed in the redesign's navigation restructuring.
11. **Payments and Expenses each have two identical-but-differently-labeled sidebar entry points** for different roles pointing at the exact same screen, with no visual signal that they're the same page.
12. **No pagination on ~31 of the app's 43 tabular views** — as data volume grows (leads, payments, users, warnings), these will degrade badly; this is systemic, not scattered.
13. **No column sorting anywhere in the entire app**, including on the few tables that do paginate.
14. **The Add/Edit Group form only exposes 2 of 4 modeled course stages** — no UI path exists to create a new Frontend or Backend stage group, only to view legacy groups that already have that value.
15. **Only 8 responsive breakpoints exist for a data-dense back-office application** — the Leads kanban, the Group Detail attendance grid (up to 31 date columns wide), and the Funnel Board canvas have essentially no tailored mobile/tablet handling and rely on generic overflow scroll.
16. **Accessibility attributes are almost entirely absent outside the Leads module** — icon-only buttons across the rest of the app have no `aria-label`, and no modal besides Leads' own has focus-trapping or `role="dialog"`/`aria-modal` wiring. `alt` text on images (avatars, student photos) is present on only two instances codebase-wide.
17. **Three to five overlapping "small button" visual systems coexist** with no single canonical secondary-action button style.
18. **Two independent Add/Edit Expense modal implementations** (Dashboard-inline vs. standalone Expenses page) have different field sets — editing an expense's category requires knowing to go to the standalone page even if you found the expense via the Dashboard.
19. **Two near-identical Broadcast-message modal implementations** (Users, Parents) are copy-pasted with only the audience/endpoint differing.
20. **Certificate inline-editing (a nice WYSIWYG pattern) has almost no "this is editable" affordance** beyond a subtle underline on one field — most editable fields on a certificate look like static print text until discovered by accident.
21. **The hand-rolled hash router has no 404/not-found state** — an unrecognized URL hash simply renders a blank content area with no error or redirect.
22. **The sidebar has exactly one collapsible nav group out of roughly eleven sections**; the Admin role in particular faces an unbroken ~19-button scroll with no search, favorites, or grouping beyond flat labels.
23. **The Login page is visually and structurally disconnected from the rest of the app** — its own color literals, its own button/input styling, and critically, it **never reflects the user's saved theme preference** — the first screen every user sees on every session ignores their theme choice, then the app "snaps" to their real theme immediately after authentication, a jarring first impression.
24. **Three separately-implemented bar charts exist with no shared charting primitive** (Dashboard, and two inside Leads Analytics), each with different number formatting and color logic — directly relevant given Section 11's finding that reporting/analytics is a near-greenfield redesign opportunity.
25. **The Funnel Board is a fully custom pan/zoom canvas** (drag-to-pan, ctrl+wheel/pinch-to-zoom, click-vs-drag disambiguation) built from scratch for a single, relatively rarely-used analytics drill-down, with no onboarding beyond one line of small gray hint text — worth questioning whether this complexity earns its keep versus a simpler static funnel visualization.
26. **Loading and empty states are inconsistent across the entire app** — most pages show a bare "Loading..." text swap; only the Leads kanban has a true skeleton loader; empty-state treatments range from a proper icon+title+subtitle pattern (Leads) to a stray emoji (Today's Attendance) to nothing distinctive at all elsewhere.
27. **Numeric and date formatting are both inconsistent app-wide** — some components format money with commas, others with Uzbek-convention spaces; some hand-roll date strings, others use locale formatting with differing option sets — with no single shared formatting utility anywhere in the codebase.
28. **A payment's "via Sales" attribution toggle**, which has real, irreversible business consequences (one-time referral crediting), is explained only via a hover tooltip — invisible on any touch device, and a poor pattern for a consequential, semi-hidden action.
29. **No unsaved-changes warning exists anywhere** — every edit modal in the app can be dismissed (✕, overlay click, or Escape) with in-progress edits silently discarded, with zero confirmation.
30. **No inline, field-level validation feedback in almost any form** — errors surface only as a toast notification after clicking Save, forcing the user to re-scan the entire form to find the offending field; only two forms in the whole app (Add Lesson, Login) show inline per-field error text.
31. **The lead pipeline promises a clean funnel from "New" to "Paid/Enrolled," but the actual enrollment step lives entirely outside the Leads page** (see finding #8) — this is a navigation/mental-model mismatch worth calling out specifically to a designer, since the visual pipeline implies a completeness that the underlying workflow doesn't deliver.
32. **Attendance-marking (a click-cycling state machine) and its downstream effect on teacher pay are conceptually connected but visually and navigationally distant** — a teacher marking attendance in Group Detail has no visible link to how that action will affect the number they'll later see on their own Salary tab, a missed opportunity for a more legible cause-and-effect UI.
33. **The app has zero saved/custom views** anywhere — every filter state (Students' tab, Payments' month, Leads' source filter) resets on navigation away and back, with no "save this view" or default-view-per-user concept, unusual for a tool this data-filter-heavy.
34. **Certificate generation, homework-sending, and salary-breakdown viewing are each reachable from two different pages with two separate, only loosely-synchronized implementations** (Group Detail vs. Teacher Dashboard for certificates; the general pattern of near-duplicate modals recurs at least four times across the app), suggesting the underlying information architecture would benefit from genuinely shared flows rather than per-context reimplementation.
35. **There is no in-app help, onboarding, or contextual documentation of any kind** — for an app this operationally dense (7 roles, 30 pages, formula-driven payroll, a pannable analytics canvas), new-staff onboarding currently depends entirely on verbal/external training, not the product itself.

---

# Section 18 — UI Redesign Priorities

Ranked highest to lowest impact, each justified by real usage/risk reasoning rather than aesthetic preference alone.

**Priority 1 — Teacher Dashboard.** Highest-traffic non-admin page (it's the entire Teacher role's home screen), currently the single worst offender for theme-breakage and inline-style sprawl (~110 inline style blocks). A ground-up rebuild here also naturally produces the app's first reusable `KpiCard`/tab-bar/info-chip components that Dashboard, Finance, and Salary could then also adopt instead of each reimplementing their own KPI-card markup — meaning this one page's redesign has outsized leverage on three other pages.

**Priority 2 — Input system unification (`.form-input` fix).** Currently breaks six of the app's most-used admin screens (Users, Salary, Expenses, Parents, BotAdmin, Dashboard's expense modal) with completely unstyled form fields. This is cheap to fix relative to its visual impact and should likely be treated as a pre-redesign hotfix rather than waiting for the full visual overhaul, since it's closer to a bug than a design opinion.

**Priority 3 — Leads module.** The busiest, most feature-dense, and (not coincidentally) the *best-executed* part of the current app — it already has the app's only skeleton loader, only real accessibility wiring, and a genuinely good stage-picker interaction pattern. It's high priority not because it's broken, but because it's the CRM's commercial core (every dollar the business makes starts here) and because fixing the lead→student conversion gap (Section 17, finding #8) is a functional win a redesign can deliver alongside the visual one.

**Priority 4 — Admin Dashboard + reporting/analytics as a combined effort.** Given Section 11's finding that there's effectively no shared charting foundation anywhere in the app (three independent hand-drawn bar charts, no library), redesigning the Dashboard is really an opportunity to establish the app's *entire* data-visualization language in one pass, then propagate it to Finance, Teacher Salaries, and Leads Analytics rather than solving charts four separate times.

**Priority 5 — Global input/button/card/badge design-token consolidation.** Not a single page but the foundational work (type scale, spacing scale, one canonical card/button/badge implementation) that every other page's redesign will be faster and more consistent for having done first. Ordered after the above four because it's less *visible* to any single user in isolation, but it's the multiplier that makes every subsequent page redesign cheaper and more consistent.

**Priority 6 — Sidebar/navigation restructuring.** High long-term value (the ~19-button unbroken Admin scroll is a real wayfinding problem, Section 17 #22) but lower urgency than the above since it doesn't block any individual page's redesign — can be tackled once the page-level component library exists, since the new nav should be built from the same token/component system.

**Priority 7 — Login page.** Low usage-frequency (seen once per session) but currently the most jarring, off-system screen a user encounters — worth a quick pass once the shared button/input/card system exists (it's mostly a matter of retrofitting existing tokens, not new design work).

**Priority 8 — Students/Groups/Attendance/Finance detail screens.** These are functionally solid and heavily used, but structurally more consistent already (they use the real `.field`/`.data-table` systems, not the broken ones) — they'll benefit automatically from the token-consolidation work in Priority 5 without needing bespoke redesign attention first.

**Priority 9 — Long-tail admin screens** (Bot Admin, Employees, Audit Warnings, Courses, Tariffs) — lowest usage frequency, lowest risk, can trail the rest of the redesign.

---

# Section 19 — Modernization Opportunities

Specific comparisons to how established products handle the same problems this CRM has, tied to concrete gaps found in this codebase (not generic platitudes):

**vs. Pipedrive / HubSpot (pipeline UX):** This app's Leads kanban already gets the fundamentals right — drag-and-drop stages, a claim/pool mechanic (an actual differentiator most generic CRMs don't need, since it solves this business's specific "who calls this lead" contention problem). What it's missing that Pipedrive/HubSpot both do well: **inline quick-actions on the card itself** (this app requires opening the drawer for almost everything except a drag-to-move — a one-click "log a call" or "set next action" directly from the card would reduce drawer-open frequency significantly), and **a genuine "won" handoff** — Pipedrive/HubSpot both trigger a structured next-step (deal→account conversion, or a task) the moment a deal is marked won; this app's "Paid/Enrolled" stage move is purely cosmetic (Section 17, finding #8) and should adopt this pattern directly: moving a lead to the won stage should open a pre-filled "create student" flow, not just recolor a kanban card.

**vs. Attio (data model flexibility & views):** Attio's core idea — that any list of records can be viewed as a table, board, or calendar, with user-saved filtered views — directly addresses two of this app's clearest gaps: **zero saved/custom views anywhere** (Section 17, finding #33) and the fact that Students/Groups/Payments each hardcode one specific presentation (Students is always a table, Groups is always cards) with no ability for a user to reshape it. A redesign doesn't need Attio's full flexible-schema ambition, but adopting "let a user save a named filter+sort combination per table" would meaningfully help the six-role, always-different-priorities user base this app actually has (a Hunter's default Students filter is not what a Metodist wants).

**vs. Close CRM (built-in calling/activity-first workflow):** Close is built around the idea that *calling* is the primary action, with everything else secondary. This app's Call Center role workflow is conceptually similar (their whole job is calling leads) but the current Leads UI treats "call" as just one possible stage-transition among several, with no dedicated "call mode" (e.g., a focused, keyboard-driven "call the next lead in my queue" flow). Given Call Center is one of only 7 roles and their entire job is captured by this one page, a Close-style "power-dial next lead" mode is a high-leverage, role-specific feature this redesign could introduce without touching any other module.

**vs. Linear (information density, keyboard-first navigation, command palette):** Linear's defining trait — nearly everything reachable via keyboard, a global command palette (Cmd+K), dense-but-legible tables — is almost entirely absent here. The one keyboard affordance that exists today (Leads' `/`-to-focus-search) is a good seed pattern that should be **generalized into an app-wide command palette**, which would also directly solve the sidebar wayfinding problem (Priority 6, Section 18) for the Admin role's ~19-button scroll — a command palette (jump to any page, any student, any group by typing) is a more scalable fix for that specific problem than trying to visually reorganize an ever-growing flat list. Linear's information density (compact rows, minimal chrome) is also a good reference point given how much of this app's data is genuinely tabular/dense (attendance grids, payment ledgers) — the current design leans toward generously-padded card grids (Groups, Today's Attendance) even in places where a denser, more scannable table would serve a power-user staff member better.

**A general modernization theme across all five reference products:** every one of them treats **inline editing** as a first-class pattern (click a cell, edit in place, save on blur) rather than "open a modal to change one field." This app has exactly one instance of that pattern today — the certificate WYSIWYG inline-edit (Section 13, form #17) and the Salary page's inline-edit amount cell — and it works well where it exists. Generalizing inline-editing to more of the app's simpler edit flows (e.g., editing a single tariff price, toggling a status) rather than opening a full modal for every edit would be a meaningfully more modern interaction model consistent with all five reference products.

---

# Section 20 — AI Redesign Brief

*(This section is intentionally self-contained — a designer working from this section alone, without reading anything above, has enough to start.)*

**Product summary:** This is the internal operating system for Minar Academy, a coding-bootcamp-style programming school. One web application fuses a sales CRM (lead pipeline), a student information system (roster, groups, attendance, grading, certificates), billing/finance (pricing, payments, debt, payroll), staff management (accounts, roles, an internal-discipline warning system), and admin tooling for a companion Telegram bot and a companion parent mobile app. There is no student- or parent-facing UI in this product — it's staff-only, used by roughly 7 distinct job functions inside one school.

**User roles (7, exhaustive):** Admin (full access/owner), Metodist/Support Teacher (curriculum), Teacher (own classes), Hunter (do-everything sales closer, the only non-admin role with finance access), Sales (lead-gen only), Call Center (phone qualification), Audit (internal staff discipline, a fully separate track from everything else). Full permission matrix in Section 2 — treat it as authoritative; it's pulled directly from the enforced backend/frontend access rules, not inferred.

**Sitemap recap (30 pages):** Login, Public Intake (unauthenticated), Lessons, Leads, Students (+ Student Detail), Groups (+ Group Detail), Payments, Dashboard, Teacher Salaries, Salary, Expenses, Tariffs, Courses, Finance, Special (discounts), Teacher Dashboard, Today's Attendance, Academic (5 sub-tabs), Feedback Inbox, Notifications (visit log), ChatBot, Parents, Users, Employees, Audit Warnings, My Warnings, Bot Admin. (Discounts exists in code but is dead — exclude it from redesign scope, or treat removing it entirely as in-scope cleanup.) Full per-page detail in Section 3.

**Core modules, ranked by business centrality:** (1) Leads/CRM — where revenue starts; (2) Students/Groups/Attendance — the operational core, largest daily-use surface across the most roles; (3) Finance/Payments/Payroll — where the money is tracked, six overlapping sub-screens sharing one derived-data model; (4) Staff/Audit — smaller but structurally distinct, worth its own coherent visual treatment rather than reusing CRM patterns since its users (Audit role) never see the rest of the app; (5) Bot/Parent admin — lowest-frequency, utility-grade screens.

**Design requirements, derived directly from the current system's real constraints:**
- Support **3 themes** (light/dark/"ocean") via CSS custom properties — the current token architecture for this is sound and should be preserved/extended, not reinvented.
- Design one canonical **input, button, card, badge, and confirmation-dialog** component — today there are 2 input systems (one completely unstyled/broken), 3–5 button systems, 5 card variants, and no styled confirmation dialogs at all (native `confirm()` used everywhere). This consolidation is the single highest-leverage foundational task.
- Design a **data-table component with built-in pagination and sorting as defaults**, not opt-in — 31 of 43 current tables have neither, and the app's data volume (student/lead/payment history) will only grow.
- Design a **KPI-card / stat-tile component** usable across Dashboard, Finance, Salary, Teacher Salaries, and Teacher Dashboard — currently reimplemented independently on each of these five pages.
- Design a **lightweight charting primitive** (bar charts at minimum) — there is currently no charting library and three independent hand-rolled implementations; Section 11 covers why analytics/reporting is close to a greenfield opportunity.
- Preserve and generalize two already-good existing patterns: the **stage-picker-as-colored-pill-grid** (Leads drawer) and **inline/WYSIWYG editing** (certificate designer, Salary's inline-edit cell) — both are better than "open a modal for everything" and should become the house style for simple edits, not the exception.
- Address the **role-scoped landing-page concept** thoughtfully — 7 roles land on 5 different default pages today (Section 2); the redesign should treat "what does role X see first" as a deliberate design decision per role, not an afterthought.

**UX goals, prioritized (full reasoning in Section 18):** (1) Fix the Teacher Dashboard — highest-traffic, most broken page. (2) Fix the six unstyled admin screens (`.form-input` bug) — cheap, high-impact, arguably pre-redesign scope. (3) Elevate the Leads module further (it's already the best part of the app) and close the lead→student conversion functional gap. (4) Unify Dashboard + all analytics/reporting around one charting language. (5) Build the foundational token/component system that makes every subsequent page cheaper to redesign. (6) Solve the Admin sidebar's ~19-button wayfinding problem, likely via a command-palette pattern generalized from the Leads page's existing `/`-search affordance rather than a purely visual nav reorganization. (7) Retrofit the Login page onto the shared system.

**Constraints to design within:**
- **No router today** — navigation is hash-based view-switching, not real URLs; a redesign can introduce real routing as part of the rebuild (this is an engineering decision more than a design one, but it affects whether deep-linking/back-button/shareable-URL behaviors can be promised in the new design).
- **No component library, no CSS framework** — the rebuild is effectively greenfield at the component layer; there's very little existing React component structure to preserve, only CSS class *names and behaviors* to reference as prior art.
- **7 roles, role-gating is pervasive** — nearly every screen has some role-conditional content; the design system needs a clean way to express "this element is role-gated" that a designer can hand off unambiguously (e.g., a documented per-role visibility matrix per screen, following the Section 2 pattern) so engineering doesn't have to re-derive access rules from a Figma file.
- **Money math is server-computed, not stored** — expected/paid/debt values are calculated on the fly; the design shouldn't assume any of these are simple stored fields that can be trivially resorted/refiltered client-side without a backend round-trip.
- **The camera-based attendance system and the Telegram bot are external services this app only displays/administers** — redesign scope should treat their data as read-only/administrative surfaces, not systems to redesign the internals of.
- **This is a live production tool for a real, currently-operating school** — any redesign needs a realistic migration/rollout path (even if out of scope for the visual design itself), since staff are actively using this daily to run the business right now.

---

*End of report. Companion file `UI_AUDIT_REPORT.md` (same directory) contains additional granular per-component engineering notes if deeper source-level detail is ever needed, though this document is designed to stand alone.*
