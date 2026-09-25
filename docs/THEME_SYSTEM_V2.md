# Theme System v2 — Light / Dark

**Status:** live on `crm.minaracademy.uz`
**Supersedes:** the single light-only token layer, and (earlier) the abandoned 3-theme
`light / dark / ocean` system.
**Source of truth:** `frontend/src/styles.css` (`:root` + `[data-theme="dark"]`) and
`frontend/src/theme.js`.

---

## 1. Architecture

Three layers, in this order:

1. **Primitives** — mode-independent. Brand scale, gray scale, radii, spacing, type,
   motion, layout. **Never redeclared** under `[data-theme]`.
2. **Semantic roles** — declared light in `:root`, dark in `[data-theme="dark"]`.
   Components consume *only* these.
3. **`--color-*` aliases** — the documented public names (`--color-bg`, `--color-surface`,
   `--color-text`, …) mapping onto the role tokens.

This is why the migration was tractable: ~5,900 lines of CSS already consumed role tokens
(`--surface`, `--text`, `--border`, …), so dark mode is largely a **token swap**, not a
rewrite. Only genuinely mode-specific behaviour is expressed as a `[data-theme="dark"]` rule
(five of them, all listed in §6).

## 2. Light tokens

| Role | Value |
|---|---|
| `--bg` | `#F5F6FA` |
| `--workspace` | `#F8F9FC` |
| `--surface` | `#FFFFFF` |
| `--surface-elev` | `#FFFFFF` |
| `--surface-2` | `#FAFAFC` |
| `--surface-3` | `#F2F4F7` |
| `--surface-sunken` | `#F2F4F7` |
| `--surface-input` | `#F8F9FC` |
| `--surface-hover` | `#F2F4F7` |
| `--surface-row` | `#F8F9FC` |
| `--border` / `--border-2` | `#E4E7EC` / `#D0D5DD` |
| `--text` / `--text-2` | `#101828` / `#475467` |
| `--muted` / `--muted-2` | `#667085` / `#98A2B3` |
| `--primary` / hover / active | `#7C3AED` / `#6D28D9` / `#5B21B6` |
| `--primary-mid` (soft) / `--primary-text` | `#F3E8FF` / `#6D28D9` |
| `--overlay` | `rgba(15,23,42,.35)` |

Sidebar `#FFFFFF`, topbar `#FFFFFF`, search `#F8F9FC`.

## 3. Dark tokens

| Role | Value |
|---|---|
| `--bg` | `#0B0F19` |
| `--workspace` | `#0F1420` |
| `--surface` | `#151B28` |
| `--surface-elev` / `--surface-2` | `#1B2230` |
| `--surface-3` / `--surface-hover` | `#202938` |
| `--surface-sunken` | `#0B0F19` |
| `--surface-input` | `#111827` |
| `--surface-row` | `#1B2230` |
| `--border` / `--border-2` | `#273244` / `#344054` |
| `--text` / `--text-2` | `#F9FAFB` / `#D0D5DD` |
| `--muted` / `--muted-2` | `#98A2B3` / `#667085` |
| `--primary` / hover / active | `#A855F7` / `#C084FC` / `#D8B4FE` |
| `--primary-mid` (soft) / `--primary-text` | `#2E1A47` / `#D8B4FE` |
| `--overlay` | `rgba(0,0,0,.60)` |

Sidebar `#0B0F19`, topbar `#0F1420`, search `#111827`. No pure black anywhere.

## 4. Semantic and module colours

| | Light | Dark |
|---|---|---|
| Success | `#16A34A` / bg `#ECFDF3` / text `#15803D` | `#4ADE80` / bg `#0F2A1D` / text `#86EFAC` |
| Warning | `#D97706` / bg `#FFFAEB` / text `#B54708` | `#FBBF24` / bg `#2A1F0A` / text `#FCD34D` |
| Danger | `#DC2626` / bg `#FEF3F2` / text `#B42318` | `#F87171` / bg `#2A1416` / text `#FCA5A5` |
| Info | `#2563EB` / bg `#EFF6FF` / text `#1849A9` | `#60A5FA` / bg `#0E1D33` / text `#93C5FD` |

Fifteen `--mod-*` module colours flip to the brighter dark set (dashboard `#7C3AED → #8B5CF6`,
leads `#2563EB → #60A5FA`, groups `#0891B2 → #22D3EE`, …), and eleven `--soft-*` container
tints flip from light tints to deep tints (`#F3E8FF → #2E1A47`).

**Module colour stays a hover-only signal** in the sidebar in both modes — 19 permanently
coloured nav icons would make colour meaningless. Active is brand purple in both modes.

### `--*-on` tokens — the non-obvious part

Text on a **filled** colour cannot be white in both modes. Light-mode fills are dark
(`#7C3AED`, `#DC2626`) so white works; dark-mode fills are *light* (`#A855F7`, `#F87171`) and
white on them is 3.96:1 and 2.77:1 — both fail AA. So:

```
--primary-on: #FFFFFF (light) → #1A0B2E (dark)
--danger-on:  #FFFFFF (light) → #2A0B0D (dark)
--success-on / --warning-on / --info-on: likewise
```

Every filled button, badge, avatar, count chip and chart label now uses these.

### `--stage-*` and `--stage-*-text`

Lead-stage and role colours are admin-chosen keys stored in the DB. Each has **two** tokens:
`--stage-teal` (fill: dot, bar, edge — no contrast requirement) and `--stage-teal-text`
(text: AA-safe). Using one value for both is what made `#0E9384` render at 3.8:1 on white.

## 5. Theme switching

`frontend/src/theme.js` is the only place that touches the theme:

- **Resolution**: explicit `localStorage.theme` → else `prefers-color-scheme`.
- **Application**: `data-theme="dark"` on `<html>` (absent = light), plus a live
  `<meta name="theme-color">` update so browser chrome matches.
- **Reactivity**: follows the OS while the user has made no explicit choice; stops following
  the moment they pick one. Syncs across browser tabs via the `storage` event.
- **No flash**: a ~12-line blocking script in `index.html` sets the attribute *before* first
  paint. Verified — `body` background is already `rgb(11,15,25)` on the first frame after reload.
- **Toggle**: `components/ui/ThemeToggle.jsx`, a two-option segmented control in the header
  (☀ / 🌙). Real `<button>`s, `aria-pressed`, `aria-label`, `title`, keyboard-operable.
- **Transition**: 180 ms on `background-color` / `border-color` / `color` only — never layout.
  Disabled under `prefers-reduced-motion`.

## 6. Dark-specific rules (the only five)

Everything else is a token swap. These could not be:

1. `.fin-trend-fill` non-current opacity `.42 → .70` — 42% over a dark ground turned the
   semantic colours olive/brown.
2. `.chart-bar.is-primary` opacity `.75 → .88`, `.ui-wf-fill` `.85 → .92` — same reason.
3. Shadows are near-invisible on dark, so `--shadow-*` become deep blacks and **separation
   is carried by `--border`**; only `--shadow-modal` stays strong.
4. `--surface-sunken` — a container that sits *below* a card. Light `#F2F4F7`, dark `#0B0F19`.
   Without it the kanban column (`--surface-2` `#1B2230`) was *lighter* than its cards
   (`--surface` `#151B28`), inverting the depth order.
5. `[data-theme="dark"] .ui-meter-track` / `.ui-wf-track` → `--viz-track`.

## 7. Components migrated

`BrandLogo` (auto-selects the white lockup in dark), `Badge` (soft fill is now
`color-mix(… , var(--surface))` — it followed the surrounding surface even before, but now
that surface can be dark), `ThemeToggle` (new), Sidebar, Topbar, Buttons, Inputs, Selects,
Tables, Cards, Tabs, Modals, Drawers, Dropdowns, Pagination, Date picker, Search, Charts
(bar/line/waterfall/sparkline/meter/stack), Progress bars, Empty/Error/Skeleton states,
Attendance grid, Kanban, Certificates.

**TeacherDashboard**: verified end-to-end as a teacher in both modes. It had already been
converted from ~101 inline hardcoded style blocks to tokens in an earlier pass, so it needed
no dark-specific work — the metric strip, group cards, stage strips, meters, tabs and
segmented control all adapt.

## 8. Files changed

- `frontend/src/styles.css` — token layer rewritten; overlays, chart tracks, on-colours,
  module tints tokenised.
- `frontend/src/theme.js` — **new**.
- `frontend/src/components/ui/ThemeToggle.jsx` — **new**.
- `frontend/src/main.jsx`, `frontend/index.html` — theme bootstrap.
- `frontend/src/components/ui/BrandLogo.jsx`, `Badge.jsx`, `States.jsx`.
- `frontend/src/components/Topbar.jsx`, `Leads.jsx`, `GroupCertificates.jsx`.
- `frontend/src/constants/domain.js`, `constants/nav.js`.

## 9. Legacy theme code removed

The `light / dark / ocean` system and its 62 `[data-theme]` rule blocks, `ThemeContext.jsx`,
the 3-dot theme selector, and the per-theme sidebar/login overrides were removed in an
earlier pass; this work confirmed none remained (`grep` for `ocean` / `ThemeContext` /
`useTheme` returns only two historical comments). Also removed here: the hardcoded hex in
`Leads.jsx`'s stage palette, `GroupCertificates.jsx`'s chrome, and the last
`color: #fff`-on-fill declarations.

## 10. Known limitations

1. **The certificate page stays light in dark mode — deliberately.** It is a document
   destined for paper, not a screen surface. Its *chrome* (toolbar, stage) follows the theme;
   the A4 sheet does not.
2. **The login brand panel stays purple in both modes.** It is the one place the brand is
   allowed to be loud; the form half switches.
3. **The logo is blue in light mode** (the official asset) and white in dark. There is still
   no purple official variant — see `BRAND_ASSET_INTEGRATION_REPORT.md` §9.
4. **Uploaded photos** (student/staff avatars) are user content and are not dimmed in dark
   mode. They read correctly against `#151B28`, but a bright photo is still bright.
5. **No per-user server-side persistence** — the choice is per-device (`localStorage`), which
   is the usual expectation for a display preference. Making it an account setting would need
   a backend field, which was out of scope.
