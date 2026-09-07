# Ish markazi (Work Center) + qo'ng'iroq faoliyati

Hunter va Call Center uchun kunlik ish navbati, har bir qo'ng'iroq uchun
natija yozuvi va admin uchun jamoa monitoringi.

Ishlab chiqarishda: `#work_center` (Ishlarim) · `#team_activity` (Jamoa faoliyati)

---

## 1. Muammo va yechim

Ilgari hunter "bugun kimga qo'ng'iroq qilaman?" degan savolga javob topish
uchun Talabalar, To'lovlar, Guruhlar va Lidlar bo'limlarini qo'lda kezib
chiqishi kerak edi. Javob esa allaqachon bazada bor edi — kechikkan callback,
ketma-ket darsga kelmagan o'quvchi, qarzdor talaba.

Ish markazi shu ma'lumotni **bitta tartiblangan ro'yxatga** aylantiradi va
har bir qo'ng'iroqdan keyin natijani 3 bosishda yozib olishga imkon beradi.

---

## 2. Arxitektura qarori: vazifalar bazada saqlanmaydi

Generatorlar har so'rovda CRM ma'lumotidan vazifalarni **qayta hisoblaydi**.
`work_tasks` jadvalida faqat xodim **bir narsa qilgan** vazifa qatori paydo
bo'ladi (bajarildi / surildi / o'tkazib yuborildi) va qo'lda yaratilgan
vazifalar.

Sabab: agar generator har safar qator yozganida, bir necha kunda o'n minglab
keraksiz qator to'planardi va "bir xil to'lov eslatmasi soatiga 5 marta chiqdi"
muammosi paydo bo'lardi.

**Dublikatga qarshi himoya — deterministik `source_key`:**

```
payment:student:123:2026-09        bitta talaba + bitta oy   = bitta vazifa
absence:student:123:2026-09-02     bitta talaba + oxirgi qoldirilgan dars
lead_callback:lead:88:2026-09-05   bitta lid + callback kuni
reminder:412                       mavjud eslatma
lead_new:lead:91                   hali tegilmagan yangi lid
```

Kalit o'zgarmasa, vazifa ham o'zgarmaydi — necha marta so'ralishidan qat'i
nazar. Bu §16 (recurring work) talabini ma'lumotlar darajasida hal qiladi.

---

## 3. Vazifa generatorlari

`backend/work_center.py`

| Generator | Manba | Vazifa turi |
|---|---|---|
| `_gen_lead_callbacks` | `leads.callback_at` ≤ bugun oxiri, yopilmagan bosqich | `CALLBACK` |
| `_gen_reminders` | mavjud `reminders` (pending, muddati kelgan) | `CALLBACK` |
| `_gen_new_leads` | birinchi bosqichdagi, 2 soatdan beri tegilmagan lidlar | `LEAD_CALL` |
| `_gen_absences` | `attendance` — ketma-ket `is_present=False` | `ABSENCE_FOLLOWUP` |
| `_gen_debtors` | `_students_payment_map` — joriy oy qarzi | `PAYMENT_REMINDER` |

Yangi tur qo'shish uchun bitta generator funksiyasi yozib, `generate()`ga
qo'shish kifoya — qolgan hamma narsa (ko'rinish, holat, statistika) ishlaydi.

### Muhimlik qoidalari

Kechikkan callback **kechikish uzunligiga** qarab baholanadi:

| Kechikish | Daraja |
|---|---|
| hali kelmagan (bugun) | `high` |
| ≤ 2 kun | `critical` |
| 3–14 kun | `high` |
| > 14 kun | `normal` — eski qoldiq |

> Bu qoida QA paytida tuzatildi: dastlab har qanday kechikish `critical` edi
> va jonli bazada **202 vazifadan 153 tasi qizil** bo'lib chiqdi. Hammasi
> shoshilinch bo'lsa, hech nima shoshilinch emas (§5). Hozirgi taqsimot:
> 44 critical / 91 high / 67 normal.

Davomat: 2 dars → `high`, 3+ dars → `critical`.
Qarz: oyning kuniga qarab — 15-kundan keyin `critical`, 5-kundan `high`.

### Qarz hisobi qayta yozilmadi

Qarz `_students_payment_map` orqali olinadi — moliya bo'limidagi **aynan o'sha**
mantiq (ta'til, Special chegirma, avans balansi hammasi hisobga olinadi).
Ikkinchi hisoblash yozilmadi: ikki manba ikki xil raqam bersa, xodim qaysiga
ishonishni bilmay qolardi.

---

## 4. Baza o'zgarishlari

Ikkita **yangi** jadval. Mavjud jadval, ustun yoki ma'lumot o'zgartirilmadi.

### `call_activities` — qo'ng'iroq tarixi

`user_id`, `entity_type` (lead|student), `entity_id`, `entity_name`, `phone`,
`source_key`, `task_type`, `outcome`, `note`, `next_action`, `next_action_at`,
`duration_sec`, `state_before`, `state_after`, `payment_promise`,
`promised_at`, `created_at`, `edited_at`, `edited_by_id`, `original_note`.

Yozuv **o'chirilmaydi va ustiga yozilmaydi**: izoh tahrirlansa asl matn
`original_note`da qoladi (§27).

### `work_tasks` — vazifa holati

`source_key` (unique), `task_type`, `assigned_to_id`, `entity_type/id`,
`title`, `reason`, `priority`, `status`, `due_at`, `postponed_to`,
`completed_at`, `completed_by_id`, `outcome`, `note`, `is_manual`.

Holatlar: `new · in_progress · completed · skipped · postponed · cancelled`.
`postponed` uchun yangi vaqt **majburiy** (§17).

**Yaratish:** `backend/scripts/create_work_center_tables.py` — faqat qo'shadi,
idempotent, mavjud ma'lumotga tegmaydi. Ishlab chiqarishda bajarildi.

---

## 5. Endpoint'lar

| Metod | Yo'l | Ruxsat |
|---|---|---|
| `GET` | `/work-center?user_id=` | crm_access (`user_id` faqat admin) |
| `POST` | `/work-center/tasks` | crm_access |
| `PATCH` | `/work-center/tasks?source_key=` | crm_access (o'z vazifasi yoki admin) |
| `POST` | `/activities/call` | crm_access |
| `GET` | `/activities` | crm_access (admin — hammasi, boshqalar — faqat o'zi) |
| `GET` | `/activities/stats` | **admin** |
| `GET` | `/activities/operators/{id}` | **admin** |

Mavjud endpoint'lar o'zgartirilmadi.

### Qo'ng'iroq natijasi mavjud tizimlarga qanday ulanadi

1. `call_activities`ga yozuv (kanonik manba, operator tahlili uchun);
2. lid bo'lsa — `lead_activities`ga ham `action='call'` yozuvi, shunda lid
   kartasidagi **mavjud** tarix ikkiga bo'linib ketmaydi (§39);
3. "Keyingi qadam: qayta qo'ng'iroq" tanlansa — mavjud `reminders` tizimida
   eslatma;
4. `source_key` berilgan bo'lsa — vazifa `completed` holatiga o'tadi.

### Bosqich AVTOMATIK o'zgarmaydi

Natija "Qiziqdi" bo'lsa ham tizim lid bosqichini o'zi ko'chirmaydi (§18).
Sabab: qo'ng'iroq natijasi — xodimning bahosi, bosqich esa hisobot va
referral/maosh hisob-kitobiga ta'sir qiladigan rasmiy holat. Foydalanuvchiga
buni lid kartasida o'zi qilishi eslatiladi.

---

## 6. Ruxsatlar (server tomonda majburlanadi)

| Rol | Ko'radi |
|---|---|
| **admin** | Hamma vazifa, hamma operator, hamma qo'ng'iroq; boshqa xodim navbatini ochishi mumkin |
| **hunter** | O'ziga biriktirilgan + egasiz (umumiy havza) vazifalar; faqat o'z qo'ng'iroqlari |
| **call_center** | Xuddi shunday |
| **sales** | Faqat **o'z lid** vazifalari — talaba/moliya vazifalari ko'rinmaydi |
| teacher / audit / support_teacher | Kirish yo'q (`require_crm_access` → 403) |

`GET /activities` da admin bo'lmagan foydalanuvchi uchun `user_id` parametri
**bekor qilinadi** — boshqa operator yozuvlarini so'rab bo'lmaydi.
`/activities/stats` va `/activities/operators/{id}` — `require_admin`.

---

## 7. Frontend

| Fayl | Vazifa |
|---|---|
| `src/components/WorkCenter.jsx` | "Ishlarim" — navbat, KPI, filtrlar, kunlik natija |
| `src/components/work/CallOutcomeDialog.jsx` | Qo'ng'iroq natijasi oynasi |
| `src/components/TeamActivity.jsx` | "Jamoa faoliyati" — admin monitoringi |
| `src/utils/datetime.js` | `tashkentToday`, `shiftDay` (davr chegaralari) |

O'zgartirilgan: `api.js`, `App.jsx`, `constants/nav.js`, `styles.css`.

Qayta ishlatilgan: `KpiCard`, `DataTable`, `Modal`, `Drawer`, `Field`,
`States`, `useConfirm`, `ConversionInsights` (Tree modulidan).

### Qo'ng'iroq natijasi oynasi

Majburiy maydon **bitta**: natija (12 ta variant). Izoh, keyingi qadam va
vaqt ixtiyoriy. To'lov vazifasida qo'shimcha "To'lov va'da qilindimi?"
(Ha / Yo'q / Qisman / Noma'lum) + va'da sanasi chiqadi (§14).

Sabab: xodim kuniga 40+ qo'ng'iroq qiladi. Uzun forma bo'lsa hech kim
yozmaydi — aynan shu sabab ilgari izohlar deyarli bo'sh edi.

---

## 8. Sana semantikasi

Backend sana filtrlarini **doim Toshkent kuni** deb tushunadi
(`_wc_day_bounds`), chunki bazada vaqtlar naive UTC saqlanadi.

Frontend ham `tashkentToday()` ishlatadi — brauzer mintaqasi emas. Bu QA
paytida topilgan xato edi: UTC'da ishlaydigan brauzer bir kun oldingi
oraliqni so'rab, "Jamoa faoliyati"ni **bo'sh** ko'rsatardi. Endi admin
boshqa mintaqadan kirsa ham ikkala tomon bir xil kunni ko'radi.

---

## 9. Ish unumdorligi

- Jurnal (`/activities`) — serverda filtrlanadi va sahifalanadi (50/sahifa).
  Butun tarix brauzerga yuklanmaydi.
- Qidiruv 300ms debounce.
- Navbat generatsiyasi jonli bazada (690 lid, 44 jadval) **~0.4s**.
- Yangi lidlar generatori 200 ta bilan cheklangan, davomat oynasi 45 kun.

---

## 10. Ma'lum cheklovlar

1. **Qo'ng'iroq davomiyligi qo'lda kiritiladi.** Telefoniya integratsiyasi
   yo'q — audio yozib olish qasddan amalga oshirilmadi (§51). Faqat CRM
   metama'lumoti saqlanadi.
2. **Talaba vazifalari umumiy havzada.** Talabaning "egasi" yo'q, shuning
   uchun to'lov/davomat vazifalari barcha hunter va call_center xodimlariga
   ko'rinadi. Kim birinchi bajarsa, boshqalarda yopiladi.
3. **Kalendar ko'rinishi qilinmadi** (§33) — bu davrda "Bugun" ro'yxati va
   "Jamoa faoliyati" jurnali yetarli deb baholandi; kalendar keyingi bosqich.
4. **Izoh tahrirlash UI'si yo'q.** Baza va model tayyor (`original_note`,
   `edited_at`, `edited_by_id`), lekin tahrirlash ekrani qilinmadi — hozircha
   yozuvlar faqat qo'shiladi.
5. **Bildirishnomalar** mavjud `Notification` tizimidan foydalanmaydi; navbat
   sahifa ochilganda yangilanadi (§34 qisman).
6. **Davomat chegaralari kodda** (`ABSENCE_THRESHOLDS`) — sozlash ekrani yo'q.
