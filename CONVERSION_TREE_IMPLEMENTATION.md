# Tree — Conversion Flow Analytics

Lid oqimini vizual tahlil qiladigan yangi CRM moduli. Ishlab chiqarishga
joylashtirilgan: `https://crm.minaracademy.uz/#tree`

---

## 1. Nima qilindi

Tree — bosqichlar bo'ylab lidlarning **haqiqiy harakatini** ko'rsatadigan ish
maydoni. Mavjud `Leads → Analitika` "hozir qayerda nechta lid bor" degan
savolga javob beradi; Tree esa boshqasiga: **"lidlar qayerda yo'qoladi va
qaysi yo'l bilan to'lovga yetadi"**.

- Bosqichlar backend'dan dinamik keladi — hech qanday qattiq kodlangan
  voronka yo'q. Admin bosqich qo'shsa/o'chirsa/nomini yoki rangini
  o'zgartirsa, daraxt avtomatik moslashadi.
- Barcha sonlar haqiqiy `leads` va `lead_activities` yozuvlaridan hisoblanadi.
  Hech qanday soxta ma'lumot yoki soxta "AI xulosa" yo'q.

---

## 2. Ma'lumot semantikasi (eng muhim qism)

Uch xil sana aralashib ketmasligi uchun har biri aniq belgilangan:

| Tushuncha | Ta'rif |
|---|---|
| **Kogorta** | Tanlangan **oyda yaratilgan** lidlar (`leads.created_at`). Barcha foizlar shu to'plamga nisbatan. |
| **Tugun (bosqich)** | Kogorta lidlaridan nechtasi shu bosqichga **yetib kelgan** (joriy holati emas, butun tarixi bo'yicha). |
| **O'tish** | Kogorta lidlarining bosqich o'zgarishlari — **vaqtidan qat'i nazar**. 30-avgustda kelgan lid 2-sentyabrda to'lashi mumkin; o'tishni oy chegarasi bilan kessak, konversiya sun'iy ravishda past ko'rinardi. |
| **Konversiya** | Kogortadan nechtasi `kind='won'` bosqichiga **yetib borgan**. Joriy bosqich bo'yicha emas — aks holda daraxtda "To'landi: 2" turib, konversiya 0% ko'rinardi. |
| **Tushum** | Konversiya bo'lgan lidlarga bog'langan talabalarning **haqiqiy to'lovlari** (`payments.amount`). |
| **Konversiya vaqti** | Lid yaratilgan paytdan `won` bosqichiga birinchi o'tish paytigacha (kunlarda). O'rtacha va mediana. |

Oy chegarasi **Toshkent vaqtida** olinadi (bazada vaqtlar naive UTC).

### Lid → Talaba bog'lanishi

Bazada `leads.student_id` maydoni **yo'q**. Bog'lanish ikki manbadan tiklanadi:

1. `converted` faoliyat yozuvidagi `meta_json.student_id` — aniq manba;
2. u bo'lmasa — telefon raqami bo'yicha (`dedup_key`, tizim dublikat izlashda
   ishlatadigan usul).

Ikkalasi ham topilmasa, lid **"studentga o'tkazilmagan"** deb belgilanadi va
sahifada ogohlantirish sifatida chiqadi. Bu taxmin emas — menejment uchun
haqiqiy signal (hozirgi bazada `converted` yozuvlari umuman yo'q, ya'ni
"To'landi" bosqichi hech qachon talaba kartasini yaratmagan).

### Bosqich tarixining nozik joyi

`lead_activities.meta_json` bosqich **nomini** saqlaydi (`{"old":"Yangi","new":"Demo"}`),
ID'sini emas. Shuning uchun:

- mavjud bosqichlar `s<id>` kalitini oladi;
- tarixda uchraydigan, lekin endi mavjud bo'lmagan nomlar `h:<nom>` kalitli
  "arxiv" tuguniga aylanadi va daraxtda `arxiv` belgisi bilan ko'rsatiladi.

Shu tufayli bosqich o'chirilsa ham tarixiy ma'lumot yo'qolmaydi.

---

## 3. Backend

### Yangi endpoint'lar

| Metod | Yo'l | Ruxsat | Vazifa |
|---|---|---|---|
| `GET` | `/leads/conversion-tree?month=&year=` | `require_crm_access` | Daraxt ma'lumoti (tugunlar, o'tishlar, KPI, xulosalar, manba/operator kesimi) |
| `GET` | `/leads/by-ids?ids=1,2,3` | `require_crm_access` | Tanlangan tugun/o'tish lidlarining to'liq kartalari (maks. 200 ta) |

Ikkalasi ham `@app.get("/intake-forms"...)` dan oldin ro'yxatdan o'tgan —
`/leads/{lead_id}` shaklidagi marshrut ularni to'sib qo'ymaydi.

### Ruxsatlar (server tomonda majburlanadi)

- `sales` — faqat o'zi yaratgan lidlar (`created_by_id == actor.id`), javobda
  `scope: "own"`;
- `admin`, `hunter` — operator kesimi to'ldiriladi (`can_see_operators: true`);
- `call_center` — lidlarni ko'radi, operator kesimi **bo'sh** keladi;
- boshqa rollar — `403` (`require_crm_access`).

Frontend hech narsani yashirmaydi — himoya butunlay serverda.

### O'zgargan fayllar

- `backend/main.py` — `lead_conversion_tree()`, `leads_by_ids()`
- `backend/schemas.py` — `TreeStageNode`, `TreeTransition`, `TreeInsight`,
  `TreeSourceStat`, `TreeOperatorStat`, `ConversionTreeRead`

Mavjud endpoint, model yoki biznes-mantiq **o'zgartirilmadi**.

---

## 4. Frontend

| Fayl | Vazifa |
|---|---|
| `src/components/Tree.jsx` | Sahifa: oy/yil boshqaruvi, KPI, maket, export, to'liq ekran |
| `src/components/tree/layout.js` | Geometriya: tugun koordinatalari, egri chiziqlar, yo'laklar, ranglar |
| `src/components/tree/ConversionTree.jsx` | Vizualizatsiya (SVG chiziqlar + HTML tugmalar) |
| `src/components/tree/TreeNode.jsx` | Bosqich tuguni |
| `src/components/tree/TreeDetailPanel.jsx` | O'ng panel: lidlar ro'yxati, qidiruv, statistika |
| `src/components/tree/ConversionPanels.jsx` | Xulosalar, manba va operator jadvallari |
| `src/utils/datetime.js` | Vaqt o'girish (UTC → mahalliy) |

O'zgartirilgan: `src/api.js`, `src/App.jsx`, `src/constants/nav.js`,
`src/styles.css`, `src/components/Leads.jsx` (`LeadDrawer` eksport qilindi).

### Qayta ishlatilgan komponentlar

`KpiCard`, `DataTable`, `EmptyState`, `ErrorState`, `Skeleton`, `CardSkeleton`
va **`LeadDrawer`** — Tree ikkinchi, mustaqil lid-kartasini yozmaydi.
Tahlil ekranida bosqichni o'zgartirish o'chirilgan (`canMove={false}`) —
ko'rsatkichlar ko'z oldida o'zgarib ketmasin; lekin `allowNote` orqali izoh
qoldirish ishlaydi.

### Vizualizatsiya qarorlari

- **Ikki qatlam**: egri chiziqlar — SVG, bosiladigan narsalar — haqiqiy
  `<button>`. Sababi: SVG ichidagi `foreignObject`da klaviatura fokusi va
  mavzu token'lari ishonchsiz ishlaydi.
- **Yo'laklar**: yon tomondan aylanadigan har bir yo'l o'z kengligini oladi
  (uzoq yo'llar tashqarida). Aks holda bir necha egri ustma-ust tushib,
  sonlarni o'qib bo'lmasdi.
- **Chiziq qalinligi** lidlar soniga mutanosib, 2–10px oralig'ida cheklangan.
- **Ranglar semantik**: kulrang — oddiy oqim, binafsha — to'g'ridan-to'g'ri
  sakrash, yashil — konversiya, qizil — yo'qotish, sariq — orqaga qaytish.
- **To'liq ekran** `createPortal` orqali `document.body`ga chiqariladi:
  `.page-anim` sahifa animatsiyasi uchun `transform` qo'llaydi, `transform`
  esa `position: fixed` uchun yangi containing block yaratadi.

---

## 5. UX xatti-harakati

- **Tugun bosilishi** → o'ng panelda o'sha bosqichga yetib kelgan lidlar.
- **Chiziq bosilishi** → aynan o'sha o'tishni bajargan lidlar
  ("Yangi → Rad etildi", 65 ta lid, 25.5%).
- Tanlov paytida bog'liq bo'lmagan tugun/chiziqlar **so'niq** bo'ladi, lekin
  ko'rinib turadi. "Filterni tozalash" tugmasi mavjud.
- **Xulosa kartalari** bosilganda tegishli o'tish/tugun daraxtda tanlanadi.
- Lid bosilganda mavjud `LeadDrawer` ochiladi (izohlar, tarix, qo'ng'iroq).
- **Export** — CSV (`;` ajratgich + BOM, Excel uchun): xulosa, bosqichlar,
  o'tishlar, manbalar, operatorlar.
- **Zoom** 50–160%, tiklash, to'liq ekran (Escape bilan chiqish).

---

## 6. Ish unumdorligi

- Barcha agregatsiya **serverda**. Daraxt javobida faqat ID'lar keladi;
  to'liq lid kartalari foydalanuvchi bosgandan keyin, **100 talik** bo'laklarda
  olinadi (`/leads/by-ids`, maks. 200 ta so'rov boshiga).
- Geometriya `useMemo` ichida — hover/tanlash qayta hisoblamaydi.
- Lid yo'lini tiklash bitta o'tishda (`touched` to'plami) — `visited`
  lug'atini har lid uchun skanerlash O(n²) edi, olib tashlandi.
- Panel qidiruvi 250ms debounce; eskirgan javoblar `reqId` orqali tashlanadi.

---

## 7. Ma'lum cheklovlar

1. **Tushum telefon raqamiga tayanadi.** `converted` yozuvi bo'lmasa, lid
   talabaga `dedup_key` orqali bog'lanadi. Talaba raqami CRM'da boshqacha
   yozilgan bo'lsa, to'lov hisobga olinmaydi. Hozirgi bazada `converted`
   yozuvlari umuman yo'q — shuning uchun tushum 0 ko'rinadi va bu **haqiqiy
   holat**, xato emas (sahifada ogohlantirish sifatida chiqadi).
2. **Boshlang'ich bosqich taxminan tiklanadi.** Lid yaratilganda bosqich
   `meta_json`ga yozilmaydi, shuning uchun u birinchi o'tishning `old`
   qiymatidan olinadi; o'tish bo'lmasa — joriy bosqichdan.
3. **Blok/spam alohida bosqich sifatida yo'q.** Hozirgi voronkada faqat
   `Rad etildi` (`kind='lost'`) bor. Yangi status **o'ylab topilmadi** — admin
   "Blok" nomli bosqich qo'shsa, Tree uni avtomatik ko'rsatadi.
4. **O'ng paneldagi "Statistika" tab'i yuklangan lidlar bo'yicha** hisoblaydi
   (100/200 talik bo'lak). Bu ekranda ochiq yozilgan.
5. **Bosqich nomi o'zgartirilsa**, eski yozuvlar arxiv tuguni sifatida
   ajralib qoladi (tarix ID emas, nom saqlaydi).
