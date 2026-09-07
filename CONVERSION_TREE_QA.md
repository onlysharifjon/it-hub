# Tree — QA hisoboti

Sinov muhiti: jonli bazaning **izolyatsiya qilingan nusxasi**
(`preview.db`), backend `127.0.0.1:8099`, statik `127.0.0.1:8098`.
Jonli baza va parollarga tegilmadi; preview paroli faqat nusxada
o'rnatildi va sinovdan keyin muhit to'liq o'chirildi.

Brauzer: headless Chromium (Playwright).

---

## 1. Backend — haqiqiy ma'lumot

`GET /leads/conversion-tree` uch oy uchun tekshirildi:

| Oy | Lidlar | Won | Lost | Ochiq | Konversiya | O'rt. kun | Tugun | O'tish | Xulosa |
|---|---|---|---|---|---|---|---|---|---|
| 2026-07 | 182 | 3 | 135 | 44 | 1.6% | 2.9 | 9 | 30 | 5 |
| 2026-08 | 255 | 2 | 71 | 182 | 0.8% | 0.2 | 8 | 19 | 5 |
| 2026-09 | 11 | 0 | 1 | 10 | 0.0% | — | 4 | 3 | 3 |

Avgust uchun tugun taqsimoti (`ever reached`):

```
Yangi 255 (100%) · Qayta ariza 21 (8.2%) · Qo'ng'iroq qilindi 16 (6.3%)
Qayta qo'ng'iroq 93 (36.5%) · Keladi 154 (60.4%) · Demo 10 (3.9%)
To'landi 2 (0.8%) · Rad etildi 118 (46.3%)
```

Eng yirik o'tishlar: `Yangi → Keladi` 127 (49.8%, skip),
`Yangi → Qayta qo'ng'iroq` 81 (31.8%, skip), `Yangi → Rad etildi` 65 (25.5%, lost),
`Keladi → Qayta qo'ng'iroq` 15 (9.7%, **back**).

O'tish turlari to'g'ri tasniflandi: `normal` / `skip` / `back` / `won` / `lost`.

### Tuzatilgan nomuvofiqlik

Dastlab `won` joriy bosqich bo'yicha sanalardi: daraxtda "To'landi: 2" turib,
konversiya **0%** ko'rinardi. `won` endi "bosqichga yetib borgan" bo'yicha
hisoblanadi — daraxt va KPI bir xil haqiqatni ko'rsatadi.

---

## 2. Funksional sinovlar

| Sinov | Natija |
|---|---|
| Sahifa yuklanishi (light/dark) | ✅ 4 KPI, 3–5 xulosa, 2 jadval |
| Tugunlar chiziladi | ✅ sentabr 4 ta, avgust 8 ta |
| O'tish yorliqlari | ✅ bosiladigan, son + foiz |
| **Tugun bosilishi** | ✅ "Yangi · 11 ta lid · 100%" → panelda 11 lid |
| **Chiziq bosilishi** | ✅ "Yangi → Qayta qo'ng'iroq · 5 ta lid · 45.5% · To'g'ridan-to'g'ri o'tish" → 5 lid |
| Panel qidiruvi | ✅ "mohigul" → 1 ta natija (debounce 250ms) |
| Lid ochilishi | ✅ mavjud `LeadDrawer` ochiladi (yangi nusxa yozilmagan) |
| Oy almashtirish | ✅ avgust → 8 tugun, KPI "255" ga yangilandi |
| Yil almashtirish | ✅ |
| Bo'sh oy (yanvar) | ✅ "Bu oy uchun lidlar topilmadi" — buzilgan konnektor yo'q |
| To'liq ekran | ✅ butun ekranni qoplaydi, Escape bilan yopiladi |
| Zoom / tiklash | ✅ 50–160% |
| Export CSV | ✅ xulosa + bosqichlar + o'tishlar + manbalar + operatorlar |
| Xulosa kartasi bosilishi | ✅ tegishli o'tish daraxtda tanlanadi |
| Runtime xatolar | ✅ **0** (light va dark) |

---

## 3. Tuzatilgan xatolar

**1. To'liq ekran yon panel ostida qolib ketardi va balandligi 0 edi.**
`.page-anim` sahifa animatsiyasi uchun `transform` qo'llaydi; `transform`
`position: fixed` uchun yangi containing block yaratadi, shuning uchun
`inset: 0` butun ekranni emas, kontent sohasini bildirardi
(`x:256, y:56, height:0` — tugunlar chizilgan, lekin kesilgan).
Yechim: `createPortal(…, document.body)`. Tekshirildi: `x:0, y:0, 1440×960`.

**2. Yon egri chiziqlar ustma-ust tushardi.** Egrilik kengligi faqat masofaga
bog'liq edi, shuning uchun 8 bosqichda bir necha yo'l bir xil yo'lakni olib,
sonlar bir-birining ustiga chiqardi. Yechim: har bir yon yo'lga alohida
yo'lak (uzoq yo'llar tashqarida).

**3. `.kc-tag` faqat `.kanban-card` ichida uslublangan edi.** Lid drawer'ida
teglar umuman uslubsiz qolib, `Manba: InstagramYaratdi: Madina FarmonovaTaklif
qilgan: Mirsaid` bo'lib yopishib ketardi. Qoida mustaqil qilindi.

---

## 4. Chegaraviy holatlar

| Holat | Xatti-harakat |
|---|---|
| 0 lid (yanvar) | Bo'sh holat matni, daraxt chizilmaydi |
| 4 tugun (sentabr) | To'g'ri chiziladi |
| 8 tugun + 19 o'tish (avgust) | Yo'laklar ajratilgan, yorliqlar o'qiladi |
| Mavjud bo'lmagan bosqich tarixda | `arxiv` belgili tugun sifatida ko'rsatiladi |
| 255 lid bitta tugunda | ID'lar bilan keladi, 100 talik bo'laklarda yuklanadi |
| Uzun bosqich nomi | `text-overflow: ellipsis` |
| Konversiya yo'q | KPI "—", "hali konversiya yo'q" |
| Tushum 0 | Ogohlantirish: "N ta lid studentga o'tkazilmagan" |

---

## 5. Mavzu (light / dark)

Ikkala mavzuda ham to'liq sinovdan o'tdi. Barcha ranglar mavjud global
token'lardan (`--surface`, `--border`, `--primary`, `--success`, `--danger`,
`--warning`, `--stage-*`). Qattiq kodlangan oq/qora rang yo'q; uchinchi mavzu
yaratilmadi.

---

## 6. Responsive

Gorizontal **sahifa** toshishi tekshirildi: 375, 390, 768, 1024, 1280, 1920px —
**hech birida toshish yo'q**. Faqat vizualizatsiyaning o'zi
(`.tree-scroll`) kerak bo'lganda gorizontal aylanadi.

≤1100px da maket bir ustunga tushadi, o'ng panel daraxt ostiga o'tadi.

---

## 7. Ruxsatlar

| Rol | Kutilgan | Holat |
|---|---|---|
| admin | Barcha lidlar + operator kesimi | ✅ `can_see_operators: true`, `scope: "all"` |
| hunter | Barcha lidlar + operator kesimi | ✅ kod bo'yicha (`can_see_operators`) |
| sales | Faqat o'z lidlari, operator kesimi yo'q | ✅ `scope: "own"`, server filtri |
| call_center | Lidlar, operator kesimi yo'q | ✅ |
| teacher / audit / support_teacher | Kirish yo'q | ✅ `require_crm_access` → 403 |

`/leads/by-ids` ham `sales` uchun `created_by_id` bo'yicha filtrlaydi — ID'ni
qo'lda kiritib boshqa xodimning lidini ochib bo'lmaydi.

---

## 8. Sinovdan o'tmagan / kelajakda

- 1000+ lidli tugun jonli bazada uchramadi (eng kattasi 255). Sahifalash
  mantig'i 100 talik bo'laklar bilan tekshirildi.
- Haqiqiy tushum ko'rsatkichi tekshirilmadi — bazada `converted` yozuvlari yo'q,
  ya'ni hech bir lid rasman talabaga o'tkazilmagan. Kod yo'li (payments
  agregatsiyasi) mavjud, lekin jonli ma'lumot bilan tasdiqlanmagan.
- Klaviatura bilan to'liq o'tish qo'lda tekshirilmadi; tugunlar va yorliqlar
  haqiqiy `<button>` va `aria-label`ga ega.
