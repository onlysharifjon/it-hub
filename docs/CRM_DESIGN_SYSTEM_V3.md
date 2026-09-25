# Minar CRM — Design System v3

**Status:** live · `crm.minaracademy.uz`
**Supersedes:** the ad-hoc token set in `styles.css` v2 (blue primary, 3 themes) and every
per-component style island documented in `UI_AUDIT_REPORT.md` §16–17.
**Single source of truth:** `frontend/src/styles.css` (`:root`) + `frontend/src/components/ui/*`.

---

## 0. What this system is for

This is not a marketing site and not a generic admin template. It is a **dense operational
product**: seven roles run a school's whole loop — lead → student → group → attendance →
payment → payroll — inside it, all day, mostly on a laptop.

That constrains the design more than any style preference:

| Constraint | Consequence in the system |
|---|---|
| People read numbers in columns and compare them | tabular figures everywhere; right-aligned money; one meter primitive instead of five bespoke bars |
| Screens are long and scroll a lot | sticky page headers, sticky table headers, sticky period pickers |
| Most pixels are data, not chrome | colour is reserved for meaning; the workspace is neutral |
| Every screen has 3–10 possible actions | one button hierarchy (primary / secondary / ghost / danger), never two |
| Destructive actions are common | one confirmation dialog primitive, with a typed-confirmation mode for irreversible ones |

**The rule that generates most of the others:** *if a colour appears, it must mean something.*

---

## 1. Colour

### 1.1 Brand — purple

| Token | Hex | Used for |
|---|---|---|
| `--purple-50` | `#FAF5FF` | active nav background, selected row, primary-tinted surface |
| `--purple-100` | `#F3E8FF` | badge fill, chip fill, focus companion |
| `--purple-200` | `#E9D5FF` | primary border, chip border |
| `--purple-300` | `#D8B4FE` | hairlines on dark, decorative |
| `--purple-400` | `#C084FC` | **focus border**, brand gradient highlight |
| `--purple-500` | `#A855F7` | focus ring alpha source (`--ring`) |
| `--purple-600` | `#9333EA` | **`--primary`** — primary buttons, active markers, meters |
| `--purple-700` | `#7E22CE` | primary hover, `--primary-text` (AA on white and on purple-50) |
| `--purple-800` | `#6B21A8` | primary active/pressed |
| `--purple-900` | `#581C87` | login brand panel depth |

**Purple is allowed in exactly five places:**

1. the primary button of a screen (there is at most one per view);
2. the active navigation item (background + text + left marker);
3. selection and focus (`--ring`, selected table row, selected chip);
4. the login brand panel — the only place the brand is allowed to be loud;
5. the primary series in a chart.

**Purple is forbidden** as a decorative surface, as a heading colour, as a table-header colour,
as a badge colour for anything that is not "primary/selected", and as a second accent inside
a card that already has a primary action.

A corollary that mattered in practice: **a control that repeats cannot be primary.** A kanban
board with a filled purple "Band qilish" on every card, or an attendance page with a filled
purple CTA on every group card, is not a board with primary actions — it is a purple board, and
the colour stops meaning anything. Those controls are secondary at rest and adopt the brand
colour on hover of their card.

### 1.2 Neutral — the workspace

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#F8FAFC` | app background (behind cards) |
| `--workspace` / `--surface` | `#FFFFFF` | cards, tables, modals |
| `--surface-elev` / `--nav-bg` | `#FCFCFD` | sidebar, elevated headers |
| `--surface-2` | `#F8FAFC` | row hover, `th`, quiet fills |
| `--surface-3` | `#F2F4F7` | meter track, skeleton, segmented control |
| `--border` | `#EAECF0` | every default hairline |
| `--border-2` | `#D0D5DD` | input border, hover border, strong divider |
| `--text` | `#101828` | primary text, headings, `<strong>` in tables |
| `--text-2` | `#475467` | body-secondary, table cells |
| `--muted` | `#667085` | labels, captions — AA at 4.9:1 |
| `--muted-2` | `#98A2B3` | placeholder, disabled, tertiary meta |

> **Why `--muted` is `#667085` and not the spec's tertiary `#98A2B3`:** `#98A2B3` on white is
> 2.5:1, which fails WCAG AA for the label and caption text this token actually carries in this
> codebase. Tertiary is kept as `--muted-2` for placeholders and disabled states, where the
> contrast requirement does not apply.

### 1.3 Semantic

| Meaning | Solid | Soft fill | Text on soft | Border |
|---|---|---|---|---|
| Success | `#16A34A` | `#DCFCE7` | `#15803D` | `#86EFAC` |
| Warning | `#F59E0B` | `#FEF3C7` | `#B45309` | `#FCD34D` |
| Danger | `#DC2626` | `#FEE2E2` | `#B91C1C` | `#FCA5A5` |
| Info | `#2563EB` | `#DBEAFE` | `#1D4ED8` | `#93C5FD` |

**Never write text in the solid colour on the soft fill** — `#F59E0B` on `#FEF3C7` is 1.9:1.
Every badge, insight and status pill uses the `-text` variant, which passes AA.

### 1.4 Data visualisation

`--viz-1…6`: purple, teal, blue, amber, pink, lime. `--accent` (teal `#0E9384`) is the
*second* data hue, so a profit line stays legible over purple income bars.

### 1.5 Themes

**There is one theme.** The `dark` and `ocean` themes and the theme switcher were removed:
they were only ~60% implemented (TeacherDashboard, Login, Salary and most inline styles never
participated), so switching produced a half-dark app. One well-tuned light system beats three
broken ones. `ThemeContext.jsx` is deleted.

---

## 2. Typography

- **One family:** Inter, via Google Fonts, with `cv11`/`ss01` on (single-storey `a`, tailed `l`).
  The unused `@fontsource-variable/geist` import was removed — it was two font families loaded
  and one used.
- **Scale (8 steps, nothing between them):**
  `--text-xs 11` · `--text-sm 12.5` · `--text-base 14` · `--text-md 15` · `--text-lg 18` ·
  `--text-xl 22` · `--text-2xl 28` · `--text-3xl 36` · `--text-display 44`
- **Weights:** 400 body · 500/550 emphasis · 600/650 headings and labels · 700 figures.
- **Tracking:** headings `-.018em` to `-.03em` (larger = tighter). Body is untracked.
- **Numbers:** `font-variant-numeric: tabular-nums` on every table cell, KPI, metric and meter.
  Money in a column must be comparable at a glance.

Uppercase is used in exactly two places: table headers and eyebrows. **Form labels are no longer
uppercase** — they were competing with the fields they described.

---

## 3. Space, radius, elevation

- **Space:** 4px rhythm, `--space-1…10`. No literal pixel padding in new code.
- **Radius:** `4 / 6 / 8 / 12 / 16 / 24 / 999`.
  Controls 8 · cards 16 · **modals 24** · pills 999.
- **Elevation:** five steps (`xs → xl`) plus `--shadow-modal`. Shadows are neutral-tinted
  (`rgba(16,24,40,…)`), never pure black — black shadows read as grey smudge on `#F8FAFC`.
- **Focus:** one treatment everywhere — `--border-focus` (purple-400) + `0 0 0 4px var(--ring)`.

---

## 4. Components

### 4.1 Buttons — two axes, no third system

**Level:** `primary` (default, purple) · `.secondary` (white, bordered — the workhorse) ·
`.ghost` (transparent, tertiary) · `.danger` · `.link`.
**Size:** `.lg 44` · default `38` · `.small 32` · `.xs 26`.
Icon-only: `.btn-icon` (30×30).

The five previously-coexisting small-button systems (`.button.small`, `.btn-sm`,
TeacherDashboard's inline `navBtn`/`TabBtn`, Login's `.lp-btn`, GroupCertificates' `.mcert-btn`)
are now one visual: `.btn-sm` is kept as an alias and is **pixel-identical** to
`.button.secondary.small`, so the remaining call sites can be migrated without a visual diff.

New: `.segmented` — the control for mutually exclusive views (list/debtors, table density).

### 4.2 Forms — one language

Every input, select, textarea, `.field` and `.form-input` share **one** rule block:
38px min-height, 8px radius, `--border-2`, `--shadow-xs`, purple focus ring. `.field-sm` (32px)
is the toolbar variant.

This closes the single largest defect in the audit: `.form-input` / `.form-label` / `.form-group`
were used in six files (Users, Salary, Expenses, Parents, BotAdmin, Dashboard) **with no matching
CSS anywhere** — those screens rendered raw browser inputs. They now render identically to the
rest of the app.

Selects get a custom SVG chevron so they look the same on every OS.
Field anatomy: label (12.5px, 600, secondary) → control → hint *or* error. Never both.

### 4.3 Tables — the primary work surface

`components/ui/DataTable.jsx` + `.data-table`:

- **sticky headers** by default (`.has-sticky-head`), `.is-scroll` for a self-scrolling table;
- **density**: `.is-compact` 36px · default 44px · `.is-relaxed` 52px, with an optional
  user-facing toggle that remembers the choice per table (`densityKey`);
- **sorting** on any column (`sortable`, optional `sortValue`), client or server mode;
- **pagination** client (`clientPageSize`) or server (`meta` + `onPageChange`);
- **row actions** fade to 55% at rest and to 100% on row hover/focus — visible enough to be
  discoverable, quiet enough that the eye lands on data; always full opacity on touch;
- the **actions column sticks to the right edge**, so on a wide table (Students has 11 columns)
  the actions stay reachable without scrolling back;
- **cells do not wrap** (`white-space: nowrap`, with `.cell-wrap` / `.cell-clamp` opt-outs).
  Ragged row heights make a column impossible to scan; the table scrolls instead;
- **empty / loading / error** states come from the component, so they are identical everywhere.

Before v3 the app had **zero column sorting** and pagination on 4 of ~35 tabular views.

### 4.4 Modals — 24px, three zones

`.modal-overlay` (`rgba(16,24,40,.55)` + 6px blur) → `.modal` (24px radius, `--shadow-modal`,
`modalIn` transform-in). Header (title + optional subtitle + close) / scrolling body / footer
(`--surface-2`, actions right-aligned, primary last). Sizes `sm 400 · md 480 · lg 680 · xl 880`.
On ≤640px the modal becomes a bottom sheet with full-width actions.

`Drawer` shares the chrome and the keyboard behaviour (Escape, focus trap, `aria-modal`).

`ConfirmDialog` replaces `window.confirm()` — every one of the app's 20 destructive actions.
The `useConfirm()` hook keeps the ergonomics of the thing it replaces, which is why the
conversion actually happened:

```jsx
const [confirmUI, ask] = useConfirm()
if (!await ask({ title: "O'chirish", message: `"${x.name}" o'chirilsinmi?` })) return
return <>{confirmUI} …</>
```

Irreversible actions add `requireText` (type the name to confirm). The dialog renders in a
`.confirm-layer` at `z-index: 1200` so it still lands on top when it is opened from inside
another modal or drawer.

### 4.5 Cards — four kinds, one surface rule

| Class | Job |
|---|---|
| `.card` | generic content block |
| `.chart-card` | analytics block (head + chart/table); `.is-flush` for edge-to-edge tables |
| `.ui-kpi` | one number + trend + sparkline (`KpiCard`) |
| `.entity-card` | a clickable object (group, student, staff) — lifts on hover |
| `.alert-card` | a state that needs attention — semantic left border + soft fill |

All share 16px radius, `--border`, `--shadow-xs`. `.ui-metric-strip` exists as the
**anti-card**: when six numbers need showing, a single divided strip beats six boxes.

### 4.6 Navigation — Linear-inspired

The sidebar was a black `#0a0a0a` slab whose active item was a solid white pill — the highest-
contrast element on the screen was the menu, not the work.

v3: `--nav-bg #FCFCFD`, one hairline border, hierarchy carried by **weight**, not colour.
Groups are collapsible and remembered (`localStorage`); the group containing the current page
auto-opens. Active item = purple-50 fill + purple-700 text + purple-600 icon + a 3px rounded
left marker. Rail mode (64px, icons only) narrows the shell grid too. Badges are counts;
in rail mode they degrade to a dot.

The topbar is a 56px translucent bar: ⌘K search, "Yangi" quick actions, notifications, avatar
menu. Page headers stick **below** it (`top: var(--topbar-h)`), never underneath it.

---

## 5. Page grammar

Every screen is built the same way:

```
page-header (sticky)        title · one-line context · actions on the right
  ↓
MetricStrip / KPI           the state of the thing, in numbers
  ↓
AttentionPanel              (dashboards only) what needs a human today
  ↓
analytics                   trend, breakdown, insights
  ↓
DataTable                   the records, with the toolbar attached to the table
  ↓
Modal / ConfirmDialog       mutations
```

**Finance** is the reference implementation of the analytics layer (one hero figure at 44px,
three supporting metrics, trend, insights with actions, risk cards, debtor list).
**Dashboard** is the reference for the executive layer (leading figure + P&L waterfall →
attention list → operational metrics → growth → teacher performance → recent activity).

---

## 6. Motion

`--dur-fast .12s` (hover/colour) · `--dur .18s` (dropdowns, reveals) · `--dur-slow .28s`
(modals, nav collapse). Easing `--ease` for UI, `--ease-out` for entrances.
Everything collapses to ~0 under `prefers-reduced-motion`.

Nothing animates size or position on scroll. Data does not bounce.

---

## 7. Accessibility floor

- One visible focus style, on every interactive element.
- Every icon-only button has `title` **and** `aria-label`.
- Colour is never the only signal: status pills carry a dot + text, trends carry an arrow + sign.
- All soft-fill/text pairs pass AA.
- Skip link to `#main-content`; `role="dialog"` + focus trap + Escape on modals and drawers.

---

## 8. What was removed

- `[data-theme="dark"]` and `[data-theme="ocean"]` — 62 rule blocks, plus the switcher and
  `ThemeContext.jsx`.
- The `@fontsource-variable/geist` imports (loaded, never referenced).
- The duplicate `.drawer` definition in the Leads section.
- The duplicate `.search-input { width }` declaration.
- The duplicate `.sidebar-overlay`, `.field`, `.field-sm`, `.form-input`, badge and
  sticky-header/sort rules that had accumulated in "Phase N" appendix sections.
- Every remaining hardcoded hex outside the token block and the login brand panel.
- `Discounts.jsx` — an orphaned page whose endpoints do not exist server-side.
- The full-bleed brand watermark behind every page (`MinarWatermark` + `.content-watermark`).
  A 380px logo centred in the work area was legible through tables and competed with empty-state
  messages. The brand lives in the sidebar mark and on the login panel; the work area is for work.

---

## 9. How to extend it

1. **Need a colour?** Use a role token. If none fits, the question is what the colour *means* —
   answer that first, then add a role token, never a raw hex in a component.
2. **Need a card?** Pick one of the four. A fifth kind of card is a smell.
3. **Need a table?** `DataTable`. If it needs something DataTable lacks, add it to DataTable.
4. **Need a confirmation?** `ConfirmDialog`, never `window.confirm`.
5. **Need a number?** `Metric` in a strip, or `KpiCard` if it is *the* number of the screen.
6. **Adding a page?** Add it to `constants/nav.js` **and** `App.jsx`'s `PAGE_ACCESS`. Those two
   plus the backend's per-endpoint check are the three places role access lives.

---

## Appendix — v3.1 visual polish (semantic colour + eye strain)

A refinement pass over the same architecture. No page was redesigned; the token
layer was re-tuned and three new rules were added.

### Layered surfaces replace flat white

The app was almost entirely `#FFFFFF` — background *and* card — so cards never read as
elevated and long sessions were tiring. Depth now comes from a surface ladder, not from
heavier shadows (shadow opacity was in fact *reduced*):

| Token | Value | Role |
|---|---|---|
| `--bg` | `#F5F6FA` | app background — the floor |
| `--workspace` | `#F8F9FC` | table headers, sticky bars, input fills |
| `--surface-2` | `#FAFAFC` | chips, footers, secondary blocks |
| `--surface-3` | `#F2F4F7` | interactive hover, meter tracks, skeletons |
| `--surface` | `#FFFFFF` | cards, table rows, modals — **kept white** |

Measured on the built pages: pure white now covers 21–52% of the viewport (was
effectively everything), with 40–73% carried by the layered neutrals.

### Brand hue moved to violet

`--primary` `#7C3AED`, hover `#6D28D9`, active surface `#F3E8FF`, active text `#6D28D9`.
`--warning` moved `#F59E0B → #D97706` and `--border` `#EAECF0 → #E4E7EC` to match.

### Module colour — meaning, not decoration

Fifteen `--mod-*` tokens (one per module). Two delivery mechanisms, and no page ever
writes a colour itself:

- **Pages**: `App.jsx` puts `data-module={activePage}` on the page wrapper; a `[data-module]`
  block resolves `--mod` / `--mod-soft`. The page-title icon and empty-state icon read them.
- **Sidebar**: `constants/nav.js` carries a `tone` per item, passed as an inline `--mod`.

**The colour is normally invisible.** All 19 nav icons sit at neutral `#667085`; the module
hue appears only on hover. Active stays brand violet, because "you are here" must mean one
thing everywhere. Nineteen simultaneously coloured icons would make colour mean nothing.

### Three rules that removed most of the noise

1. **A control that repeats cannot be primary.** A filled purple button on every row of the
   visit log made purple meaningless; those rows now use a soft semantic button that
   saturates on hover. Same reasoning already applied to kanban cards and attendance cards.
2. **Colour marks the exception, not the column.** Payment amounts and expense rows were
   fully green/red — when every row is coloured, colour stops being a signal. Amounts are
   neutral; the status badge carries the meaning. `is-out` is kept only where direction is
   the point (debt, P&L).
3. **Icons live in soft tiles, never bare saturated.** `.icon-tile` (24/28/32px) plus the
   page-title and attention-panel icons.

### Accessibility

`--muted-2` (`#98A2B3`, 2.5:1 on white) was being used as body text in 13 places — chart
axis labels, sidebar footer, eyebrows, pagination. All raised to `--muted` (`#667085`,
4.9:1). The token is now documented as placeholder/disabled-only.

`Badge` soft backgrounds changed from `${color}1a` (alpha — composited against whatever was
behind, so contrast depended on context) to `color-mix(… 12%, #fff)` (opaque).

Verified in headless Chromium: **24 pages, zero runtime errors, zero contrast failures**
(automated WCAG AA check on every text node against its resolved background), no horizontal
overflow at 375 / 768 / 1024 / 1440 / 1920.
