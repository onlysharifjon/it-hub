# Tree — joylashuv va vizualizatsiya tuzatishi

Mavjud Tree moduli o'chirilmadi va qaytadan yozilmadi — **joylashuv dvigateli
(layout engine)**, yorliqlash va o'zaro ta'sir tuzatildi. Backend hisob-kitobi
tegilmadi (u allaqachon to'g'ri edi — pastga qarang).

---

## 1. Aniqlangan muammolar

| Muammo | Sabab |
|---|---|
| Chiziqlar tugunlar ustidan kesib o'tardi | Har bir o'tish bitta katta yoy (bezier) bilan chizilardi; yoy kengligi faqat masofaga bog'liq edi, oradagi tugunlar hisobga olinmasdi |
| Yoylar juda ko'p joy egallardi | Bir nuqtadan chiqqan bir necha yoy bir xil kenglikni olardi |
| Yorliqlar tasodifiy joyda | Yorliq yoyning "eng chekka" nuqtasiga qo'yilardi, qo'shnisi bilan to'qnashuvi tekshirilmasdi |
| Foizlar tushunarsiz | "46.2%" yozilardi, lekin nimaga nisbatan ekani hech qayerda aytilmasdi |
| Bosqich % va o'tish % aralashib ketardi | Ikkalasi bir xil ko'rinishda chizilardi |
| Yo'nalish noaniq | Asosiy yo'l ajratilmagan, hamma chiziq bir xil og'irlikda |
| Grafik konteynerdan kengroq | Masshtab moslash yo'q edi — o'ng chekka kesilardi |

---

## 2. Metrikalar — ta'riflar (o'zgarmadi, endi EKRANDA yozilgan)

Backend hisobi tekshirildi va **spec bilan aynan mos** chiqdi, shuning uchun
hisob-kitobga tegilmadi:

| Metrika | Formula | Manba |
|---|---|---|
| **Bosqich %** | `bosqichga yetgan lidlar / kogortadagi jami lidlar` | `main.py:6567` |
| **O'tish %** | `o'tish soni / chiqish bosqichiga yetgan lidlar` | `main.py:6596` |
| **Kogorta** | Tanlangan oyda yaratilgan lidlar (`leads.created_at`) | |
| **Bosqich soni** | Lid o'sha bosqichga **yetib kelganmi** (butun tarix bo'yicha, joriy holati emas) | |
| **O'tish soni** | `lead_activities.action='stage_changed'` yozuvlaridan, lid bo'yicha noyob (from,to) juftliklari | |

**Endi har bir foiz izohlangan:**

- tugunda: `255 lid` / `100% kogortadan`
- chiziqda hover: *"Yangi bosqichiga yetgan lidlardan 127 tasi Keladi ga o'tgan"*
- drawer sarlavhasida: `127 ta lid · 49.8% — Yangi bosqichiga yetgan lidlardan`
- afsona ostida doimiy ta'rif:
  *Tugundagi % — kogortadagi barcha lidlarga nisbatan · Chiziqdagi % —
  chiqish bosqichiga yetgan lidlarga nisbatan*

Izohsiz foiz endi ekranda yo'q.

---

## 3. Yangi joylashuv arxitekturasi

**USTUN + YO'LAK** (column + lane routing) — sxema muharrirlarida
ishlatiladigan klassik usul.

```
   B yo'lagi      MARKAZIY USTUN       A yo'lagi        YON USTUN
   (orqaga)       (asosiy yo'l)        (barcha         (chetki
                                        qolganlari)     bosqichlar)
      │           ┌─────────────┐          │          ┌─────────────┐
      │           │ Yangi  255  │──────────┼─────────→│ Qayta ariza │
      │           └──────┬──────┘          │          └─────────────┘
      │             127 │ 49.8%            │
      │           ┌─────▼───────┐          │          ┌─────────────┐
      └───────────│ Keladi 154  │──────────┼─────────→│ Rad etildi  │
                  └──────┬──────┘          │          └─────────────┘
                       1 │ 0.6%            │
                  ┌─────▼───────┐          │
                  │ To'landi  2 │          │
                  └─────────────┘          │
```

1. **Asosiy yo'l** — eng ko'p lid oqadigan zanjir, DINAMIK topiladi
   (`findMainPath`). Bosqichlar `order` bo'yicha tartiblangani uchun oldinga
   yo'nalgan o'tishlar sikl hosil qilmaydi (DAG) → shu DAG ustida dinamik
   dasturlash bilan eng "og'ir" zanjir topiladi. Imkon bo'lsa zanjir `won`
   bosqichida tugaydi. **Hech qanday bosqich nomi qattiq kodlanmagan.**
2. Asosiy yo'l tugunlari **markaziy ustunga** tik tiziladi (yuqoridan pastga).
3. Qolgan barcha bosqichlar **bitta yon ustunda**.
4. Qo'shni bo'lmagan har bir bog'lanish **yo'lakdan** o'tadi: gorizontal
   chiqadi → yo'lakda tik yuradi → gorizontal kiradi (burchaklari yumaloq).

### Nega kesishish MUMKIN EMAS

Yo'lak — ustunlar orasidagi bo'sh vertikal zona, unda tugun yo'q. Bog'lanishning
oraliq qismida `x` doimo yo'lak `x`iga teng. Ikkala uchi ham (markaz va yon
ustun) shu yo'lakka tegib turadi, shuning uchun **har qanday** bog'lanish
faqat shu zonadan o'tadi. Bu "chamalab yaxshi ko'rinadi" emas — geometrik
kafolat.

> **Ikki yon ustundan voz kechildi.** Dastlab yo'qotishlar o'ngga, qolganlari
> chapga qo'yilgan edi. Chiroyli ko'rinardi, lekin chapdagi tugundan o'ngdagi
> tugunga boradigan bog'lanish (masalan `Qayta qo'ng'iroq → Rad etildi`)
> markaziy ustunni **kesib o'tishga majbur** bo'lardi. Bitta yon ustun bilan
> bunday holat umuman yuzaga kelmaydi.

### Yo'laklarni ulashish

Har bir bog'lanishga alohida yo'lak berilganda 14 ta o'tish 14 ta parallel tik
chiziq hosil qildi — natija "elektron plata"ga o'xshadi. Endi **interval
partitioning**: tik oralig'i kesishmaydigan bog'lanishlar bitta yo'lakni
ulashadi. Avgust uchun 14 yo'lak → 5 yo'lak.

### Yorliqlarni ajratish

Yorliq o'z chizig'ining tik qismida istalgan balandlikda tura oladi. To'qnashuv
aniqlansa, yorliq shu oraliq ichida ikkala yo'nalishda ham siljitiladi; joy
topilmasa — yo'lakdan gorizontal chetga suriladi.

---

## 4. Kichik oqimlar filtri

Avgustda 19 ta o'tishning 8 tasi **1–2 ta liddan** iborat edi. Ular grafikni
chalkashtirardi, lekin hech qanday ma'no bermasdi.

Endi ular yig'ib qo'yiladi va `Kichik oqimlar 8` tugmasi bilan qaytariladi.

- Chegara: `max(2, kogortaning 1%)`.
- Faqat 10 tadan ko'p o'tish bo'lganda ishlaydi.
- **Konversiya (`won`) o'tishlari hech qachon yashirilmaydi** — voronkaning
  butun maqsadi shular.
- Ma'lumot yo'qolmaydi: yashiringanlar soni ko'rsatiladi, bir bosishda
  qaytariladi va **CSV eksportda doim to'liq** bo'ladi.

---

## 5. Kenglikka moslash

Grafik konteynerdan kengroq bo'lsa avtomatik kichraytiriladi
(`ResizeObserver` → `availableWidth` → `scale`). Foydalanuvchi masshtabi shu
ustiga ko'paytiriladi. Endi o'ng chekka kesilmaydi.

---

## 6. Mobil ko'rinish

760px dan tor ekranda grafik o'rniga **soddalashtirilgan tik oqim**
(`TreeMobile.jsx`):

- asosiy yo'l — tik ro'yxat (nom, son, `% kogortadan`);
- oralarida o'q + o'tish soni va foizi;
- chetki tarmoqlar har bosqich ostida yig'ilgan: `Boshqa yo'nalishlar (4)` →
  bosilganda ochiladi, har birida rang chizig'i + `81 lid · 31.8% ·
  To'g'ridan-to'g'ri o'tish`.

Ma'lumot bir xil — faqat taqdimot boshqacha. 375px ekranga to'liq grafikni
siqishga urinilmadi.

---

## 7. O'zgargan fayllar

**Frontend (faqat shular):**

| Fayl | O'zgarish |
|---|---|
| `tree/layout.js` | To'liq qayta yozildi: `findMainPath`, ustun+yo'lak routing, `orthPath`, `spreadLabels`, yo'lak ulashish |
| `tree/ConversionTree.jsx` | Yangi chizish, hover tooltip, kenglikka moslash |
| `tree/TreeNode.jsx` | Tugun tarkibi: `255 lid` / `100% kogortadan`, asosiy yo'l urg'usi |
| `tree/TreeLegend.jsx` | **Yangi** — afsona + foiz ta'riflari |
| `tree/TreeMobile.jsx` | **Yangi** — mobil soddalashtirilgan oqim |
| `tree/TreeDetailPanel.jsx` | Drawer sarlavhasida foiz izohlanadi |
| `components/Tree.jsx` | Kichik oqimlar filtri, `ResizeObserver`, mobil almashinuv |
| `styles.css` | Tree bo'limi qayta yozildi (tooltip, mobil, afsona, tugun) |

**Backend:** o'zgarish **yo'q**. Hisob-kitob tekshirildi va spec bilan mos
chiqdi; boshqa CRM modullariga tegilmadi.

---

## 8. O'tkazilgan testlar

Jonli bazaning izolyatsiya qilingan nusxasida (`preview.db`), headless
Chromium orqali. **Avtomatlashtirilgan geometrik tekshiruv** yozildi: har bir
SVG yo'l bo'ylab 80–500 nuqta olinadi, `getScreenCTM()` bilan ekran
koordinatasiga o'tkaziladi va har bir tugun to'rtburchagi bilan solishtiriladi.

| Test | Iyul (182 lid) | Avgust (255 lid) | Sentabr (11 lid) | Yanvar (0 lid) |
|---|---|---|---|---|
| Tugunlar | 9 | 8 | 4 | bo'sh holat |
| **Chiziq ⨯ tugun kesishishi** | **0 ✓** | **0 ✓** | **0 ✓** | — |
| **Yorliq ⨯ tugun** | **0 ✓** | **0 ✓** | **0 ✓** | — |
| **Yorliq ⨯ yorliq** | **0 ✓** | **0 ✓** | **0 ✓** | — |
| KPI ↔ 1-tugun mosligi | 182 = 182 ✓ | 255 = 255 ✓ | 11 = 11 ✓ | "Lidlar topilmadi" |

Qo'shimcha:

- **To'liq ekran** — butun ekranni qoplaydi (`0,0,1560,1000`), kesishish 0 ✓
- **Mobil (390px)** — 3 bosqich, 2 ta yig'ilgan tarmoq guruhi, ochilganda 4 tarmoq ✓
- **Gorizontal toshish** — 375/390/768/1024/1280/1920px: **yo'q** ✓
- **Tooltip** — *"Yangi bosqichiga yetgan lidlardan 127 tasi Keladi ga o'tgan"* ✓
- **Chiziq bosish** → `Yangi → Keladi · 127 ta lid · 49.8% — Yangi bosqichiga
  yetgan lidlardan` drawer'i, aynan o'sha 127 lid ✓
- **Light va dark** — ikkalasida ham barcha testlar takrorlandi ✓
- **Runtime xatolar** — 0 ✓

### Tuzatilgan test xatosi

Dastlab geometrik tekshiruv "6 ta kesishish" ko'rsatdi. Bu **testning o'z
xatosi** edi: SVG yo'l nuqtalari SVG ichki koordinatasida, tugunlar esa ekran
koordinatasida o'lchanardi — kenglikka moslash `scale()` qo'shilgach ikkalasi
mos kelmay qoldi. `getScreenCTM()` qo'shilgandan keyin natija 0 bo'ldi.

---

## 9. Ma'lum cheklovlar

1. **Asosiy yo'l qisqa bo'lishi mumkin.** Avgustda u atigi 3 tugundan iborat
   (`Yangi → Keladi → To'landi`), chunki jonli ma'lumotda lidlar haqiqatan ham
   bosqichlarni sakrab o'tadi (`Yangi → Keladi` 127 ta, `Yangi → Qayta
   qo'ng'iroq` 81 ta). Bu grafikning kamchiligi emas — **haqiqiy jarayonning
   aksi**. Sun'iy oraliq tugunlar qo'shilmadi.
2. **Yon ustun bitta.** Yo'qotishlar alohida chap/o'ng ustunga bo'linmaydi
   (kesishishning oldini olish uchun). Ular rang (qizil) va afsona orqali
   ajraladi.
3. **Kichik oqimlar sukut bo'yicha yashirin** (10 tadan ko'p o'tish bo'lsa).
   Bu tanlov: to'liq ko'rinish bir bosishda ochiladi, lekin birinchi
   taassurot toza bo'lishi kerak.
4. **Juda ko'p bosqichda (12+) grafik baland bo'ladi** va tik aylantirish
   kerak. Kenglik moslanadi, balandlik esa yo'q — matn o'qilarli qolishi uchun.
5. **Yorliq siljishi ba'zan chiziq o'rtasidan chetga chiqadi** — juda qisqa
   bog'lanishlarda yorliq uchun joy bo'lmasa, u yo'lakdan gorizontal suriladi.
