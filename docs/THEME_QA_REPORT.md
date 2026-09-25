# Theme QA Report — Light / Dark

Method: headless Chromium against an **isolated copy** of the production database on a
separate port. Production data and credentials were never touched; the copy was deleted
afterwards. Every check below was run **twice — once per mode**.

The audit is automated, not eyeballed: for every text node on every page it resolves the
actual painted background by walking ancestors, computes the WCAG contrast ratio, and
applies the AA threshold (4.5:1, or 3:1 for large/bold text). It separately counts
large light-coloured blocks while in dark mode to catch "white leakage".

---

## 1. Pages tested (24 authenticated + 2 public)

Dashboard · Leads · Students · Groups · Payments · Finance · Expenses · Teacher Salaries ·
Salary · Tariffs · Courses · Special Discounts · Today's Attendance · Academic ·
Feedback Inbox · Visit Log · ChatBot · Parents · Users · Employees · Audit Warnings ·
My Warnings · Bot Admin · Lessons — plus **Login** and **Public Intake** (unauthenticated),
and these interaction states: modal, drawer, Group Detail (attendance grid), Certificate
designer, Teacher Dashboard (signed in as a `teacher`).

| Check | Light | Dark |
|---|---|---|
| Runtime errors (page + console) across all pages | **0** | **0** |
| WCAG AA contrast failures | **0** | **0** |
| Stray white blocks in dark mode | n/a | **0** |
| Horizontal overflow @ 375/390/768/1024/1280/1440/1920 | **none** | **none** |

## 2. Theme switching

| Behaviour | Result |
|---|---|
| No stored preference + OS dark | `data-theme="dark"` ✓ |
| No stored preference + OS light | light (no attribute) ✓ |
| Stored `light` while OS is dark | light — stored choice wins ✓ |
| Toggle click | `data-theme` updates, `localStorage.theme` written ✓ |
| After reload | preference retained ✓ |
| Flash-of-wrong-theme | none — `body` background is `rgb(11,15,25)` on the first frame ✓ |
| `aria-pressed` state | `Yorug' rejim=false, Qorong'i rejim=true` ✓ |
| Keyboard operable | ✓ |
| Cross-tab sync | via `storage` event ✓ |
| Follows OS live (until user chooses) | ✓ |

## 3. Issues found and fixed during QA

Everything below was caught by the audit or by looking at the rendered screenshots, and
fixed in this pass:

1. **App failed to boot** — `COLORS is not defined`. Refactoring the lead-stage palette to CSS
   variables removed an object still referenced in five places. Restored as a `var(--stage-*)`
   map. *(Caught by the error sweep, not by the build — Vite compiled it fine.)*
2. **Logo stayed brand-blue on the dark sidebar.** `BrandLogo` now resolves `tone="auto"` from
   the theme and serves the white lockup in dark.
3. **Kanban depth inverted in dark** — columns (`#1B2230`) were lighter than their cards
   (`#151B28`). Introduced `--surface-sunken`.
4. **White text on light fills failed AA in dark** — `#FFF` on `#A855F7` = 3.96:1, on `#F87171`
   = 2.77:1. Affected the avatar, skip link, notification count, pagination, date-range
   selection, stack-bar labels. Added `--primary-on` / `--danger-on` / `--success-on` /
   `--warning-on` / `--info-on`.
5. **Light-mode regression from themeable stage colours** — `--stage-teal` `#0E9384` is 3.8:1
   on white, so "Fullstack" badges and group progress percentages dropped below AA. Split into
   fill vs `-text` tokens.
6. **Finance trend bars went olive/brown in dark** — 42% opacity over a dark ground muddies
   hue. Raised to 70% in dark only (and similar for waterfall/bar charts).
7. **Certificate chrome leaked light theme** — the toolbar was `#fff` with a near-invisible
   title. Toolbar and stage now follow the theme; the A4 sheet stays white by design.

## 4. Module-by-module notes

- **Dashboard** — KPI card, P&L waterfall, attention panel (soft tiles), metric strip, and the
  income/expense bar+line chart all readable in both modes; grid lines use `--viz-grid`,
  which is `#E4E7EC` light / `#273244` dark, so they stay visible but subtle.
- **Finance** — collection-rate hero, trend, insights, stack bar, risk cards, debtor list.
  Red/green stay legible without going neon (`#4ADE80` / `#F87171` on `#151B28`).
- **Leads** — kanban columns, cards, stage edge colours, pool/overdue badges, drawer, filters,
  view toggle. Stage colours use the dark palette (`#818CF8`, `#22D3EE`, …).
- **Students / Groups** — tables with sticky headers and sticky action column, group cards,
  stage badges, payment states, avatars (uploaded photos are not washed out).
- **Attendance** — Group Detail grid: present/absent/unmarked legend carries **icon + colour +
  text**, so it never relies on colour alone.
- **Academic / Payments / Salary / Expenses** — tabular figures, semantic badges, meters.
- **Teacher Dashboard** — verified signed in as a teacher; no hardcoded surfaces remain.
- **Login** — light: bright, white form panel. Dark: `#151B28` form panel, purple brand panel
  retained in both. **Public Intake** — follows the theme, white or dark card.

## 5. Remaining issues

None blocking. Deliberate, documented in `THEME_SYSTEM_V2.md` §10:

- the certificate sheet stays white in dark mode (it is a print document);
- the login brand panel stays purple in both modes (single loud-brand surface);
- the logo has no official purple variant, so light mode shows the official blue;
- uploaded photos are not dimmed in dark mode;
- the preference is per-device (`localStorage`), not stored per user account.
