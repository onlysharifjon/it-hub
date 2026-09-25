# CRM Redesign v3 — Progress

Companion to `CRM_DESIGN_SYSTEM_V3.md`. Source audits: `CRM_DISCOVERY_REPORT.md`,
`UI_AUDIT_REPORT.md`, `CRM_PRODUCT_ARCHITECTURE_V2.md`.

Legend: **✅ done** · **◐ partial** (works and looks right, deeper refactor pending) · **☐ open**

---

## 1. Foundation

| Item | State | Notes |
|---|---|---|
| Token layer rewritten (purple + Untitled-UI neutrals + semantics) | ✅ | `styles.css` `:root`, 16 groups, ~120 tokens |
| Dark theme removed | ✅ | 62 rule blocks deleted |
| Ocean theme removed | ✅ | incl. sidebar/login overrides |
| Theme switcher + `ThemeContext.jsx` removed | ✅ | Topbar, `App.jsx`, logo, watermark de-themed |
| Second font family (Geist) removed | ✅ | was loaded, never referenced |
| Type scale enforced (8 steps) | ✅ | |
| Space scale (4px rhythm) | ✅ | |
| Radius / elevation / motion / focus tokens | ✅ | modal radius = 24px per brief |
| Hardcoded hex eliminated outside tokens | ✅ | only the login brand panel keeps literals, intentionally |
| `prefers-reduced-motion` honoured | ✅ | |

## 2. Primitives

| Primitive | State | Notes |
|---|---|---|
| Buttons — 4 levels × 4 sizes | ✅ | 5 legacy systems collapsed; `.btn-sm` kept as pixel-identical alias |
| Segmented control | ✅ | new; used by Payments view switch + table density |
| Form system (one rule for every control) | ✅ | fixes the unstyled `.form-input` in 6 files |
| Field / Input / Select / Textarea / Checkbox / Switch | ✅ | `ui/Field.jsx` |
| Table system — sticky head, density, sorting, row actions, empty/loading | ✅ | `ui/DataTable.jsx` + `.data-table` |
| Modal system — 24px, 3 zones, mobile sheet | ✅ | `ui/Modal.jsx` |
| Drawer | ✅ | shares modal chrome + keyboard behaviour |
| ConfirmDialog (replaces `window.confirm`) | ✅ | `requireText` mode for irreversible actions |
| Card system — card / chart-card / kpi / entity / alert | ✅ | |
| MetricStrip (the anti-card) | ✅ | |
| Badge / status pill (AA-safe) | ✅ | |
| Meter, Sparkline, BarChart, Waterfall | ✅ | one charting primitive, was 4 bespoke bar charts |
| Empty / error / skeleton states | ✅ | `ui/States.jsx` |

## 3. Shell

| Area | State | Notes |
|---|---|---|
| Sidebar redesigned (Linear-inspired light panel) | ✅ | grouped, collapsible, remembered, active marker, rail mode |
| Rail mode narrows the shell grid | ✅ | previously the panel shrank and left a gap |
| Sidebar brand block (logo + workspace + role) | ✅ | |
| Topbar (⌘K, quick actions, notifications, profile) | ✅ | theme toggle removed |
| Sticky page headers, offset below the topbar | ✅ | |
| Command palette | ✅ | inherited, restyled |
| Mobile drawer + bottom-sheet modals | ✅ | rail mode disabled on mobile |

## 4. Modules

| Module | State | What changed |
|---|---|---|
| Dashboard | ✅ | executive layout: hero figure + P&L waterfall → attention panel → 6 operational metrics → **student growth** → **teacher performance** → **recent activity** → expenses → monthly table |
| Finance | ✅ | Stripe-style: collection-rate hero, trend, insights with actions, risk cards, debtor list (built in v2, re-tuned to the v3 palette) |
| Payments | ✅ | KPI wall → MetricStrip; segmented list/debtors; both tables → DataTable (sort + density + pagination); modal → `Modal` + `Field`; `confirm()` → ConfirmDialog; new payment-preview block |
| Students | ✅ | DataTable + density toggle; header/subtitle grammar |
| Users | ✅ | raw table → DataTable (sort, pagination, empty state); row actions |
| Parents | ✅ | raw table → DataTable; chips for children; search moved into the table toolbar |
| Expenses | ✅ | DataTable + flush card + footer total; modal → `Modal` + `Field`; ConfirmDialog |
| Special discounts | ✅ | DataTable; full modal rebuild with `Select`/`Input` + hints; ConfirmDialog |
| Salary | ✅ | MetricStrip; DataTable with inline edit + `Meter`; the inline-styled breakdown modal → real `Modal` + DataTable |
| Teacher salaries | ✅ | MetricStrip (adds average per teacher); header grammar |
| Academic (5 tabs) | ✅ | one conditional `<table>` → per-tab column definitions on DataTable; leaderboard too |
| Audit warnings | ✅ | DataTable; staff filter in the toolbar; ConfirmDialog for cancellation |
| Employees | ✅ | DataTable; Telegram-link modal → `Modal` + `Field` |
| My warnings | ✅ | rewritten on DataTable, with an active-count subtitle |
| Notifications (visit log) | ✅ | both tables → DataTable; avatar cell primitive |
| Bot admin (3 tabs) | ✅ | all three raw tables → DataTable |
| Tariffs / Courses | ✅ | already on DataTable; header grammar + subtitles |
| Groups | ✅ | card grid rebuilt on the entity-card rules; status/day filters → segmented controls; progress states named (`is-near` / `is-done`) instead of inline colours |
| Today's attendance | ✅ | group cards and the tap-list rebuilt: 52px touch rows, status shown by colour **and** text **and** edge bar; card CTA is secondary until hover |
| Leads (kanban / list / analytics) | ✅ | header grammar, kanban column/card on the v3 surface rules, view toggle → segmented, drawer deduped, per-card "Band qilish" no longer a wall of purple |
| Group detail | ✅ | header grammar; context sidebar is now sticky and rebuilt on one `.info-card` rule; attendance grid intentionally left bespoke |
| Student detail | ✅ | header grammar; shares the rebuilt `.info-card` / `.stat-row` sidebar |
| Teacher dashboard | ✅ | **rewritten** — 101 inline style blocks → 11; now on `.page`/`MetricStrip`/`.tab-bar`/`Meter`/`DataTable`/`Modal`; also fixed a latent `ReferenceError` (undefined `th` in the salary breakdown table) |
| Lessons | ✅ | delete confirmation lifted to `ConfirmDialog`; inherits the system |
| Chatbot | ✅ | header grammar; also fixed two content bugs the redesign exposed — every row read "Invalid Date" (the code appended `Z` to timestamps that already carried a `+05:00` offset) and Telegram HTML (`<b>…`) was rendering as literal text in previews and bubbles |
| Feedback inbox | ✅ | rebuilt: tab bar, semantic status cards, empty state, skeleton |
| Login | ✅ | brand panel reworked to the purple gradient; inputs/buttons aligned to the system |
| Public intake | ✅ | inherits the system |

## 5. Backend

| Item | State | Notes |
|---|---|---|
| `GET /stats/student-growth` | ✅ | monthly joins + cumulative, admin-only; powers the dashboard growth block. Additive — no schema or migration change. |

## 6. Audit findings closed

From `UI_AUDIT_REPORT.md` §17:

- **#1** TeacherDashboard invisible to theming → moot, themes removed; page is fully tokenised.
- **#2** two fonts loaded, one used → ✅ fixed.
- **#3** `.form-input`/`.form-label`/`.form-group` had no CSS in 6 files → ✅ fixed.
- **#4** orphaned `Discounts.jsx` → ✅ removed.
- **#7/#8** duplicated role/stage colour maps → ✅ centralised in `constants/domain.js`.
- **#9** `window.confirm()` on every destructive action → ✅ **fully closed**. All 20 call sites
  now use `ConfirmDialog` via a new `useConfirm()` hook, which keeps the call shape of
  `confirm()` (`if (!await ask({...})) return`) so the conversion did not restructure handlers.
- **#12** no pagination on ~31 of 35 tables → ✅ on every converted table.
- **#13** no column sorting anywhere → ✅ sorting is now the default on converted tables.
- **#15** duplicate `.search-input { width }` → ✅ fixed.
- **#17/#18** missing `aria-label`s on icon buttons → ✅ on every converted screen.
- **#19** 3–5 overlapping small-button systems → ✅ collapsed to one.
- **#22** Salary breakdown modal bypassing the modal system → ✅ fixed.
- **#26** Login disconnected from the design system → ✅ fixed.
- **#27** 4 unshared bar-chart implementations → ✅ one `BarChart`.
- **#29** inconsistent empty/loading states → ✅ on converted screens.
- **#30** inconsistent number formatting → ✅ `uz-UZ` on converted screens.

Still open: **#5** (dead `RecordPaymentModal` in `Students.jsx`), **#6** (role access defined in
3 places), **#10** ("Notifications" naming collision — the sidebar label is now
"Kelish-ketish", the page title follows, but the internal key is unchanged), **#11** (duplicate
Payments/Expenses entry points), **#14** (only 2 of 4 group stages exposed), **#20/#21**
(duplicate expense and broadcast modals), **#23** (contentEditable certificate affordance),
**#24** (no 404 route), **#28** (funnel-board complexity), **#31** (no shared date util),
**#32** (tooltip-only explanation — improved in Payments, still present elsewhere),
**#33** (no unsaved-changes guard), **#34** (wide grids on mobile).

## 7. Verified in a browser

The build was driven end-to-end in headless Chromium against an **isolated copy** of the
database on a separate port — production data and credentials were never touched. Every page
was loaded as `admin` and checked for console/page errors (zero remain), then captured at
1440×950 and at 390×844.

Fixes that only surfaced this way:

- the sidebar section had been **silently deleted** by an earlier edit (the section-splitting
  helper's header regex did not tolerate a blank line inside a comment block), so navigation
  was rendering unstyled — restored and the helper hardened;
- `DataTable` never passed `column.className` to the `<th>`, so the sticky actions column had a
  sticky body but a scrolling header;
- table cells wrapped, giving ragged row heights on wide tables — cells are now `nowrap` with
  `.cell-wrap` / `.cell-clamp` opt-outs, and the actions column sticks to the right edge;
- the centred 380px brand watermark was legible through tables and empty states — removed;
- purple was leaking into repeated elements (one primary button per kanban card, per attendance
  card, per filter row) — those became secondary controls that adopt the brand colour on hover.

## 8. Next

1. The Leads funnel board onto system tokens (the last bespoke surface).
2. A shared `formatDate` / `formatMoney` util, then a codemod across all screens (#31).
3. Unsaved-changes guard in `Modal` (#33).
4. Collapse the duplicate expense and broadcast modals (#20/#21).
5. Expose all four group stages in the group form (#14).
6. Remove the dead `RecordPaymentModal` in `Students.jsx` (#5).

## 9. Deployment

Per project convention, after each change: `npx vite build` → `pm2 restart it_hub_api` →
`systemctl reload nginx`. Frontend builds to `/var/www/it-hub/frontend/dist`.
