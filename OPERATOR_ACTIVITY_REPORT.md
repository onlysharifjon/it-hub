# Ish markazi + Jamoa faoliyati — QA hisoboti

Sinov muhiti: jonli bazaning **izolyatsiya qilingan nusxasi**
(`preview.db`), backend `127.0.0.1:8099`, statik `127.0.0.1:8098`.
Jonli baza va parollarga tegilmadi; preview paroli faqat nusxada
o'rnatildi, sinovdan keyin muhit o'chirildi.

Brauzer: headless Chromium (Playwright), light va dark.

---

## 1. Navbat haqiqiy ma'lumotdan yig'iladi

`GET /work-center` (jonli nusxa, 2026-09-05):

```
KPI      : jami 202 · bajarildi 0 · qoldi 202 · shoshilinch 44 · kechikkan 156
Turlari  : CALLBACK 167 · PAYMENT_REMINDER 29 · LEAD_CALL 4 · ABSENCE_FOLLOWUP 2
Muhimlik : critical 44 · high 91 · normal 67
```

Namuna yozuvlar (haqiqiy, to'qilmagan):

```
To'lov eslatmasi   Odilov Saidamir    700 000 so'm qarz        guruh P-006
To'lov eslatmasi   Yo'ldoshev Farxod  700 000 so'm qarz        guruh S002
Davomat follow-up  Sharofiddin        4 ta dars ketma-ket      oxirgi 28.08.2026
Davomat follow-up  Xafizov amirbek    2 ta dars ketma-ket      onasi +998934760331
```

Qarz raqamlari moliya bo'limi bilan bir xil manbadan
(`_students_payment_map`) olinadi.

### Tuzatilgan xato — "hammasi qizil"

Dastlabki qoidada har qanday kechikkan callback `critical` edi:

```
critical 153 / high 49 / normal 0        ← ishlatib bo'lmaydi
```

Bazada 150+ ta uzoq muddat oldin kechikkan callback bor. Hammasi qizil
bo'lsa, xodim bugun nima muhimligini ajrata olmaydi (§5). Kechikish
uzunligiga qarab baholash joriy etildi:

```
critical 44 / high 91 / normal 67        ← foydalanish mumkin
```

---

## 2. Funksional sinovlar

| Sinov | Natija |
|---|---|
| Navbat yuklanishi (light/dark) | ✅ 4 KPI, 200 karta, 3 muhimlik bo'limi |
| Muhimlik bo'yicha guruhlash | ✅ Shoshilinch 44 / Muhim 90 / Oddiy 67 |
| Tur bo'yicha filtr | ✅ "To'lov eslatmasi" → 28 karta |
| Muhimlik bo'yicha filtr | ✅ |
| Kechikkan ishlar bloki | ✅ "155 ta" + eng eskisining sanasi |
| Telefon havolasi (`tel:`) | ✅ har kartada, ota va ona raqami alohida |
| **Qo'ng'iroq natijasi oynasi** | ✅ 12 natija + 4 keyingi qadam (16 tugma) |
| Natija saqlanishi | ✅ vazifa `completed`, navbatdan chiqadi |
| "Bugun bajarilgan" ro'yxati | ✅ izoh bilan birga ko'rinadi |
| Kunlik statistika | ✅ qo'ng'iroq / bog'landi / javobsiz / callback / to'lov / davomat |
| Qo'lda vazifa yaratish | ✅ |
| Keyinga surish (vaqt majburiy) | ✅ modal orqali |
| O'tkazib yuborish (tasdiq bilan) | ✅ |
| **Jamoa faoliyati** KPI | ✅ 4 qo'ng'iroq · 100% bog'lanish · 4 bajarilgan |
| Operatorlar jadvali | ✅ 5 qator, saralanadi |
| **Operator drawer** | ✅ 4 timeline yozuvi + bajarilgan vazifalar |
| Jurnal filtrlari | ✅ operator / tur / natija / matn qidiruvi (serverda) |
| Davr tanlash | ✅ Bugun / Kecha / Hafta / Oy / Oraliq |
| Runtime xatolar | ✅ **0** (light va dark) |

Operator drawer'i spec §24 talab qilgan hamma narsani ko'rsatadi:

```
00:36  Xomid            Bog'landim     "QA sinovi — bog'landim, keyingi hafta keladi."   CALLBACK
23:14  Odilov Saidamir  To'lov qiladi  "Onasi bilan gaplashdim, 10-sentabrda to'laydi."
                                        PAYMENT_REMINDER · va'da: yes · sana: 2026-09-10
```

---

## 3. Tuzatilgan xatolar

**1. Sana mintaqasi mos kelmasdi.** Frontend "bugun"ni brauzer mintaqasida
hisoblardi, backend esa sanalarni Toshkent kuni deb tushunadi. UTC'da
ishlaydigan brauzer bir kun oldingi oraliqni so'rab, "Jamoa faoliyati"ni
**bo'sh** ko'rsatardi (0 qo'ng'iroq, 0 operator — aslida 3 tadan). Yechim:
`tashkentToday()` / `shiftDay()`. Endi 4 qo'ng'iroq, 5 operator ko'rinadi.

**2. `prompt()` bilan keyinga surish.** Brauzer oynasi mobil qurilmada
ishonchsiz va mavzuga moslashmaydi. Alohida modal bilan almashtirildi.

**3. Karta tugmalari noto'g'ri o'raldi.** `min-width: 110px` ikonka
tugmalarini ikkinchi qatorga tushirardi. `flex: 1 1 96px` + `.btn-icon
{ flex: none }`.

**4. Admin xodim tanlagichi butun qatorni egallardi.** `.wc-user-pick`
kengligi cheklandi.

**5. "Eng eskisi" noto'g'ri hisoblanardi.** Ro'yxat muhimlik bo'yicha
tartiblangan, oxirgi element eng eski emas. Sana bo'yicha alohida topiladi.

---

## 4. Chegaraviy holatlar

| Holat | Xatti-harakat |
|---|---|
| Vazifa yo'q | "Bugun hammasi bajarilgan" + tushuntirish |
| Filtrga mos vazifa yo'q | "Bu filtrda vazifa yo'q" |
| 200 vazifa | Muhimlik bo'yicha bo'limlarga ajratiladi, sahifa ishlaydi |
| Kechikkan callback (155 ta) | Alohida ogohlantirish bloki |
| Talabada ota/ona telefoni yo'q | `phone1`ga tushadi; bo'sh bo'lsa tugma chiqmaydi |
| Bir vazifa ikki generatordan | `source_key` bo'yicha birinchisi qoladi |
| Bir xil vazifani ikki marta bajarish | `source_key` unique — ikkinchi yozuv yaratilmaydi |
| Bo'sh davr (Jamoa faoliyati) | "Bu davrda faoliyat yo'q" |
| Keyinga surilgan vazifa | Yangi vaqt kelgunicha navbatda ko'rinmaydi |

---

## 5. Ruxsat sinovlari

| Rol | Kutilgan | Holat |
|---|---|---|
| admin | Hammasi + boshqa xodim navbati | ✅ `can_pick_user: true` |
| hunter | O'ziga biriktirilgan + egasiz | ✅ `visible_to()` |
| call_center | Xuddi shunday | ✅ |
| sales | Faqat o'z **lid** vazifalari | ✅ talaba/moliya vazifalari filtrlanadi |
| teacher / audit / support_teacher | 403 | ✅ `require_crm_access` |
| Admin bo'lmagan → `/activities?user_id=X` | O'z yozuvlari | ✅ `user_id` bekor qilinadi |
| Admin bo'lmagan → `/activities/stats` | 403 | ✅ `require_admin` |
| Sales → talabaga qo'ng'iroq yozish | 403 | ✅ kodda tekshiriladi |
| Boshqaning vazifasini o'zgartirish | 403 | ✅ `assigned_to_id` tekshiruvi |

---

## 6. Mavzu va responsive

Light va dark — ikkalasida ham to'liq sinovdan o'tdi. Barcha ranglar mavjud
global token'lardan (`--surface`, `--border`, `--danger`, `--warning`,
`--success`, `--info`, `--primary`). Qattiq kodlangan oq/qora yo'q.

Gorizontal sahifa toshishi: 375 / 768 / 1024 / 1920px — **toshish yo'q**.
≤640px da kartalar bitta ustunga tushadi, tugmalar balandligi 42px
(§47 "no tiny buttons").

---

## 7. Sinovdan o'tmagan / kelajakda

- **1000+ faoliyat yozuvi** sinovdan o'tkazilmadi — jonli bazada hozircha
  bir nechta yozuv bor. Sahifalash mantig'i (50/sahifa, server tomonda)
  ishlaydi, lekin katta hajmda o'lchanmagan.
- **Izoh tahrirlash auditi** — model va ustunlar tayyor (`original_note`,
  `edited_at`), UI qilinmagani uchun oxirigacha sinovdan o'tmadi.
- **Klaviatura bilan to'liq o'tish** qo'lda tekshirilmadi; barcha
  boshqaruvlar haqiqiy `<button>` / `<select>` va `aria-label`ga ega.
- **Bir vaqtda ikki xodim bitta vazifani bajarishi** — `source_key` unique
  bo'lgani uchun ikkinchisi mavjud qatorni yangilaydi, xato bermaydi; lekin
  poyga holati alohida sinovdan o'tkazilmadi.
