# Minar Academy — Ota-ona mobil API (Parent API)

Flutter ilovasi bilan shartnoma. Kod: `backend/parent/`. Testlar: `backend/tests/test_parent.py`.
OpenAPI: [`openapi.yaml`](openapi.yaml). So'rovlar to'plami: [`parent-api.http`](parent-api.http).
Mobil ilova versiyasi va texnik ko'rik: [`release-control.md`](release-control.md).

Base URL: `https://crm.minaracademy.uz/api` (nginx `/api` prefiksini olib, `crm-api`ga uzatadi).

## 1. Umumiy qoidalar (barcha endpointlar)

| Qoida | Amalda |
|---|---|
| Javob shakli | Xom JSON: ro'yxat — `[...]`, obyekt — `{...}`. `data`/`results` o'rami yo'q. |
| Bo'sh ro'yxat | `200 []` |
| Sahifalash | Yo'q. Hech bir ro'yxat yashirin qisqartirilmaydi (oldingi `limit 50/100` olib tashlandi). Katta hajm uchun pagination — mobil bilan kelishiladigan alohida kengaytma. |
| ID | Integer, endpointlar orasida bir xil. |
| Pul | Butun JSON integer, so'm. |
| Sana | `YYYY-MM-DD` (Toshkent kalendari). |
| Vaqt | ISO-8601 `+05:00` (`2026-10-05T10:30:00+05:00`). Bazada naive UTC, global encoder offset qo'shadi. |
| Nullable | Faqat hujjatda belgilanganlar: `children[].start_date`, `children[].avatar`, `recent_payments[].notes`, `recent_payments[].group_name`, `attendance.records[].group_name`, `schedule[].room`. Qolgan string maydonlar ma'lumot yo'q bo'lsa `""`, sonlar `0`. |
| Til | `Accept-Language` talab qilinmaydi; server matnlari (title/body/comment) tarjima qilinmaydi. |
| CORS | `CORS_ORIGINS` env (vergul bilan). Flutter **web** build ishlatilsa, uning origin'ini shu ro'yxatga qo'shing. Metod va header'lar (Authorization, Content-Type) ochiq. |
| request_id | Har javobda `X-Request-ID` header; xato tanasida `request_id`. nginx yuborgan `X-Request-ID` (8–64 xavfsiz belgi) qabul qilinadi. |

### Xato formati (faqat `/parent/*`)

```json
{"code": "validation_error", "message": "So'rov ma'lumotlari noto'g'ri.",
 "errors": {"amount": ["Musbat butun son kiriting."]}, "request_id": "4f0c…"}
```

`errors` doim obyekt (bo'sh bo'lishi mumkin). CRM endpointlari avvalgidek FastAPI standart formatida qoladi.

| Status | Qachon | `code` misollari |
|---|---|---|
| 400 | Buzilgan JSON | `invalid_json` |
| 401 | Login xato, token yo'q/yaroqsiz/eskirgan | `invalid_credentials`, `unauthorized`, `invalid_token`, `token_expired`, `token_reuse` |
| 403 | Begona bildirishnoma; muddati o'tgan sertifikat havolasi | `forbidden`, `link_expired` |
| 404 | Bola bog'lanmagan/yo'q, guruh begona, o'qituvchi biriktirilmagan | `child_not_found`, `group_not_found`, `not_found`, `teacher_not_assigned` |
| 422 | Maydon validatsiyasi | `validation_error`, `invalid_amount`, `nothing_to_pay` |
| 429 | Rate limit (`Retry-After: 60`) | `rate_limited` |
| 426 | Ilova buildi minimal builddan eski | `upgrade_required` |
| 500 | Kutilmagan xato (stack trace faqat server logida) | `internal_error` |
| 503 | Baza vaqtincha ishlamaydi (`Retry-After: 30`); texnik ko'rik (`Retry-After: 120`); to'lov provayderi sozlanmagan | `service_unavailable`, `maintenance`, `payment_provider_unavailable` |

**Bola bo'yicha ruxsat**: har bir `/children/{childId}/…` endpointida token → parent → `parent_children` bog'lami
qayta tekshiriladi (`deps.get_owned_child`). Begona yoki mavjud bo'lmagan bola — bir xil **404**
(`child_not_found`), shunda boshqa oilalar bolalarining ID'larini terib aniqlab bo'lmaydi. Bildirishnomalar uchun
shartnoma bo'yicha begona — **403**, mavjud emas — **404**.

## 2. Autentifikatsiya

* **Login** `POST /parent/auth/login` `{username, password}` → `{access_token, refresh_token}`.
  * `username` — telefon har qanday formatda (`+998901234567`, `+998 90 123 45 67`, `901234567`) yoki
    akkaunt login'i. Avval aniq login, keyin telefonning oxirgi 9 raqami bo'yicha qidiriladi; bir nechta akkaunt
    mos kelsa — hech biri tanlanmaydi (401).
  * Parol trim qilinmaydi. Akkaunt yo'q / parol xato / akkaunt nofaol — bir xil `401 invalid_credentials`
    (topilmasa ham bcrypt ishlaydi — javob vaqtidan bilib bo'lmaydi).
  * Rate limit: IP bo'yicha 15/min, login+IP 6/min, login 30/min (Redis bo'lsa — barcha konteynerlar uchun umumiy).
  * Xodim JWT'si (`role` claim'i `parent` emas) parent endpointlarida 401.
* **Refresh** `POST /parent/auth/refresh` `{refresh_token}` → yangi juftlik. Rate limit: IP bo'yicha 60/min.
  * Refresh token — tasodifiy 64 belgili opaque satr, bazada faqat SHA-256 hash.
  * **Rotation**: har refresh eski tokenni atomik (`UPDATE … WHERE revoked_at IS NULL`) bekor qiladi va yangisini beradi.
    Parallel ikki so'rovdan faqat bittasi yutadi.
  * **Qayta ishlatish**: bekor qilingan token `PARENT_REFRESH_REUSE_GRACE_SEC` (10 s) ichida kelsa — faqat 401
    (tarmoq qayta urinishi); keyin kelsa — o'g'irlik deb, ota-onaning **barcha** refresh tokenlari bekor (`token_reuse`).
  * Eskirgan/bekor/noma'lum token, nofaol akkaunt — 401. Baza ishlamasa — 503 (401 emas).
* **TTL**: access `PARENT_ACCESS_TTL_MIN` (30 daqiqa), refresh `PARENT_REFRESH_TTL_DAYS` (30 kun). JWT kaliti — `SECRET_KEY` env.
* **Revoke**: admin parolni tiklasa (`POST /parents/{id}/reset-password`) barcha refresh tokenlar bekor bo'ladi;
  ota-ona nofaol qilinsa keyingi so'rovdayoq 401. Allaqachon berilgan access token muddati (≤30 daq.) tugaguncha
  amal qiladi — buni kamaytirish uchun TTL'ni qisqartiring.

## 3. Endpointlar bo'yicha qarorlar

| # | Endpoint | Qaror / mapping |
|---|---|---|
| 03 | `GET /parent/profile` | `display_name` = `parents.display_name`, bo'sh bo'lsa `full_name`. `phone` E.164 (`+998901234567`). Avatar qaytarilmaydi. |
| 04 | `PATCH /parent/profile` | **204**. Faqat yuborilgan maydonlar. `display_name` trim → 1–100 belgi. Noma'lum maydon (`phone`, `role`, `child_ids` …) → 422. `avatar_base64`: JPEG/PNG/WEBP (magic bytes), ≤ 2 MB, `data:` prefiksi ixtiyoriy; `""` — o'chirish; boshqa narsa → 422. Saqlash: `parents.avatar` (tekshirilgan toza base64). |
| 05 | `GET /parent/children` | Tartib: ism bo'yicha. **Asosiy guruh** — hozirgi faol a'zoliklar ichida eng birinchi qo'shilgani (`joined_at`, keyin `group_students.id`). `stage` — guruh bosqichi (`Frontend`). `schedule` — `Du · Chor · Ju, 14:00`. `tariff` — barcha faol guruhlar xom oylik narxi yig'indisi (a'zolik tarifi, bo'lmasa guruh narxi). `discount_percent` — joriy oyda amaldagi Special chegirmalar xom narxdan necha foiz (0–100, butun). `start_date` — asosiy guruhga qo'shilgan sana va guruh boshlanishining kechrog'i. `avatar` — talaba rasmi uchun imzolangan HTTPS URL (12+ soat amal qiladi) yoki `null`. |
| 06 | `payment-summary` | 4-bo'limga qarang. `month` (1–12) va `year` (2020…joriy+1) **majburiy**. |
| 07 | `POST …/pay` | 5-bo'limga qarang. |
| 08 | `attendance` | Faqat belgilangan (`is_present` true/false) **va bugungacha** bo'lgan darslar; belgilanmagan (`NULL`) va kelajakdagi yozuvlar qaytarilmaydi. Har dars (guruh+sana) alohida yozuv. `percent = round(present / len(records) * 100)`. CRM'da faqat keldi/kelmadi/belgilanmagan holatlari bor (late/excused yo'q). |
| 09 | `schedule` | Barcha faol guruhlar slotlari, `(day_of_week, start_time)` bo'yicha. Manba — `schedule_slots`; ular kiritilmagan guruh uchun `groups.schedule` matni ("Toq/Juft kunlar", "Du, Chor, Ju") + `lesson_time`, tugash vaqti = boshlanish + `PARENT_DEFAULT_LESSON_MINUTES` (120). `lesson_time` noma'lum bo'lsa slot qaytarilmaydi (HH:mm shartnomasi buzilmasin). Bir martalik ko'chirish/bayram/bekor qilish **yo'q** (kengaytma). |
| 10 | `notifications` | Barchasi, `created_at` kamayish tartibida. Har ota-ona uchun alohida qator (o'qilganlik ham alohida). Noma'lum `type` → `announcement`. Yaratuvchi CRM hodisalari: to'lov qo'shildi, onlayn to'lov tasdiqlandi/qaytarildi (`payment`); darsga kelmadi (`attendance`, faqat holat yangi "kelmadi"ga o'zgarganda); baho, izoh, sertifikat, coin (`announcement`); `/parents/broadcast`. |
| 11 | `…/read` | 204, idempotent. Begona — 403, yo'q — 404. |
| 12 | `grades` | Barchasi, sana kamayish. `max_score > 0` bo'lmagan yozuvlar chiqarilmaydi; `score` `[0, max_score]` ga qisiladi (CRM kiritishda allaqachon tekshiradi). CRM ballari butun son. |
| 13 | `homework` | Faol guruhlar vazifalari, faqat bola guruhga qo'shilgan kundan keyingilari. `due_date`: berilgan bo'lsa — o'sha kun `23:59:59+05:00`; berilmagan bo'lsa (CRM: "keyingi dargacha") — jadval bo'yicha keyingi dars boshlanishi; jadval noma'lum — dars sanasi + 7 kun `23:59:59`. Status: topshiriq yozuvi yo'q → `pending`; `done` → `submitted`. Tartib: `due_date` o'sish. |
| 14 | `feedback` | O'qituvchi izohlari (CRM modelida barcha izohlar ota-onaga ko'rinadigan deb belgilangan). Sana — Toshkent kuni. |
| 15 | `certificates` | 6-bo'limga qarang. |
| 16 | `teacher` | Asosiy guruh o'qituvchisi; u nofaol bo'lsa keyingi faol guruh o'qituvchisi. Faqat `name/phone/telegram` (string). `phone` E.164, `telegram` `@username` (`https://t.me/x` → `@x`), yo'q bo'lsa `""`. Hech kim yo'q → `404 teacher_not_assigned`. |

## 4. Moliya: CRM registridan API maydonlariga mapping

Manba — `backend/core_calc.py` (CRM bilan bir xil funksiyalar) va CRM'ning
`GET /students/{id}/payments/summary` endpointi; parent API ayni o'sha hisobni qaytaradi.

| Maydon | Hisob |
|---|---|
| `groups[]` | So'ralgan oyda billing qilinadigan barcha a'zoliklar (`group_billable_in` + `covers_month`) — arxivlangan guruhning o'tgan oylari va guruhdan chiqqan oy ham. |
| `groups[].owed` | `student_month_owed(oy)` — a'zolik tarifi yoki guruh narxi; guruh boshlanmagan/a'zo bo'lmagan oy — 0; ta'til kunlari chiqariladi; Special chegirmalar (`monthly`, `one_time`, `free_month`) qo'llanadi; global chegirma faqat bitta (eng kichik ID'li) faol guruhga. |
| `groups[].paid` | `payments` jadvalida shu guruh + shu `month/year` ga yozilgan summa. |
| `groups[].remaining` | `max(0, owed − paid)` |
| `total_owed` / `total_paid` | `groups` bo'yicha yig'indi. **`total_paid` avansni o'z ichiga OLMAYDI** — faqat shu oyga yozilgan to'lovlar. |
| `debt` | **Kumulyativ**: `max(0, Σ owed(barcha oylar ≤ so'ralgan oy) − Σ paid(butun tarix) − students.advance_balance)` = CRM `student_cumulative_balance`. Bir oydagi ortiqcha to'lov boshqa oy qarzini yopadi. Shuning uchun `debt` ≠ `total_owed − total_paid` bo'lishi mumkin (o'tgan oy qarzi yoki oldindan to'lov) — ilova uni qayta hisoblamaydi. |
| `advance_balance` | `max(0, kumulyativ balans)` — hali ishlatilmagan ortiqcha to'lov + boshlang'ich avans qoldig'i. |
| `advance_applied` | `students.advance_balance` (CRM'da qo'lda kiritiladigan boshlang'ich avans) ning so'ralgan oygacha qarzni yopishga ketgan qismi: `min(avans, max(0, Σ owed − Σ paid))`. To'lovlar avval, avans keyin hisoblanadi; avans ikki marta ayirilmaydi (`debt` formulasida bir marta). |
| `payment_status` | `debt == 0` → `paid` (to'lov talab qilinmagan davr ham); `debt > 0` va hech bo'lmasa bitta to'lov yoki avans bor → `partial`; aks holda `debtor`. CRM'ning `none` holati `paid` ga aylantiriladi (soxta qarzdorlik yo'q). |
| `recent_payments` | Bolaning **butun** to'lov tarixi (`payments` qatorlari), `paid_at` kamayish. Faqat yakunlangan to'lovlar: onlayn to'lov provayder tasdiqlagandan keyingina qator yoziladi. `recorded_by_name` — qabul qilgan xodim, onlayn to'lovda `""` (`notes` = `Payme (onlayn, #<invoys>)`). |

Bekor qilish/qaytarish: CRM'da to'lov o'chirilsa yoki provayder refund qilsa, `payments` qatori o'chadi — summary
avtomatik yangilanadi.

## 5. Onlayn to'lov (`POST /parent/children/{childId}/pay`)

1. Tekshiruv tartibi: bola egaligi (404) → `group_id` shu bolaning a'zoligi (joriy yoki tarixiy; aks holda 404) →
   summa `PAYMENT_MIN_AMOUNT…PAYMENT_MAX_AMOUNT` (1 000 … 20 000 000) → biznes chegarasi
   `kumulyativ qarz + 3 × guruhning oylik to'lovi` (0 bo'lsa `422 nothing_to_pay`) → provayder sozlanganmi (aks holda `503 payment_provider_unavailable`).
2. `parent_invoices` qatori: parent, child, group, amount (so'm), provider, `status=pending`, `expires_at = +PARENT_INVOICE_TTL_MIN` (12 soat).
   Takroriy bosish: 30 daqiqa ichida xuddi shu (parent, child, group, provider, amount) bilan provayderga hali tushmagan
   pending invoys bo'lsa — o'sha qaytariladi (Idempotency-Key talab qilinmaydi).
3. `checkout_url` faqat ruxsat etilgan hostlarga: `checkout.paycom.uz` / `checkout.test.paycom.uz`, `my.click.uz`, `www.uzumbank.uz`.
   Bearer talab qilmaydi. `PAYMENT_RETURN_URL` (https) — faqat brauzerni qaytaradi; **qaytish to'lov tasdig'i emas**.
4. Pul registrga **faqat** provayder `Perform/Complete/Confirm` qilganda yoziladi.
   **Taqsimot**: tanlangan guruh bo'yicha eng eski qarzdan boshlab (a'zolik boshlangan oydan joriy oygacha) har oy uchun
   alohida `payments` qatori; ortib qolgani joriy oyga (guruh hali boshlanmagan bo'lsa — boshlanish oyiga) yoziladi va CRM
   hisobida avansga aylanadi. So'ng ota-onalarga `payment` bildirishnomasi.
5. Ilova qaytganda `payment-summary`ni qayta oladi; alohida status endpointi yo'q.

### Callback'lar (provayder kabinetida sozlanadi)

| Provayder | URL (`https://crm.minaracademy.uz/api` + …) | Auth | Kabinet sozlamalari |
|---|---|---|---|
| Payme | `POST /payment-callbacks/payme` (JSON-RPC 2.0: CheckPerformTransaction, CreateTransaction, PerformTransaction, CancelTransaction, CheckTransaction, GetStatement) | `Basic base64("Paycom:" + PAYME_KEY)` | Endpoint URL; hisob (account) maydoni `invoice_id` (`PAYME_ACCOUNT_FIELD`), turi — son; summa tiyinda; kassa ID → `PAYME_MERCHANT_ID`, kalit → `PAYME_KEY` (test kalit bilan sandbox `checkout.test.paycom.uz`). |
| Click | `POST /payment-callbacks/click/prepare` va `POST /payment-callbacks/click/complete` (form-urlencoded) | `sign_string` = MD5 (Click SHOP API formulasi, `CLICK_SECRET_KEY`) | Prepare URL, Complete URL; `service_id`, `merchant_id`, secret key; `merchant_trans_id` = invoys ID. |
| Uzum | `POST /payment-callbacks/uzum/check`, `/create`, `/confirm`, `/reverse`, `/status` | `Basic base64(UZUM_LOGIN:UZUM_PASSWORD)` + `serviceId` tekshiruvi | Webhook bazaviy URL, login/parol, `serviceId`; to'lov parametri nomi `order_id` (`UZUM_ACCOUNT_FIELD`); summa tiyinda. Xato javobi — HTTP 400 + `{"status":"FAILED","errorCode":"100xx"}`. |

nginx `/api/payment-callbacks/` ni `crm-api`ga uzatishi kerak (umumiy `/api/` qoidasi bilan qamraladi). Provayder IP
allowlist'i ixtiyoriy qo'shimcha himoya sifatida nginx'da qo'yilishi mumkin.

Kafolatlar: imzo/credential, invoys mavjudligi va provayderi, summa (tiyin aniqligida), invoys holati va muddati
tekshiriladi. `payment_transactions (provider, provider_txn_id)` unikal; invoys qatori `SELECT … FOR UPDATE` bilan
qulflanadi; `pending → paid` faqat bir marta — takroriy/parallel callback ikkinchi `payments` qatorini yaratmaydi.
Created/cancelled tranzaksiyalar tarixga kirmaydi. Payme: "created" tranzaksiya 12 soatdan keyin perform qilinsa —
reason 4 bilan bekor. Refund (`CancelTransaction` state 2 / Uzum `reverse`) — `PAYMENT_ALLOW_REFUND=false` bo'lsa rad etiladi
(Payme −31007, Uzum 10017).

**Reconciliation**: admin `GET /parent-invoices?status=&provider=&student_id=` (CRM token, admin roli) — invoyslar
va provayder tranzaksiyalari; provayderga tushmagan va muddati o'tgan pending invoyslar `expired` ko'rinadi.
Payme `GetStatement` ham shu ma'lumotdan javob beradi. Provayderdan faol ravishda status so'rash (pull) amalga
oshirilmagan — 9-bo'limga qarang.

## 6. Sertifikat havolalari

`url` = `https://crm.minaracademy.uz/api/parent/certificates/{id}/file?exp=…&sig=…` — HMAC-SHA256 (`SECRET_KEY`) bilan
imzolangan, `PARENT_CERT_URL_TTL_HOURS` (24) + soat boshigacha amal qiladi. Bearer va token URL'da yo'q. Server faylni
o'zi beradi (`/uploads/certificates/<uuid>.pdf`) yoki tashqi HTTPS manzilga 302 qiladi. Muddati o'tgan havola —
`403 link_expired`: ilova ro'yxatni (`GET …/certificates`) qayta olishi kerak (offline keshdagi eski havola ishlamaydi).
`http://` (shifrlanmagan) manzilli sertifikatlar ro'yxatga kirmaydi.

## 7. Administrator yo'riqnomasi: ota-ona akkaunti

1. CRM → Ota-onalar (hunter yoki admin): `POST /parents` `{full_name, phone, student_ids[]}`. Login avtomatik = telefon.
   Parol berilmasa 8 belgili tasodifiy parol **bir marta** javobda ko'rsatiladi — ota-onaga xavfsiz kanal orqali bering.
2. Bola qo'shish/olib tashlash: `POST /parents/{id}/children {student_id}`, `DELETE /parents/{id}/children/{student_id}`.
3. Parol tiklash: `POST /parents/{id}/reset-password` (barcha sessiyalar bekor bo'ladi).
4. Bloklash: `PATCH /parents/{id} {is_active:false}`.
Mobil ilovada ro'yxatdan o'tish, OTP yoki parolni tiklash yo'q.

## 8. Test fixture (production'dan ajratilgan)

```bash
# staging/lokal baza (DATABASE_URL), credential faqat env'da — repoga yozilmaydi
PARENT_FIXTURE_PHONE=+998900000099 PARENT_FIXTURE_PASSWORD='<kamida-10-belgi>' \
  python -m backend.scripts.seed_parent_fixture --i-understand-this-is-not-production
```
1 ota-ona + 2 "TEST —" bola (biri 2 guruhda), jadval, davomat, to'lov, baho, uy vazifasi, izoh yaratadi.
`backend/seed_test_parent.py` (haqiqiy talabani bog'laydigan eski skript) endi parolni `TEST_PARENT_PASSWORD` env'dan oladi.

Flutter: `flutter run --dart-define=USE_MOCK=false --dart-define=API_BASE_URL=https://crm.minaracademy.uz/api`.
Live test: `flutter test --run-skipped test/live_api_test.dart --dart-define=LIVE_BASE_URL=… --dart-define=LIVE_USERNAME=… --dart-define=LIVE_PASSWORD=…`
(u faqat o'qish oqimlarini qamraydi; mutatsiyalar, refresh va to'lov backend testlarida).

## 9. Test natijalari va nimalar sinalgan

`pytest backend/tests/test_parent.py` — 38 test (umumiy to'plam 232 test, hammasi o'tadi). Qamrov: login (telefon formatlari,
bir xil 401, trim yo'q, nofaol, xodim tokeni, eskirgan access, rate limit + Retry-After), refresh (rotation, grace,
reuse → revoke, eskirgan), xato formati (400/422/503), profil PATCH (204, extra=forbid, avatar MIME/base64),
farzandlar (bo'sh, shakl, chegirma foizi), barcha child endpointlarida ownership, bo'sh ro'yxatlar, payment-summary
(debtor/partial/paid/ortiqcha to'lov, ko'p guruh, avans, free_month, query validatsiyasi), davomat (bir kunda ikki dars,
belgilanmagan/kelajak chiqarilgan), jadval (slot/matn/vaqtsiz), bildirishnomalar (403/404/idempotent/ota-onalar mustaqil),
baholar (max_score 50), uy vazifasi (muddat va timezone, `done`→`submitted`, qo'shilishdan oldingilar yo'q), izoh,
o'qituvchi (string, `""`, t.me), sertifikat (imzo, Bearer'siz, 302, muddati/sig xato → 403), /pay (503, validatsiya,
checkout URL tarkibi, takroriy bosish, to'lanmagan pul tarixda yo'q), Payme/Click/Uzum to'liq oqimlari (noto'g'ri
imzo/auth, summa, begona invoys, takroriy perform/complete/confirm — bitta yozuv, bekor qilish, refund, timeout).

**Sinalmagan**: haqiqiy provayder sandbox'lari (credential yo'q) — adapterlar rasmiy protokol bo'yicha yozilgan va
mock so'rovlar bilan sinalgan; haqiqiy parallel (ko'p jarayonli) callback'lar faqat Postgres `FOR UPDATE` + unique
constraint'ga tayanadi (SQLite testlarida ketma-ket takror sinalgan).

## 10. Tayyor bo'lmagan joylar / kerakli qarorlar

1. **Provayder credential'lari yo'q** — `PAYME_*`, `CLICK_*`, `UZUM_*` berilmaguncha `/pay` → 503. Har biri uchun sandbox'da
   sinov o'tkazing (Payme sandbox test-suite'i, Click/Uzum test kabinet). Uzum xato javobining HTTP statusi (400) va
   `params` kalit nomi provayder bilan tasdiqlansin.
2. **Ilova uch provayderni ham ko'rsatadi** — productionda sozlanmaganlari 503 qaytaradi. Yashirish uchun frontend
   sozlamasi yoki keyingi bosqichda `GET /parent/config` (yoqilgan provayderlar) endpointi kerak.
3. **Reconciliation pull** — Click `payment/status` va Payme receipts API orqali faol tekshiruv qilinmaydi (merchant
   API credential'lari kerak); hozircha callback + `/parent-invoices` ko'rinishi + Payme `GetStatement`.
4. **Fiskalizatsiya (OFD/IKPU)** — Payme `detail`/`SetFiscalData` va soliq talablari aniqlanmagan; buxgalteriya qarori kerak.
5. **CRM `/uploads/certificates/`** — CRM UI uchun hali imzosiz (eski xatti-harakat). Parent API o'z imzolangan havolasidan
   foydalanadi; to'liq yopish uchun CRM frontend ham imzolangan havolaga o'tishi kerak.
6. **Ko'p guruhli bola** — `/children` va `/teacher` bitta asosiy guruhni ko'rsatadi (qoidasi yuqorida); bir nechta o'qituvchi —
   mobil model kengaytmasi.
7. Mobil hali chaqirmaydigan imkoniyatlar (alohida bosqich): `POST /parent/auth/logout` (refresh revoke), push (APNs/FCM)
   device token, notification preferences, parol tiklash/OTP, payment status polling va deep link, markaz kontaktlari
   konfiguratsiyasi, locale, bir martalik dars o'zgarishlari, qo'shimcha davomat statuslari, uy vazifasi topshirish.
8. Decimal ballar — CRM'da ball butun son; kasr kerak bo'lsa CRM va mobil model o'zgarishi kerak.
