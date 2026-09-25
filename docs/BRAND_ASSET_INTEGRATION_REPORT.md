# Brand Asset Integration — Minar Academy LMS

**Status:** live on `crm.minaracademy.uz`
**Source masters:** `data/Untitled-1-01.png` … `Untitled-1-08.png` (8 files, all 4500×4500 RGBA)
**Companion docs:** `CRM_DESIGN_SYSTEM_V3.md`, `CRM_REDESIGN_PROGRESS.md`

---

## 1. Asset inventory — what was actually in `data/`

Every file was opened, measured, alpha-analysed and colour-sampled. They are **not** variations
of one image; they are five different artworks across three background treatments.

| File | Content | Background | Alpha | Ratio (content) | Verdict |
|---|---|---|---|---|---|
| `Untitled-1-01.png` | Mark only, white | Solid brand blue `#2961FF`, full bleed | Opaque | 1:1 | **App icon / favicon.** Also the reference for the white mark. |
| `Untitled-1-02.png` | Mark only, white + glow | Black ornamental pattern | Opaque | 1:1 | Decorative dark-social artwork. Not UI-usable. |
| `Untitled-1-03.png` | Mark only, blue | Off-white ornamental pattern | Opaque | 1:1 | Decorative light artwork. Not UI-usable (patterned rectangle). |
| `Untitled-1-04.png` | **Stacked lockup** — mark above "Minar Academy" | **Transparent** | Real (content 3266×2235) | 1.461 | **Master** for stacked lockup *and* for the isolated mark. |
| `Untitled-1-05.png` | **Horizontal lockup** — mark + "Minar Academy" | **Transparent** | Real (content 3204×776) | 4.124 | **Primary master.** The main brand asset. |
| `Untitled-1-06.png` | Mark only, white + green glow | Black | Opaque | 1:1 | Decorative dark artwork. Not UI-usable. |
| `Untitled-1-07.png` | Horizontal lockup, **white** | Blue→green gradient, full bleed | Opaque | 1:1 | Proves a white lockup is an **official variant**; the gradient square itself is a social/OG card. |
| `Untitled-1-08.png` | Mark only, white | Solid brand green `#20CE94`, full bleed | Opaque | 1:1 | Alternate-colour app icon. Held in reserve. |

**Brand colours read from pixels:** blue `#2961FF` (primary), green `#20CE94` (secondary).

> **Important consequence.** The official logo is **blue**, while the product UI (per the v3
> design brief) is **purple**. The logo was not recoloured. Instead the rule is: *the logo always
> sits on a neutral or brand-owned surface, never directly against a purple fill.* That is why
> the sidebar brand block is separated by its own border, the login mark uses the white variant
> on the purple field, and no purple control ever touches the logo.

---

## 2. Derived production assets

The 4500×4500 masters are unusable directly (128–700 KB each for a 24 px slot). A web/print set
was produced in `frontend/public/brand/` by **trimming, cropping and downscaling the official
artwork** — no redrawing, no hue changes.

| File | Size | From | Purpose |
|---|---|---|---|
| `minar-logo-full.png` / `@2x` | 1200×291 / 2400×582 | 05, trimmed | Primary horizontal lockup |
| `minar-logo-full-white.png` / `@2x` | 1200×291 / 2400×582 | 05 alpha, official white variant (07) | Lockup for dark/coloured surfaces |
| `minar-logo-stack.png` | 900×616 | 04, trimmed | Stacked lockup (near-square slots) |
| `minar-logo-stack-white.png` | 900×616 | 04 alpha | Stacked, dark surfaces |
| `minar-mark.png` / `@2x` | 512×512 / 1024×1024 | 04, mark region cropped | Mark for tight space |
| `minar-mark-white.png` / `@2x` | 512×512 / 1024×1024 | same mask, white | Mark on dark surfaces |
| `minar-icon-32/180/192/512.png` | square | 01, as-is | Favicon, apple-touch, PWA |
| `minar-logo-print.png` | 3200×775 | 05 | Certificates / print |

Two production details worth recording:

- The **white variants share the blue variants' alpha mask**, so blue and white are
  pixel-identical in geometry. Keying the white lockup out of 07's gradient was tried first and
  rejected — the gradient produced edge artefacts.
- **`@2x` is exactly 2× the `1x` dimensions.** Rounding them independently gave 291 vs 290.5 → a
  1 px ratio mismatch between the two sources of the same `srcset`.

---

## 3. Selection per context

| Context | Asset | Why |
|---|---|---|
| Login — brand panel (desktop) | `full` / **white**, 30 px | Panel is a deep purple field; the blue lockup would lose contrast. White is an official variant. |
| Login — above form (mobile ≤768) | `full` / brand, 30 px, centred | The brand panel is hidden on mobile, which previously left the login **unbranded**. |
| Sidebar — expanded | `full` / brand, 24 px | 256 px panel has room for the wordmark. Left-aligned with the nav. |
| Sidebar — rail (64 px) | `mark` / brand, 32 px, centred | A 4.1:1 lockup squeezed into 64 px is unreadable. Switched by **variant**, never by CSS scaling. |
| Sidebar — mobile drawer (272 px) | `full` / brand | Room exists; drawer is the only brand surface on mobile. |
| Topbar — desktop | *none* | The sidebar already carries the brand. Repeating it is clutter. |
| Topbar — mobile ≤768 | `mark` / brand, 32 px | The sidebar is off-canvas, so this is the only persistent brand cue. |
| Public intake form | `full` / brand, 38 px, centred + divider | Externally-facing page; strongest asset, most space, most polish. |
| Certificates (screen + print) | `print`, 58 px CSS from a 3200 px master (≈13× oversampled) | Formal document. Replaces a hand-drawn SVG + typographic "Minar / Academy". |
| Empty states | `mark`, 92 px @ 4.5 % opacity, behind the icon | Brand *texture*, not a message. Suppressed in `compact` states. |
| Favicon / apple-touch / PWA | `minar-icon-*` (01) | A horizontal lockup is illegible at 32 px; 01 is already a full-bleed icon. |
| Loading states | *none* | Skeletons stay neutral — a branded splash on every fetch is noise. |
| Dashboard | *none* | Business data only, per the design system. |

---

## 4. New components and configuration

**`frontend/src/constants/brand.js`** — single source of truth: asset paths, exact aspect ratios,
icon set, official brand name/colours, the size scale, and a cache-busting version token.

**`frontend/src/components/ui/BrandLogo.jsx`** — the only way a logo enters the UI.

```jsx
<BrandLogo variant="full|stack|mark|print" tone="brand|white"
           size="xs|sm|md|lg|xl|hero"  // or height={30}
           decorative />               // renders alt="" + aria-hidden
```

Guarantees enforced by the component, not by call sites:

- **sized by height**, width computed from the asset ratio → distortion is structurally impossible;
- `width`/`height` attributes emitted → no layout shift while loading;
- `object-fit: contain` as a second line of defence — never `cover`;
- `srcset` 1x/2x on the variants that have it;
- `alt="Minar Academy"` by default, `alt="" aria-hidden` when `decorative`.

---

## 5. Legacy brand usage removed

| Removed | Where it was | Replacement |
|---|---|---|
| `MinaretLogo.jsx` — a hand-drawn 8-point-star SVG, **purple**, an approximation of the real mark | Sidebar, Login, PublicIntake | `<BrandLogo>` with the real artwork. File deleted. |
| `--logo-star-a/b/c`, `--logo-cent-a/b` CSS tokens | `styles.css` `:root` | Replaced with `--brand-blue` / `--brand-green` (documented as logo-only). |
| `.lp-logo-icon` — a text badge reading "IT" + the word "Hub" | Login | Real lockup. (The product had been showing the **wrong brand name**.) |
| `<div className="name"><b>Minar</b><span>Academy</span></div>` — text imitating a wordmark | Certificate header | Official print lockup. |
| `.brand-text` / `.brand-name` / `.brand-sub` — "Minar Academy" typed beside the mark | Sidebar | Removed: the wordmark is already inside the lockup. |
| `MinarWatermark.jsx` (removed in the prior v3 pass) | App shell background | Not reinstated — the brief explicitly rules out a dashboard watermark. |

Verified by grep: no `.png`/`.svg`/`url()`/base64 logo path exists in any component; the only
module that names a brand file is `constants/brand.js`.

---

## 6. Responsive behaviour

| Width | Login | Sidebar | Topbar |
|---|---|---|---|
| ≥1024 | white lockup, brand panel | full lockup (or mark in rail) | none |
| 768–1023 | white lockup | full lockup / mark in rail | none |
| ≤768 | **brand lockup above the form** | full lockup inside the drawer | **mark** |

Measured at 375 / 390 / 768 / 1024 / 1280 / 1440 / 1920 in headless Chromium:
aspect ratio preserved at every width (rendered ratio vs natural ratio within 0.02), no
horizontal overflow, no failed asset requests, no console or page errors on any of the 24 screens.

---

## 7. Performance and caching

- Only the needed variant loads per context; the rail/expanded switch swaps `src`, it does not
  load both. Largest UI asset is 52 KB (`minar-logo-full.png`); the 3200 px print asset (141 KB)
  loads only inside the certificate view.
- No base64, no duplicated requests, no full-size master shipped to the browser.
- nginx serves `/brand/*.png` with `Cache-Control: immutable, 1 year`, and the filenames are not
  content-hashed — so `constants/brand.js` appends `?v=1`. **Bump `V` when an asset changes.**
- `/site.webmanifest` now serves as `application/manifest+json` (it was `application/octet-stream`,
  which some browsers ignore). This is the only server-config change made.

---

## 8. Accessibility

- Meaningful logos: `alt="Minar Academy"` from `BRAND_NAME`.
- Decorative logos (empty-state watermark): `alt=""` + `aria-hidden="true"`.
- The sidebar no longer duplicates "Minar Academy" as text next to the lockup, so screen readers
  hear the brand once per view, not twice.
- Document title corrected from "O'quv metodikasi" to **Minar Academy LMS**.

---

## 9. Remaining limitations

1. **No vector master.** Everything derives from 4500×4500 rasters. The set is oversampled enough
   for screen and A4 print, but an SVG/EPS from the brand owner would be strictly better —
   especially for the certificate, which is currently the one place a raster is scaled into print.
2. **Brand hue vs product hue.** The logo is blue `#2961FF`; the UI system is purple. This is
   managed by isolation, not resolved. If the academy adopts purple as the brand, a purple
   lockup should come from the brand owner — it must not be recoloured in code.
3. **Certificate ornaments remain hand-drawn SVG** (corner stars, medal disc, background
   watermark). They are decorative pattern work rather than the logo, and vector is correct for
   print, so they were deliberately left alone. Only the identity block was swapped.
4. **The green icon variant (08) is unused.** Kept in `data/` as a reserve for an alternate app
   icon; not wired up, since two app icons would be a brand-consistency problem.
5. **No OG/social image.** `Untitled-1-07.png` is exactly that asset, but the CRM is
   `noindex, nofollow` and unlinked publicly, so it was not added.
