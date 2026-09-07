# IT Hub CRM — Product Architecture V2

**Prepared by:** Principal Product / SaaS Architecture review
**Source of truth:** `CRM_DISCOVERY_REPORT.md` + `UI_AUDIT_REPORT.md` (this document does not
re-derive facts from the codebase — every factual claim below is sourced from those two reports
or independently re-verified against the live app where noted).
**Scope:** Product architecture, information architecture, workflows, permissions, scalability,
roadmap. **This document does not specify UI, CSS, colors, or visual design** — a separate,
already-in-progress visual redesign (design tokens + component system) covers that track and is
referenced only where it's a dependency, never a deliverable, of this document.

**A note on currency:** two items the source reports flagged as broken have already been fixed
since those reports were written (confirmed directly against the live repo): the orphaned
`Discounts.jsx` page and its dead backend calls have been deleted, and the unreachable
`RecordPaymentModal` dead code in `Students.jsx` has been removed. The six-file `.form-input`
unstyled-input defect is also already resolved. These are noted inline, not presented as open
problems — this document reflects the *architecture*, which those fixes did not change.

---

## 1. Executive Summary

Minar Academy's CRM is not a generic CRM wearing an education skin — it is five fused systems
(sales pipeline, student information system, billing/payroll, staff management, and
bot/parent-app administration) running as one React + FastAPI application, serving 7 staff roles
across roughly 30 screens. The underlying data model is sound: money math is computed
server-side from a single source of truth (tariff × vacations × discounts), teacher payroll is
genuinely formula-driven from real attendance data, and the lead pipeline already has a
non-trivial "shared pool / claim" mechanic that most off-the-shelf CRMs don't even offer.

**The problem is not the data model. It is the architecture layer wrapped around it:**
navigation, permissions, cross-entity workflow, and scale-readiness.

Four architectural facts drive nearly everything in this document:

1. **Navigation is organized by department metaphor, not by business object or task frequency.**
   The Admin role faces an unbroken ~19-button flat sidebar scroll across five sections
   (Metodika/CRM/Akademik/Moliya/Boshqaruv) with only one collapsible group. Two pages
   (Payments, Expenses) are silently duplicated under two different labels for two different
   roles, with no visual signal they're the same screen.
2. **Permissions are hardcoded in three independent places** (frontend sidebar boolean logic,
   a frontend `PAGE_ACCESS` map, and per-endpoint backend guards) that must be hand-kept in
   sync. There is no permissions *data model* — access is 100% role-name string matching, with
   no granular capability system and no in-product way to manage roles at all.
3. **The product's single most important conversion — Lead → Student — is not a real system
   action.** Moving a lead to the "Paid/Enrolled" pipeline stage is cosmetic; creating the actual
   Student record is a disconnected manual action on a different page with zero field
   carry-over. The pipeline visually promises a handoff the workflow doesn't deliver.
4. **The app has no cross-cutting task, timeline, or notification system.** Reminders exist only
   inside Leads. Only Leads has an activity timeline. "Notifications" is the name of two
   unrelated features. 31 of 43 tabular views have no pagination and none have sorting — this is
   a systemic scale ceiling, not scattered inconsistency, and it will fail visibly well before
   20,000 students.

None of this requires a rewrite. It requires: one permission source of truth, a real
object-centric information architecture, a universal task/timeline layer, a closed
lead→student loop, and a scaling plan for the data/table layer executed *before* it's forced by
an outage. That is the substance of this document.

---

## 2. Current Architecture Analysis

### 2.1 The five fused systems

| System | What it owns | Business centrality |
|---|---|---|
| Sales CRM | Lead capture (manual / public intake form / Facebook Lead Ads webhook), pipeline kanban, shared-pool claiming, referral-source tracking | **1 — where revenue starts** |
| Student Information System (SIS/LMS) | Student roster, groups/cohorts, attendance (manual + camera face-recognition), grading, homework, certificates | **2 — largest daily-use surface, most roles touch it** |
| Billing & Finance | Tariffs, monthly payments, debt (derived), teacher/staff payroll (formula-driven), expenses, P&L | **3 — six overlapping screens sharing one derived data model** |
| Staff Management | Internal accounts/roles, an internal-discipline warning system delivered over Telegram | **4 — structurally separate; its one role (Audit) never touches the rest of the app** |
| Bot / Parent-app Administration | Admin surface for a separate Telegram bot (own SQLite DB) and a separate parent-facing mobile app (own account table) | **5 — lowest frequency, utility-grade, but growing (an investor-broadcast automation was added here most recently)** |

### 2.2 Roles (7, exhaustive — from `backend/models.py UserRole`, cross-checked against both
frontend access-control tables)

| Role | Summary | Default landing page |
|---|---|---|
| `admin` | Superadmin — every page, all finance, payroll, user mgmt, bot admin | Lessons (curriculum) |
| `support_teacher` (Metodist) | Curriculum owner + LMS admin (students/groups/academic). No CRM, no finance | Lessons |
| `teacher` | Own classes only — attendance, grading, own salary | Teacher Dashboard |
| `hunter` | "Do-everything" sales closer: leads, students/groups, **and** payments/expenses/parents/chatbot | Payments |
| `sales` | Lead-gen/referral only — leads + students/groups, explicitly no finance | Leads |
| `call_center` | Phone qualification — leads, students/groups, parent-feedback triage | Leads |
| `audit` | Fully separate track — staff discipline only, cannot see anything else | Employees |

Two structural observations worth carrying into every later section: **`hunter` is a superset
role** whose permission footprint overlaps `sales` + `call_center` + partial `admin` finance
access, and **`audit` is intentionally, completely isolated** (correct as designed — do not
merge it into the main nav in the redesign).

### 2.3 Permission architecture (as built today)

Access control is enforced independently in three places with no shared source:
1. `Sidebar.jsx` — per-button boolean flags (`isAdmin`, `hasCrmAccess`, etc.)
2. `App.jsx` — a `PAGE_ACCESS` allow-list map used to redirect users off pages they can't see
3. `backend/main.py` — per-endpoint `require_*` dependency guards (the actual security boundary)

All three are hand-maintained. A new role or page added to only one of the three silently
breaks either navigation or security. This is flagged in full in §14.

### 2.4 Cross-module dependency map (the parts of the system that are causally linked but not
navigationally connected — this is a recurring theme in this document)

- **Attendance → Payroll:** a teacher's pay is a direct function of attendance data they
  themselves record (fixed base + per-student-per-lesson share, lesson pool ÷ held-lesson-count).
  This is real, working automation — but the product gives the teacher no visible signal that
  today's attendance click is tomorrow's paycheck number.
- **Group.tariff → Payment.expected:** money owed is *computed*, not stored, from tariff price
  adjusted by vacation days and per-student special discounts. This is architecturally correct
  (single source of truth) but means the UI can never treat "debt" as a simple sortable/filterable
  stored column without a server round-trip — a real constraint on any future table/reporting work.
- **Lead.stage → Student creation:** *not* causally linked today despite looking like it is (§7).
- **Camera service, Telegram bot, Parent mobile app:** three external systems this app only
  *administers* (reads/writes their data over an API or a second SQLite DB) — not systems whose
  internals are in scope for this architecture review.

### 2.5 Strengths (preserve these, don't rebuild them)

- The lead **shared-pool/claim mechanic** — a genuine differentiator most CRMs don't model.
- **Server-computed, never-stored money math** — correct architecture for a domain with vacations
  and per-student discounts layered on top of pricing.
- **Formula-driven payroll directly tied to attendance** — real, working automation already.
- The **stage-picker-as-colored-pill-grid** interaction in the Lead drawer, and the certificate
  designer's **inline/WYSIWYG editing** — both better than "open a modal for everything" and
  worth generalizing as house patterns, not one-offs.
- `DateFilter`/`DateRangePicker` and `Pagination` — well-built shared components, just
  under-adopted (Pagination wired into only 4 of 43 tables).

### 2.6 Weaknesses / complexity points

- Flat, department-metaphor navigation with duplicate entry points and no search.
- No task/reminder/timeline system outside the Leads module.
- Six overlapping finance screens (Payments, Debtors, Finance, Special Discounts, Salary,
  Teacher Salaries) with no single "Finance home."
- Two independent implementations of the same form in four separate cases (Add/Edit Expense,
  Broadcast message, Certificate generation, Salary breakdown UI).
- No router / real URLs — hash-based view switching with `sessionStorage` hacks for
  drill-down state and no 404 handling.

### 2.7 Scaling problems (detailed in §16)

- **"Load everything, no pagination" is the default, not the exception** — 31 of 43 tabular
  views (Users, Leads list, Payments Debtors, Warnings, Parents, all of Academic's 5 tabs, and
  more) fetch the full table client-side with no server pagination and no column sorting
  anywhere in the app.
- **SQLite as the system of record** — fine at current scale, a real ceiling well before 20,000
  students (§16).
- **No search infrastructure** — every page has its own local text filter; there is no
  global/cross-entity search.
- **A single 6,900-line `main.py` holding all 194 routes** — an engineering maintainability risk
  more than a user-facing one, but it will slow every future feature this document recommends if
  left unaddressed.

---

## 3. Problems

This section synthesizes the source reports' 35 UX findings up to the *architecture* level
(pixel-level findings — button variants, unstyled inputs, hardcoded hex colors — belong to the
separate visual-redesign track already underway and are intentionally excluded here) and adds
the missing-module gap analysis requested for this review.

### 3.1 Navigation & information-architecture problems

| # | Problem | Why it's architectural, not visual |
|---|---|---|
| N1 | ~19-button unbroken Admin sidebar scroll, one collapsible group out of ~11 sections | No amount of visual polish fixes a list that grows linearly with feature count |
| N2 | Payments and Expenses each have two sidebar entry points for different roles | Signals a missing "this is one object, many roles reach it differently" model |
| N3 | No global search / command palette | The one keyboard affordance that exists (`/`-search in Leads) never generalized |
| N4 | No saved/custom views anywhere | Every filter state resets on navigation; a Hunter's default Students filter is not what a Metodist wants, yet both get the same hardcoded view |
| N5 | "Notifications" names two unrelated features (visit log page vs. system-notification bell) | A naming/IA collision, not a copy fix |
| N6 | No router, no deep links, no 404 handling | Blocks shareable URLs, browser-native back/forward reliability, and any future SEO/embed use case |

### 3.2 Workflow / lifecycle problems

| # | Problem | Business impact |
|---|---|---|
| W1 | Lead → Student conversion is cosmetic, not a real action (no field carry-over) | Every enrollment today re-types data a rep already captured; source/referral attribution can silently break at the handoff |
| W2 | No task/reminder system outside Leads | A Metodist, Teacher, or Finance user has no first-class way to say "follow up on this in 3 days" — it becomes a mental-load problem or a side-channel (Telegram DM) instead of a product feature |
| W3 | No activity timeline outside Leads | Students, Groups, Teachers, and Payments all have real history (payments, attendance changes, salary overrides) but no consolidated "what happened" view — support/dispute resolution relies on institutional memory |
| W4 | Attendance's causal link to payroll is invisible in-product | A teacher has no way to see "this action affects that number" without navigating to a separate page and mentally reconstructing the formula |
| W5 | No month-end close ritual | Admin already performs an implicit monthly close (payments recorded, payroll generated, expenses logged, report exported) with zero product support — pure tribal knowledge today |
| W6 | Graduated students become indistinguishable from dropped-out students (both just "archived") | No Alumni state means the school has no clean way to reuse graduate data for referrals/marketing/case studies |

### 3.3 Permission-architecture problems

Covered in full in §14; headline: three-source RBAC, no granular capability model, no in-product
role management (every role change today requires an engineer to edit code).

### 3.4 Data / scale problems

Covered in full in §16; headline: unpaginated tables are the default, SQLite is a medium-term
ceiling, there is no search infrastructure, and reporting queries currently compute live over raw
transactional tables (`stats_overview` etc.) rather than pre-aggregated data.

### 3.5 Feature-gap matrix vs. modern SaaS (ranked by business impact)

**High impact**

| Gap | Reference product doing this well | Why it matters here specifically |
|---|---|---|
| Real "Convert Lead → Student" action | Pipedrive/HubSpot's deal→account conversion | Closes W1 — the single highest-leverage functional fix in this whole document |
| Universal task/follow-up system | Every modern CRM (HubSpot, Attio, Pipedrive) | Closes W2; also the natural home for automation output (§13) |
| Command palette / global search | Linear | Directly solves the ~19-button sidebar problem more durably than any visual reorg (N1, N3) |
| Saved/custom views per user per table | Attio | Six roles, six different daily priorities, one hardcoded view each today (N4) |
| One permission/capability model | Any RBAC-mature SaaS | Removes the 3-source-drift risk (§14); blocks safely adding an 8th role today |
| Automated payment reminders (dunning) | Stripe Dashboard / any billing product | Debt collection today is 100% manual staff labor against a derived list |
| Pagination + sorting as table defaults | All five reference products | Non-negotiable before 5,000 students (§16) |

**Medium impact**

| Gap | Why it matters |
|---|---|
| Universal activity timeline (W3) | Support/dispute resolution, audit trail, onboarding new staff faster |
| Styled, tiered confirmation dialogs | Native `confirm()` gives "delete a vacation entry" and "permanently delete a staff account" identical ceremony |
| Shared charting/reporting primitive | Currently 3 independently hand-rolled bar charts, no library — blocks §12 |
| Role-scoped landing dashboards for all roles, not just Admin/Teacher | 7 roles land on 5 different pages today with no deliberate per-role "what matters first" design |
| Bulk actions beyond attendance's "mark all" | Every other list (payments, students, leads) is one-row-at-a-time |
| A real Parent/Student self-service surface | Parents exist only as mobile-app accounts administered here; no student-facing surface exists at all (§6, §17 Phase 5) |

**Low impact (real, but sequence last)**

- In-app help/onboarding (currently zero — acceptable short-term given a small, trained staff)
- Integrations beyond the existing Facebook Lead Ads webhook + Telegram bot
- Mobile-*native* workflows beyond a solid responsive web layer (§15)

---

## 4. New Sitemap

The current sitemap groups pages by **department metaphor** (Metodika / CRM / Akademik / Moliya
/ Boshqaruv). The redesign groups by **business object and task frequency** instead — this is
the single change that most directly fixes the navigation problems in §3.1, because it caps
growth: a new *report* doesn't need a new top-level section, it's a new row inside Reports.

### 4.1 Three-level hierarchy

**Level 1** = 7 fixed top-level domains (down from today's ~11 sidebar sections, several of
which duplicate the same 2 pages). **Level 2** = objects/pages within a domain. **Level 3** =
tabs within a page (a pattern the app already uses well in places — Student Detail's 4 tabs,
Academic's 5 tabs — and should use *everywhere*, per the Unified Entity Standard in §6.8).

```
L1: Home                                    (role-aware landing — see §11)

L1: CRM
 L2: Pipeline            L3: Board · List · Analytics
 L2: Intake Forms        (admin: public lead-capture form management)

L1: Education
 L2: Students            L3: Active · Demo · Archived · Alumni (new, §3.2 W6)
 L2: Student Profile     L3: Overview · Academic · Payments · Attendance · Files · Timeline
 L2: Groups              L3: list (cards or table, user-selectable — see §14 Attio parallel)
 L2: Group Detail        L3: Roster · Attendance · Curriculum · Certificates · Timeline
 L2: Attendance          L3: Today · Monthly Grid (per group) · Camera Log
 L2: Curriculum          (Lessons library — Foundation/Frontend/Backend)
 L2: Academic            L3: Grades · Coins · Feedback · Certificates · Events

L1: Finance
 L2: Payments            L3: Ledger · Debtors
 L2: Expenses
 L2: Pricing             L3: Tariffs · Courses · Special Discounts
 L2: Payroll             L3: Salary (all staff) · Teacher Salaries (drill-down)

L1: Reports                                  (new consolidated home — see §12)
 L2: Executive Overview
 L2: Sales & Pipeline Reports
 L2: Student & Academic Reports
 L2: Attendance Reports
 L2: Finance Reports
 L2: Teacher Performance                     (new — see §9)

L1: People
 L2: Staff Directory      (Users — internal accounts)
 L2: Roles & Permissions  (new in-product surface — see §14)
 L2: Audit & Warnings     L3: Warnings Log · My Warnings · Discipline Codes
 L2: Parents              (external parent-app accounts)

L1: Automation & Settings
 L2: Bot Admin            L3: Employees · Roles · Settings · Admin/CEO · Investors
 L2: Notification Center  (unifies the two "Notifications" — see N5)
 L2: Integrations         (Facebook Lead Ads status, future webhooks)
 L2: System Settings
```

### 4.2 What moved and why

- **Attendance becomes its own L2 under Education**, not buried as a Group Detail tab plus a
  separate "Today's Attendance" page with no shared entry point — both surfaces stay (they solve
  genuinely different use cases per the source report), but they're now siblings under one
  visible heading instead of two unrelated sidebar destinations.
- **Payroll nests under Finance** (not a standalone top-level section) — it's a finance concern
  by nature and audience (Admin only); nesting it caps L1 growth without hiding it (it's an L2,
  one click away).
- **Reports becomes its own top-level domain**, separated from the transactional Finance/
  Education/CRM screens. Today's "Dashboard" (P&L + KPIs), Finance's per-group report, and
  Leads' Analytics tab all currently live inside their transactional module. Splitting reporting
  out gives it room to grow (§12) without further bloating CRM/Education/Finance, and matches
  how Stripe Dashboard and HubSpot both separate "do the work" screens from "review the work"
  screens.
- **People consolidates Users + Employees + Audit + Parents**, which today are scattered across
  "Boshqaruv" (Admin-only) and a standalone "Audit" section — same underlying concept (a person
  the school has a relationship with, staff or external), same L1 home.
- **Automation & Settings is new** as a named concept — Bot Admin already exists but has no
  peer; a Notification Center and an Integrations page don't exist today and are the natural
  home for the automation work in §13.

---

## 5. New Navigation

### 5.1 Sidebar (Level 1 + role visibility)

The sidebar renders **only the L1 domains a role has any access into** — no domain appears as an
empty shell. Each domain expands to its L2 items; only one domain is expanded at a time by
default (an accordion, not the current "everything permanently open" flat list) to keep the
visible surface short regardless of how many L2 items a domain accumulates over time.

| L1 Domain | admin | support_teacher | teacher | hunter | sales | call_center | audit |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Home | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CRM | ✅ | ⬛ | ⬛ | ✅ | ✅ | ✅ | ⬛ |
| Education | ✅ | ✅ | 🟡 own groups | ✅ | ✅ | ✅ | ⬛ |
| Finance | ✅ | ⬛ | 🟡 own salary only | 🟡 payments/expenses only | ⬛ | ⬛ | ⬛ |
| Reports | ✅ | 🟡 academic only | 🟡 own performance only | 🟡 sales/collections only | 🟡 sales only | 🟡 sales only | ⬛ |
| People | ✅ | ⬛ | ⬛ | 🟡 Parents only | ⬛ | ⬛ | 🟡 Audit & Warnings only |
| Automation & Settings | ✅ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ | ⬛ |

This is the same access matrix the app already enforces today (§2.2) — nothing about *who can
see what* changes, only *how it's grouped and how many top-level items exist*. For the busiest
role (Admin), this collapses ~19 always-visible buttons down to 7 always-visible domains.

### 5.2 Command palette (new)

The single highest-leverage navigation addition. `Cmd/Ctrl+K` (and the existing `/`-to-search
affordance from Leads, generalized) opens a palette that:
- Jumps to any L1/L2/L3 destination by typing its name (fixes N1/N3 more durably than any sidebar
  reorganization — it scales with feature count instead of degrading as it grows)
- Jumps directly to any Student/Lead/Group/Payment by name/phone (a real cross-entity search that
  doesn't exist today at all)
- Executes common actions without navigation ("Add Lead," "Record Payment," "Mark attendance for
  [group]") — the Linear pattern

### 5.3 Supporting navigation elements

- **Breadcrumbs** at L2/L3 depth (Education › Student Profile › Ismoilov Ali › Attendance),
  replacing the current back-button-via-`sessionStorage-origin` pattern with something legible
  and shareable once real routing exists.
- **Favorites/pins** (Attio-style) — let a user pin 2–4 destinations they live in daily (a
  Hunter pinning Pipeline + Payments; a Teacher pinning their own Group Detail) to the top of the
  sidebar, independent of the L1/L2 structure.
- **Saved views per table**, addressed fully in §12/§16 — surfaces as a dropdown at the top of
  any List/table page ("My view," "Debtors only," "This month's new leads").

---

## 6. User Journeys

The brief asks for Admin, Manager, Teacher, Operator, Finance, Student, and Parent journeys.
This CRM's actual role system (§2.2) doesn't have "Manager," "Operator," or "Finance" as literal
roles, and **Student/Parent are not users of this web application today** (parents get a
separate mobile app; students get nothing). Rather than force a mismatch, each requested journey
below is mapped to its closest real role, with gaps called out explicitly where none exists.

| Brief's requested role | Maps to (today) | Note |
|---|---|---|
| Admin | `admin` | Direct match |
| Manager | closest is `support_teacher` (Metodist) for academic ops, or `admin` wearing an ops hat — **no dedicated ops-manager role exists** | Flagged as a role-architecture gap in §14 |
| Teacher | `teacher` | Direct match |
| Operator | `hunter` / `sales` / `call_center` (three distinct operator-type roles) | Treated as three sub-journeys, since they're meaningfully different in practice |
| Finance | `admin`'s finance capability + `hunter`'s partial finance visibility | **No dedicated Finance role exists** — flagged in §14 as a recommended new capability grant, not necessarily a new role |
| Student | *not a user of this system* | Forward-looking journey only — see §6.7 |
| Parent | *mobile app only, no web presence* | Forward-looking web-companion journey — see §6.8 |

### 6.1 Admin

- **Goals:** company-wide oversight, exception handling, the only role that touches money at the
  company level and manages the system itself.
- **Daily tasks:** review Dashboard/Reports, approve/adjust payroll, resolve escalations
  (debtors, blocked accounts, staff warnings), manage users/roles.
- **Pain points today:** the ~19-button sidebar scroll (§3.1 N1); no single "what needs my
  attention today" view — Admin must proactively check 5+ separate pages to find work.
- **Required screens:** Home (role dashboard), Reports (all), Finance (all), People (all),
  Automation & Settings.
- **Required actions:** approve/override payroll, manage roles (currently code-only, §14),
  resolve escalated debtors/leads.
- **Required shortcuts:** command palette (§5.2), an "attention needed" widget on Home
  surfacing overdue debts, stalled leads, and unresolved staff warnings in one place (new — no
  equivalent exists today).

### 6.2 Manager (mapped to Metodist / an Admin ops-lens — see gap note above)

- **Goals:** keep curriculum current, keep the student/group operational layer running smoothly.
- **Daily tasks:** maintain lesson plans, manage student/group admin, review academic data
  (grades/coins/feedback/certificates).
- **Pain points today:** Academic's 5 tabs have no per-student rollup — a Metodist reviewing one
  student's trajectory must manually cross-reference 5 separately filtered tabs (§3.2, adjacent
  to W3).
- **Required screens:** Education (all), Reports › Student & Academic Reports.
- **Required actions:** curriculum CRUD, academic-record CRUD, group/student admin.
- **Required shortcuts:** a per-student "academic rollup" view (new, addressed in §6.8's Unified
  Entity Standard — Student Profile's Academic tab should aggregate grades+coins+feedback+certs
  in one place instead of requiring 5 separate tab visits).

### 6.3 Teacher

- **Goals:** run class, get paid correctly, minimal admin overhead.
- **Daily tasks:** land on Teacher Dashboard → pick today's group → mark attendance → send
  homework → occasionally check own salary calculation.
- **Pain points today:** own salary formula is causally driven by attendance-marking with **zero
  visible connection between the two actions** (§2.4, §3.2 W4) — a teacher has to trust the
  number, not see why it changed.
- **Required screens:** Home = Teacher Dashboard, Education › Group Detail (own groups), a real
  Schedule view (doesn't exist today — a teacher's schedule is only implicit in group cards).
- **Required actions:** mark attendance, send homework, grade, view own certificates queue.
- **Required shortcuts:** an in-context "this month's pay so far, updated live as you mark
  attendance" indicator directly inside the attendance-marking flow — turns W4 from a
  documentation problem into a product feature.

### 6.4 Operator — three sub-journeys (Hunter / Sales / Call Center)

| | Sales | Call Center | Hunter |
|---|---|---|---|
| **Goal** | Generate/manage referral-source leads | Qualify inbound leads by phone | Close everything — leads through cash collected |
| **Daily tasks** | Work referral pipeline, track source performance | Call new leads, triage parent-feedback follow-ups | All of the above **plus** record payments, manage expenses/parents |
| **Pain point today** | No dedicated "referral performance" home — buried in Leads Analytics | No "call mode" — calling is one stage-transition among several, no focused dial queue (§3.5 medium-impact gap, referencing Close CRM) | Busiest single role in the app with no role-specific dashboard distinguishing their finance-adjacent work from a pure Sales/Call-Center view |
| **Required screens** | CRM › Pipeline (Analytics tab), Reports › Sales & Pipeline | CRM › Pipeline (Board), People › Parents (feedback triage) | CRM (all), Education (all), Finance › Payments/Expenses |
| **Required shortcut** | Referral funnel as a first-class widget on Home, not a drill-down | **Power-dial mode:** a focused, keyboard-driven "call the next lead in my queue" flow (new — direct Close CRM parallel, high leverage for exactly one role's entire job) | A combined Home dashboard blending pipeline + collections KPIs (§11) |

### 6.5 Finance (no dedicated role exists — capability, not a persona, today)

- **Goals:** accurate books, healthy collection rate, payroll correctness.
- **Daily tasks (currently split between Admin and Hunter):** record/verify payments, chase
  debtors, reconcile expenses, review/approve payroll.
- **Pain point today:** finance work is split across a role that also does everything else
  (Hunter) and a role that also does everything else at the company level (Admin) — there is no
  persona whose *only* job is finance, so no dashboard is built for that lens either.
- **Recommendation:** don't necessarily add an 8th role — grant a **finance capability** (§14)
  that could be assigned narrowly (e.g., a future bookkeeper account) without inheriting all of
  Hunter's or Admin's other permissions.

### 6.6 Student *(forward-looking — no web presence exists today)*

- **Goals (inferred):** know what's owed and when, see attendance/grade history, get homework
  and certificates.
- **Ideal journey:** a lightweight, mobile-first student portal (or an extension of the existing
  parent mobile app to also support direct student login) surfacing: this month's payment
  status, attendance history, grades/coins/feedback, upcoming homework, and downloadable
  certificates — all data that **already exists** server-side (Payments, Attendance, Academic)
  but has zero self-service surface today. This is a Phase 5 (§17) opportunity, not a near-term
  gap, but worth designing the data model to support now rather than retrofitting later.

### 6.7 Parent *(mobile app only today — no web companion)*

- **Goals:** know their child is safe/attending, know what's owed, get feedback from teachers.
- **What already works:** the Parent account system exists server-side (separate `Parent` table,
  own auth), receives Telegram-delivered attendance/feedback notifications, and the mobile app
  is the primary surface — this is correctly out of scope for this web-app architecture review.
- **Gap worth flagging:** Parent account *administration* (creating accounts, linking children,
  broadcasting messages) is admin/hunter-only inside this CRM — there is no self-service
  password reset or account-recovery flow for a parent who loses mobile-app access, meaning every
  parent support issue currently becomes a staff ticket. Worth a lightweight web fallback
  (magic-link login) in a later phase.

### 6.8 Cross-cutting product systems

These three systems don't belong to any single role — they're infrastructure every journey above
depends on, and none of them exist today outside the Leads module.

**Task & follow-up system.** Today: reminders exist only inside the Lead drawer (due datetime,
body, kind, always self-assigned). Recommendation: promote this into a system-wide primitive —
any entity (Lead, Student, Group, Payment, Teacher) can have tasks attached, tasks can be
assigned to someone other than the creator, tasks surface in a personal "My Tasks" queue on
Home, and overdue tasks generate notifications. This is the landing zone for most of §13's
automation output (an auto-generated "payment overdue, follow up" task is more useful than a
Telegram ping alone, because it's trackable to completion).

**Activity timeline architecture.** Today: only Leads auto-generates a timeline (server-side, on
every stage change). Recommendation: generalize the same mechanism to Students (enrollment,
group changes, payment events, vacation periods), Groups (roster changes, teacher reassignment),
Payments (creation, edits, voids), and Teachers (salary overrides, warnings). One shared
`ActivityEvent` shape (actor, action, entity, timestamp, description) powering every entity's
Timeline tab — a single backend concept, not five bespoke ones.

**Unified entity detail-page standard.** Today, detail pages are built ad hoc per entity (Student
Detail has 4 tabs; Group Detail has a different tab set; Payments has no detail page at all,
just a list row). Recommendation: standardize on one anatomy for every core entity (Lead,
Student, Group, Teacher, Payment where applicable):

| Tab | Contents |
|---|---|
| **Overview** | Key fields, status, quick actions — today's "info form," made read-first with an edit affordance rather than always-editable |
| **Activity** | The unified timeline (above) |
| **Notes** | Freeform notes — exists ad hoc today (Lead notes, Student notes); formalize as a standard tab |
| **Files** | Photos, certificates, uploaded documents — currently scattered (student photo is a sidebar element, certificates live in a completely separate designer) |
| **History** | Structural history distinct from Activity — e.g. a Student's group-membership history, a Payment's edit/void audit trail |
| **Actions** | Entity-specific actions (archive, convert, claim, generate certificate) — currently scattered as page-level buttons with no consistent location |
| **Relationships** | Linked entities — a Student's Lead origin, Groups, Payments, Parent account; a Group's Teacher, Students, Tariff — today these links exist in the data model but are inconsistently surfaced (e.g. a Payment doesn't visibly link back to the Lead that originated the student) |

Not every tab applies to every entity (a Payment doesn't need a Files tab) — the standard is a
menu to select from, not a mandate that all seven appear everywhere.

---

## 7. Lead Lifecycle

### 7.1 Current state (as built)

```
New → Called → Callback/Will-come → Demo → Paid/Enrolled (cosmetic) ⇥ [gap] ⇥ Student (manual, disconnected)
                                          ↘ Rejected
```

Stages are admin-configurable (name/color/icon/order/kind), not a fixed enum — a genuine
strength. The shared-pool/claim mechanic and the activity timeline (auto-generated on every
stage move) are both already well-executed. The gap is entirely at the handoff: reaching the
"won" stage recolors a kanban card and nothing else — the Student record is a fully separate,
manually re-typed action on a different page.

### 7.2 Redesigned lifecycle

```
Lead Created (manual / public intake / Facebook webhook)
   → Contacted (first call logged — today implicit in a stage move, should be an explicit
     activity-timeline event independent of stage, so "contacted but still undecided" is
     representable)
   → Qualified (meets basic criteria — budget/interest/age fit)
   → Demo Scheduled (callback datetime set — exists today)
   → Demo Attended (exists today as the "Demo" stage)
   → WON: real "Convert to Student" action fires here (new — see 7.3)
        → Student record created, pre-filled from Lead fields (name, phone, parent info,
          course interest, source — full carry-over, zero re-typing)
        → Lead marked converted, linked bidirectionally (Student.origin_lead_id — new field)
        → Placement flow begins (§8.2)
   → LOST: Rejected, with a required reason taxonomy (today: freeform notes only) feeding a
     nurture/re-engagement queue (new — see §13) instead of just disappearing from active counts
```

### 7.3 The "Convert to Student" action (highest-leverage single fix in this document)

A button on a "won"-kind stage, replacing the current silent cosmetic move:
1. Opens a pre-filled Add-Student form (name, phone, parent info, notes carried directly from
   the Lead — zero re-entry).
2. On save: creates the Student, sets `Student.origin_lead_id`, marks the Lead as converted
   (visually distinct from simply "won," so reporting can tell "won but not yet enrolled" apart
   from "fully converted").
3. Feeds directly into Placement (§8.2) — the rep doesn't leave the flow to separately find the
   Groups page.

This single change closes §3.2's W1 and directly answers the source report's explicit
recommendation (discovery report §17 finding #8, §19's Pipedrive/HubSpot comparison).

---

## 8. Student Lifecycle

### 8.1 Current state

```
Student created (standalone, optionally flagged Demo)
   → [optional] attached to a Group (promotes out of Demo)
   → Active (Attendance + Payment tracked monthly)
   → [optional] Vacation periods, Special discounts applied along the way
   → Archived (terminal state — indistinguishable whether graduated or dropped out, §3.2 W6)
```

### 8.2 Redesigned lifecycle

```
Enrollment (from Lead conversion, §7.3, or direct entry)
   → Placement: a real recommendation step — match course interest + existing groups' schedule/
     capacity/level, rather than today's raw "pick any group from a dropdown" (new — today's
     Group-assignment UI has no capacity awareness or fit-scoring at all)
   → Onboarding checklist (new — today these signals exist but aren't tracked as a state):
        ☐ Group assigned  ☐ Tariff confirmed  ☐ Telegram linked (parent notification channel)
        ☐ Parent account linked  ☐ Photo uploaded
     A student isn't "fully onboarded" until this checklist clears — gives Hunter/Metodist a
     concrete, trackable definition of done instead of tribal knowledge.
   → Active:
        - Attendance tracked (existing 3-surface system, kept as-is — it correctly solves 3
          different real use cases per the source report)
        - Payment tracked monthly (existing computed expected/paid/debt model, kept as-is)
        - Progress tracked: a genuine rollup (grades + coins + feedback + certificates in one
          Student Profile tab, replacing today's 5-separate-Academic-tabs-filtered-by-dropdown
          pattern — see §6.8's Unified Entity Standard and §6.2's Manager journey)
   → Graduation: certificate issued (exists) — but now transitions to...
   → Alumni (new terminal state, replacing "just archived"): distinct from a dropped-out
     student. Enables future referral/marketing reuse (a graduate is a warm lead source for
     siblings/friends) and gives Reports (§12) a real "completion rate" metric distinct from
     "attrition rate" — today both collapse into the same `is_archived` flag and can't be told
     apart in reporting.
```

### 8.3 Why Placement matters at scale

Today's raw group-picker dropdown is workable at ~500 students across a handful of groups. At
5,000+ students across dozens of concurrent groups, capacity-blind placement becomes a real
operational risk (over-enrolling a group past its effective teaching capacity, or a schedule
conflict that isn't caught until attendance-marking reveals it). This is flagged again in §16.

---

## 9. Teacher Lifecycle

### 9.1 Current state

```
Hired → User account created (role=teacher) → assigned to Group(s) via a single dropdown on
the Group edit form (no conflict detection) → runs class via Group Detail (attendance, homework,
grading — all solid, existing functionality) → pay auto-computed monthly from a fixed formula,
visible read-only via Teacher Dashboard's "Maosh hisobi" tab
```

### 9.2 Redesigned lifecycle

```
Onboarding (new — today: none exists beyond account creation):
   ☐ Curriculum access confirmed  ☐ Groups assigned  ☐ Telegram bot linked
   Same checklist pattern as Student Onboarding (§8.2) — consistent product language for
   "is this person/record ready to be active."

Assignment (formalized — today: a bare dropdown with zero validation):
   A real "Assign Teacher to Group" flow with schedule-conflict checking (can this teacher
   actually be in two places at once given the school's even/odd-day scheduling convention?)
   and a visible capacity/load view (how many groups/students is this teacher already carrying?).

Schedule (new — no dedicated view exists today):
   A teacher's schedule is currently only *implicit* in which groups they're assigned to plus
   each group's day/time fields. A real Schedule view (calendar or weekly-grid) assembled from
   that same data, both for the teacher themselves and for whoever is doing Assignment above.

Delivery (existing, solid): attendance, homework, grading via Group Detail.

Performance (new — no metric beyond raw attendance-marking exists today):
   A real Teacher Performance report (§12): on-time attendance-marking rate, homework-send
   consistency, certificate-generation turnaround, feedback volume. This is the direct product
   answer to the source report's observation that attendance-marking and payroll are causally
   linked but navigationally and *measurement-wise* invisible to everyone but the teacher
   themselves (§3.2 W4) — Performance reporting makes that link visible to Admin/Manager too.

Payroll (existing, solid — formula-driven, tied to attendance): kept as-is functionally, but
   made visible in-context per §6.3's recommendation (a live salary-impact indicator inside the
   attendance-marking flow itself, not just a separate read-only tab).
```

---

## 10. Finance Lifecycle

### 10.1 Current state

Six overlapping sub-screens (Payments, derived Debt, Finance per-group report, Special
Discounts, Salary, Teacher Salaries) sharing one server-computed data model, with no single
"Finance home" tying them together, and zero automation on the collections side (a debtor stays
a debtor until a staff member manually notices and calls).

### 10.2 Redesigned lifecycle

```
Revenue Recognition:
   Tariff assigned at enrollment → monthly Expected amount computed (tariff price, adjusted
   for vacation days and special discounts) — existing, correct architecture, kept as-is.

Collection:
   Payment recorded → Debt re-derived automatically — existing, kept as-is.

Collections Management (new — today: fully manual):
   Automated reminder cadence (§13): a Telegram nudge to the parent at day 3/7/14 overdue,
   escalating to an in-product Task (§6.8) assigned to Hunter/Admin at day 21. Turns the
   Debtors list from a static report staff must remember to check into a queue that pushes
   work to the right person automatically.

Expense Tracking:
   External + payroll-labeled expenses — existing, kept as-is (recommend consolidating the two
   independent Add/Edit Expense implementations into one, per §3's problem list).

Payroll Generation:
   Existing formula auto-calc + manual override, kept as-is functionally. Recommend a "Generate
   & Lock" ritual (new): once Admin reviews and locks a month's payroll, teachers are
   auto-notified their pay is finalized (extends the existing Telegram-notification
   infrastructure, doesn't require new channels).

Financial Reporting:
   Consolidated into one Finance Reports hub (§12) instead of scattered across Dashboard,
   Finance, and ad hoc Excel exports from three different pages.

Month-End Close (new — currently a fully tribal-knowledge ritual):
   A guided checklist state for the month: all payments recorded, all attendance marked
   (payroll depends on it), expenses logged, payroll generated & locked, report exported/
   archived. Doesn't add new data — it makes an already-happening process visible, trackable,
   and impossible to accidentally skip a step of, which matters increasingly as more staff
   touch finance workflows at scale (§16).
```

---

## 11. Dashboard Architecture

The current app has exactly two dashboards (Admin's company P&L view, Teacher's personal
cockpit) with zero role-conditional logic inside either — every other role gets no dashboard at
all, just a default landing page. This section designs a role-aware **Home** for every role,
replacing "default landing page" with "purpose-built first screen."

| Role | KPIs | Widgets | Reports (drill-in) | Actions | Alerts | Shortcuts |
|---|---|---|---|---|---|---|
| **Admin** | Total students (active/demo/archived split), MRR-equivalent (this month income), net profit, collection rate | P&L summary card, annual revenue chart, "attention needed" queue (overdue debtors, stalled leads, unresolved warnings — new, §6.1) | Executive Overview (§12) | Approve payroll, resolve escalations | Debt threshold breaches, staff-warning backlog | Command palette, pinned favorites |
| **Manager (Metodist)** | Active groups, curriculum completeness %, students needing academic follow-up | Curriculum health, per-group academic-rollup snapshot | Student & Academic Reports | Add lesson, review flagged feedback | Groups nearing lesson-count completion (certificate due soon) | Jump to any group's curriculum |
| **Teacher** | Today's groups, this-month pay (live-updating, §6.3), pending homework | Today's schedule, salary-impact-of-attendance indicator, certificate queue | Own Performance (§9.2, new) | Mark attendance, send homework | Group nearing completion (cert due) | Group search-jump (existing pattern, keep) |
| **Operator — Sales** | New leads (period), source performance, referral conversion % | Referral funnel (existing, elevate from drill-down to Home widget) | Sales & Pipeline Reports | Add lead | Stalled leads (no contact in X days) | Power-dial mode (§6.4) |
| **Operator — Call Center** | Leads to call today, feedback-triage queue depth | Today's-callback queue, "today" filter (existing, elevate to Home) | Sales & Pipeline Reports (call-outcome view) | Claim lead, log call | New feedback needing triage | Power-dial mode (§6.4) |
| **Operator — Hunter** | Pipeline + collections blended: leads to work, debt total, this-month collected | Combined pipeline snapshot + Debtors summary | Sales & Pipeline + Finance Reports | Add lead, record payment, add expense | Overdue debtors, stalled leads | Command palette |
| **Finance (capability, §6.5)** | Collection rate, MRR, payroll cost, net profit | P&L summary, debtor aging | Finance Reports | Record/void payment, generate payroll | Debt threshold breaches | — |
| **Audit** | Open warnings, staff needing follow-up | Recent warnings list | — (Audit is intentionally narrow — no broader reporting need) | Issue warning | Unresolved warning past SLA | — |

Design principle carried through every row: **the dashboard surfaces work, not just numbers** —
every KPI has an adjacent "here's what to do about it" widget or action, addressing the brief's
explicit "the dashboard should not be random metrics" instruction.

---

## 12. Reporting Architecture

Today's reporting is, in the source reports' own words, "close to a greenfield opportunity" —
there is no charting library, three independently hand-rolled bar charts, and "Analytics" exists
formally only inside the Leads module. This section defines the target reporting layer.

| Report | Metrics | Filters | Exports |
|---|---|---|---|
| **Student Reports** | Enrollment trend, active/demo/archived/alumni split, retention rate, avg. tenure, attrition reasons (new field, feeds off §7's lost-reason taxonomy) | Date range, group, course track, tariff | Excel (existing pattern), CSV |
| **Lead / Sales Reports** | Volume by source, stage-conversion funnel, avg. time-to-convert, referral performance, lost-reason breakdown | Date range, source, rep, stage | Excel, CSV |
| **Attendance Reports** | Attendance rate by group/student/teacher, chronic-absence flags (new — pattern-based, not just per-event), holiday-adjusted completion % | Date range, group, teacher | Excel, CSV |
| **Teacher Reports** | Performance metrics (§9.2), salary breakdown history, attendance-marking timeliness | Date range, teacher | Excel |
| **Finance Reports** | P&L (existing, consolidated from Dashboard), collection rate, debtor aging buckets (new — 0-7/8-14/15-30/30+ days overdue, feeding the reminder cadence in §10.2), per-group/per-course margin | Date range, group, course | Excel, CSV, scheduled auto-export (new, §13) |
| **Management / Executive Reports** | Cross-module rollup: revenue + enrollment + attendance + payroll cost in one view, month-over-month and year-over-year trend | Date range, comparison period | Excel, scheduled auto-send (extends the existing investor-Telegram-broadcast infrastructure already built into Bot Admin) |

**Foundational recommendation:** build one shared charting primitive (bar/line minimum) before
building any of the above — every report in this table needs at least a trend chart, and solving
it once instead of the current "three independent implementations" pattern is a direct
prerequisite, not optional polish (this is a build-order dependency captured in §17 Phase 3).

---

## 13. Automation Architecture

The app has real automation today (formula-driven payroll, Telegram-delivered attendance/
feedback/warning notifications, an investor daily-stats broadcast recently added to Bot Admin) —
but all of it is *reactive to a staff click*, not *proactive on a schedule or condition*. This
section closes that gap.

| Automation | Trigger | Action | Lands in (per §6.8) |
|---|---|---|---|
| **Lead auto-assignment** | New lead enters the shared pool | Round-robin or source-based auto-claim among eligible reps (today: 100% manual claim) | Task assigned to rep |
| **Lead SLA / escalation** | Lead uncontacted past N hours | Escalate visibility (surfaced in Admin's "attention needed" widget, §11) | Home alert |
| **Payment reminders (dunning)** | Payment overdue by day 3/7/14 | Telegram nudge to parent (day 3/7), escalating Task to staff (day 14/21) | Task + existing Telegram channel |
| **Attendance-pattern alerts** | Student absent N times in a rolling window | Alert to Metodist/Admin (today: only per-event notification exists, no pattern detection) | Task + Home alert |
| **Parent notifications** | Attendance event, feedback posted, payment received | Telegram message (existing — expand trigger set, don't rebuild the channel) | — |
| **Teacher notifications** | Warning issued (existing), schedule change, homework-due reminder (new) | Telegram message | — |
| **Payroll generation** | Month-end | Auto-calculate (existing) + new "Generate & Lock" ritual (§10.2) with auto-notify | Task (Admin review) |
| **Report generation** | Scheduled (monthly) | Auto-export + auto-send via the existing investor-broadcast Telegram infrastructure, extended to internal Management Reports (§12) | — |
| **Lost-lead re-engagement** | Lead marked lost with a reason | Enter a nurture queue (new — today lost leads just stop appearing in active counts) | Task, scheduled follow-up |

**Build-order note:** every row above needs *somewhere to land* — that's why the Task system
(§6.8) is sequenced before automation in the roadmap (§17). Automation without a task/
notification substrate to deliver into is just more Telegram noise, not a product capability.

---

## 14. Permission Architecture

### 14.1 Current state — problems

- **Three independent enforcement points** with no shared source: `Sidebar.jsx` boolean flags,
  `App.jsx`'s `PAGE_ACCESS` map, and backend `require_*` guards. A role or page added to only
  one silently breaks navigation or security.
- **No granular capability model** — access is 100% role-*name* string matching (`if role ==
  'admin'`), not role-*capability* matching (`if has_permission('finance:write')`). There is no
  way to grant one narrow capability without granting an entire role's full footprint.
- **No in-product role management** — every permission change today requires an engineer to
  edit code and redeploy. There is no Roles & Permissions screen despite Admin having access to
  nearly everything else administrative.
- **Redundant/overlapping roles:** `hunter` is a superset of `sales` + `call_center` + a slice of
  `admin`'s finance access — functionally a "Sales Manager" tier in disguise, not cleanly
  distinct from the roles it overlaps.
- **Confusing permission granularity:** several "permissions" are really just role checks with no
  read/write distinction (e.g., Hunter "can see Expenses" is view-only, encoded as a role
  check, not an actual view-vs-edit flag).
- **Audit role is correctly isolated** — the one part of the current architecture that needs no
  change, only preservation.

### 14.2 Recommended architecture

1. **One source of truth.** Backend serves a `/auth/permissions` payload (or equivalent) on
   login describing exactly what the current user can see/do; both the sidebar and the
   page-access guard consume *that*, not independently hardcoded logic. The backend endpoint
   guards remain the real security boundary (correct, keep as-is) — the fix is that frontend
   logic stops re-deriving what they already enforce.
2. **Capability-based, not role-name-based.** Model permissions as `module:action` pairs
   (`finance:view`, `finance:edit`, `students:write`, `payroll:approve`) grouped into named
   roles as *bundles* of capabilities, not hardcoded string checks. This is what makes adding an
   8th role (or narrowing Hunter's footprint) a data change instead of a code change.
3. **Formalize Hunter as what it already is.** Either rename/reposition it as a "Sales Manager"
   tier with an explicit, documented superset relationship to Sales+Call Center, or split its
   finance capability into a separately grantable permission — so a future narrower role (e.g.,
   a pure collections/bookkeeping account, per §6.5's Finance capability) doesn't have to inherit
   Hunter's full CRM footprint just to get finance access.
4. **Ship a Roles & Permissions admin screen** (new — People › Roles & Permissions in §4's
   sitemap) so role/capability changes become an in-product Admin action, not an engineering
   ticket. This is the single change that most future-proofs everything else in this document —
   every subsequent phase in §17 that touches access control gets cheaper once this exists.
5. **Keep Audit's isolation exactly as-is** — it's correctly modeled as a fully separate
   capability bundle with zero overlap into the operational app, and should stay that way as the
   capability model is formalized.

---

## 15. Mobile Strategy

| Belongs on mobile (mobile-first or mobile-native) | Belongs desktop-only | Needs a dedicated mobile-native flow (not just responsive web) |
|---|---|---|
| Attendance marking (Teacher — already a tap-list pattern, high-frequency, physically happens in a classroom) | Payroll/Salary editing (dense tables, irreversible money actions — benefits from deliberate friction and a large screen) | **Attendance** — the teacher is physically walking a room; a true mobile-native tap experience (not just a shrunk desktop grid) is worth the investment |
| Lead follow-up / calls (Operator roles — on-the-go by nature of the job) | Reporting/Analytics deep-dives (§12 — wide tables, charts, exports) | **Power-dial mode** (§6.4/§11 Call Center) — a phone-native tap-to-call queue is meaningfully better than a responsive web page for this specific job-to-be-done |
| Notifications / approvals (all roles) | Admin configuration (Roles & Permissions, pipeline Stage Manager, Bot Admin) | **Push notifications generally** — today's Telegram-bot-as-notification-channel is a clever, working substitute, but a real mobile app would eventually want native push; flag as a future architectural question once §17 Phase 5's student/parent portal work begins |
| Teacher's day-of actions (today's schedule, mark attendance, send homework) | Bulk data operations (relevant at the 20k+ scale in §16) | — |

**Strategic call:** invest in **responsive web first** for every role except Teacher and the
Call-Center power-dial use case — those two are the only journeys in this system where the job
itself is physically/attentionally mobile-native (walking a classroom; working a phone queue),
not just "someone might check this on their phone sometimes." Everything else (Admin, Manager,
Finance, most of Hunter/Sales) is desk-based work that a well-built responsive layout serves
correctly without the cost of native app development.

---

## 16. Scalability Strategy

| Dimension | Today (~500 students) | 5,000 students | 20,000 students | 50,000 students |
|---|---|---|---|---|
| **Navigation** | Flat sidebar tolerable | Command palette (§5.2) becomes necessary, not optional — flat browsing no longer scales | Saved views (§5.3) become necessary for every role to have a usable default | Favorites/pins become the primary navigation mode for power users; full sidebar browsing becomes a fallback, not the default path |
| **Data structure** | SQLite fine | SQLite nearing its practical ceiling for concurrent write load (payments, attendance, leads all writing constantly) | **Postgres migration should already be complete** — SQLAlchemy already abstracts the DB layer (the app's own `DATABASE_URL` pattern already supports swapping engines), so this is a lower-risk migration *if done proactively* rather than reactively under load | Postgres with read replicas for reporting queries, separated from the transactional write path |
| **Search** | Per-page text filters adequate | Global search (§5.2) becomes necessary — per-page filters can't answer "find this person across the whole system" | Dedicated search infrastructure (Postgres full-text search minimum; a dedicated search service if query patterns demand it) | Same, with index-freshness/latency now a real design constraint |
| **Tables** | Unpaginated tables barely tolerable today already (§2.7) | **Pagination + sorting must be the default everywhere, not opt-in** — this should happen well before 5,000, not at it | Virtualization needed for the largest grids specifically (the Group attendance calendar-column grid, the Leads kanban) | Same, plus server-side aggregation for any table that currently computes summary rows client-side |
| **Reporting** | Live queries over raw tables (`stats_overview` etc.) fine | Live aggregation queries start to show latency | **Pre-aggregated rollup tables / materialized views required** — computing P&L live over every Payment row stops being viable | Scheduled aggregation jobs feeding a dedicated reporting store, decoupled from the transactional database entirely |
| **Workflows** | Manual lead-claim, manual debt-chasing tolerable with a small team | Auto-assignment and SLA automation (§13) become **necessary, not nice-to-have** — no single Hunter can eyeball a shared pool at this volume | Same automation, now load-bearing for the business (a missed SLA at this scale is real lost revenue, not an edge case) | Automation coverage becomes a core product requirement, not an enhancement — the business literally cannot run without it at this headcount-to-student ratio |
| **Org structure** | Single-campus assumption baked into the data model (no "branch/location" concept anywhere) | Still fine for one campus | **A second campus is plausible at this scale** — worth designing a `branch_id`/location concept into the data model *before* it's forced, since retrofitting multi-tenancy-adjacent structure into a live system is far more expensive than building it in from the start | Multi-branch is likely a hard requirement — flag this explicitly as a data-model decision to make in Phase 4 (§17), not Phase 5, since it touches nearly every table (Students, Groups, Leads, Payments all need a location dimension) |

**The single most important scalability recommendation:** everything in the "5,000 students"
column should be treated as **Phase 1-2 work (§17), not deferred until the school actually hits
5,000** — pagination/sorting defaults, the command palette, and auto-assignment automation are
all cheaper to build now, into a system with 500 students' worth of test data, than to retrofit
under live load later.

---

## 17. Product Roadmap

### 17.1 Priority matrix

| | High effort | Low effort |
|---|---|---|
| **High impact** | **P1:** RBAC single source of truth · Convert-to-Student action · New sitemap/nav rollout · Universal task system · Pagination/sorting defaults | **P1:** Unify the two "Notifications" features · Remove dead code (already done) |
| **Medium impact** | **P2:** Automation layer v1 (reminders, alerts, SLA) · Consolidated Reports hub + shared charting primitive · Role-specific dashboards | **P2:** Styled/tiered confirmation dialogs · Consolidate duplicate Expense/Broadcast modals |
| **Lower impact (still real)** | **P3:** Roles & Permissions admin UI · Postgres migration · Saved/custom views · Teacher Performance reporting | **P3:** Command palette (surprisingly cheap given the existing `/`-search seed pattern) |
| **Strategic bets** | **P4:** Student/Parent self-service portal · Multi-branch data model · Mobile-native Teacher/Operator app | — |

### 17.2 Phased roadmap

**Phase 1 (30 days) — Architecture-prep & hotfixes**
- RBAC: backend-served single permission source of truth (§14.2 item 1)
- Real "Convert Lead → Student" action (§7.3)
- Pagination + sorting defaults on the highest-risk tables first (Users, Leads list, Debtors,
  Warnings)
- Unify the two "Notifications" features (rename the visit-log page)
- *(Already complete: dead `Discounts` page and unreachable `RecordPaymentModal` removed)*
- **Effort:** Medium · **Impact:** High · **Risk:** Low · **Dependencies:** none blocking

**Phase 2 (60 days) — Navigation & task foundation**
- New 7-domain sitemap/sidebar rollout (§4–5), including the command palette
- Unified entity detail-page standard applied to Student, Lead, Group (§6.8)
- Universal task/follow-up system, generalized from Leads' existing reminder pattern
- **Effort:** High · **Impact:** High · **Risk:** Medium (touches every page's navigation
  wiring) · **Dependencies:** Phase 1's single permission source (nav needs one place to ask
  "what can this user see")

**Phase 3 (90 days) — Automation & reporting**
- Automation layer v1: payment reminders, attendance-pattern alerts, lead SLA/escalation,
  auto-assignment (§13)
- Shared charting primitive + consolidated Reports hub (§12), replacing the three independent
  hand-rolled charts
- **Effort:** High · **Impact:** High · **Risk:** Medium · **Dependencies:** Phase 2's task
  system (automation needs somewhere to land its output)

**Phase 4 (6 months) — Scale & administration**
- Role-specific dashboards for every role (§11)
- Roles & Permissions admin UI (§14.2 item 4)
- Postgres migration, executed proactively per §16 (not reactively)
- Saved/custom views, Teacher Performance reporting, Month-End Close workflow (§10.2)
- Multi-branch data model foundation (§16) — even if no second campus exists yet, lay the
  `branch_id` groundwork now
- **Effort:** High · **Impact:** Medium-High · **Risk:** Medium (the DB migration specifically
  carries real production risk and needs its own careful cutover plan, independent of this
  document's scope) · **Dependencies:** Phase 3's reporting foundation

**Phase 5 (12 months) — New surfaces**
- Student/Parent self-service web portal (§6.6–6.7)
- Mobile-native app for Teacher attendance + Call Center power-dial (§15)
- Full search infrastructure at scale (§16)
- Alumni lifecycle state + referral/marketing reuse loop (§8.2)
- **Effort:** Very High · **Impact:** High (new revenue/retention surface, not just internal
  efficiency) · **Risk:** Medium-High (new user-facing surfaces are new support and security
  surface area) · **Dependencies:** everything prior — this phase only makes sense once the
  internal architecture from Phases 1–4 is solid; building a parent-facing portal on top of
  today's three-source RBAC and zero-automation collections process would just export the same
  problems to a bigger audience.

---

## 18. Final Recommendations

Ten recommendations, in priority order, each a direct answer to the highest-leverage finding in
its section:

1. **Fix the Lead → Student handoff first.** It's the cheapest, highest-visibility functional
   fix in this entire review, and it's the literal core of the business (§7.3).
2. **Collapse permissions to one source of truth before building anything else navigational.**
   Every later phase that touches access control gets cheaper once this exists; every phase that
   doesn't wait for it inherits the current three-way drift risk (§14.2).
3. **Build the task/timeline system before the automation layer.** Automation without a place to
   land its output is just more notifications, not a capability (§6.8, §13).
4. **Make pagination and sorting the default, not opt-in, starting now — not at 5,000
   students.** This is cheaper to fix with 500 students' worth of data than to retrofit under
   live load (§16).
5. **Reorganize navigation around business objects, not departments**, and pair it with a
   command palette — the palette scales with feature growth in a way no sidebar reorganization
   alone can (§4–5).
6. **Give Finance its own capability, not necessarily its own role** — the current split between
   Hunter's partial finance access and Admin's full access leaves no persona whose dashboard is
   actually built for finance work (§6.5, §14.2 item 3).
7. **Consolidate the six overlapping finance screens around one Finance Reports hub** before
   adding new reporting types — solving charts/reporting once, not four separate times, per
   module (§12).
8. **Design the multi-branch/location concept in Phase 4, not when the second campus is already
   being opened.** Retrofitting this into a live, revenue-bearing system is far more expensive
   than building it in ahead of need (§16).
9. **Treat Teacher and Call-Center power-dial as the only two genuinely mobile-native journeys**
   — invest mobile-app effort there specifically rather than spreading it thin across every
   role's every screen (§15).
10. **Sequence the student/parent portal last, not first**, despite it being the most visible
    "new feature" — it should be built on top of a solid task/automation/RBAC foundation, or it
    will simply expose today's manual-collections and permission-drift problems to a much larger
    external audience (§17 Phase 5).

**Closing framing:** this CRM does not need a new data model, a new backend, or a rewrite. It
needs its existing, sound data model wrapped in an information architecture organized around
business objects instead of departments, a single permission source of truth instead of three,
a universal task/timeline layer instead of one module-specific implementation, and a scaling
plan executed ahead of the load that will otherwise force it. Every recommendation in this
document is sequenced to compound on the ones before it — that ordering, not any single feature,
is the actual architecture decision this review is making.
