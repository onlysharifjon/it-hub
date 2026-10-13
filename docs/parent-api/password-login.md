# Minar Parents — telefon raqam + parol bilan kirish

Telegram Gateway OTP har kirishda pul talab qiladi va kod har doim ham yetib bormaydi. Yangi iOS versiyasi
**telefon raqam + parol** bilan kiradi. Mavjud endpoint va javob formati o'zgarmaydi.

## 1. API shartnomasi (iOS)

### Login — `POST /api/parent/auth/login` (o'zgarmagan)

```json
{"username": "+998901234567", "password": "<parol>"}
```

* `200` → `{"access_token": "...", "refresh_token": "..."}`.
* `401 invalid_credentials` — raqam yo'q / parol xato / akkaunt bloklangan (hammasiga bir xil javob).
* `401 account_not_found` — akkaunt ilovadan o'chirilgan (**faqat to'g'ri parol berilganda**).
* `429 rate_limited` (+ `Retry-After`) — IP 15/min, raqam+IP 6/min, raqam 30/min.
* Parol trim qilinmaydi. Kirishda eski parollar ham qabul qilinadi (uzunlik talabi faqat yangi parollarga).

### Refresh — `POST /api/parent/auth/refresh` (o'zgarmagan)

### Parolni almashtirish — `POST /api/parent/auth/change-password` (YANGI)

`Authorization: Bearer <access_token>`

```json
{"current_password": "<joriy>", "new_password": "<yangi, 15+ belgi>"}
```

| Javob | Ma'nosi | iOS nima qiladi |
|---|---|---|
| `200 {access_token, refresh_token}` | Almashtirildi. Boshqa qurilmalardagi sessiyalar bekor qilindi | **Ikkala yangi tokenni saqlaydi** (eskilari endi ishlamaydi) |
| `400 invalid_current_password` | Joriy parol xato. Sessiya saqlanadi | Xatoni ko'rsatadi, logout **qilmaydi** |
| `422 validation_error`, `errors.new_password[]` | Yangi parol talabga mos emas yoki joriy parol bilan bir xil | `errors.new_password[0]` ni ko'rsatadi |
| `429 rate_limited` + `Retry-After: 900` | 15 daqiqada 5 urinishdan ko'p (IP bo'yicha — 20) | Kutadi |
| `401 unauthorized` | Token yaroqsiz | Odatdagi logout/refresh |

Yangi parol talablari:
* kamida **15 belgi**;
* ko'pi bilan **72 bayt** UTF-8 (lotin harflari bilan 72 belgigacha, 64 belgili ibora ham bemalol sig'adi; bcrypt
  72 baytdan keyingi qismni e'tiborsiz qoldiradi, shuning uchun uzunrog'i rad etiladi);
* bo'shliq bilan boshlanmaydi va tugamaydi, boshqaruv belgilari yo'q, kamida 5 xil belgi.

Tarkib bo'yicha qoidalar (katta harf, raqam va h.k.) yo'q: uzun ibora (passphrase) tavsiya etiladi.

### Sessiyalarni bekor qilish

Ota-ona parolni o'zi almashtirsa ham, admin reset qilsa ham:
* ota-onaning **barcha refresh tokenlari o'chiriladi** (boshqa qurilma refresh qilsa — `401 invalid_token`);
* access token'da `pwv` claim (parol hash'idan olingan HMAC) bor. Parol o'zgarishi bilan avval berilgan access
  tokenlar ham **darhol** `401` bo'ladi (30 daqiqa kutilmaydi);
* `pwv`siz tokenlar (deploy'dan oldin berilganlari) TTL tugaguncha (≤ 30 daqiqa) ishlayveradi, shuning uchun deploy
  paytida hech kim majburan chiqarilmaydi.

## 2. Administrator yo'riqnomasi

### Yangi ota-ona

CRM → Ota-onalar → «Yaratish» (`POST /parents`). Login avtomatik = telefon, **+998XXXXXXXXX** ko'rinishida saqlanadi.
Parol maydoni bo'sh qolsa, 20 belgili tasodifiy parol yaratiladi (o'xshash 0/O/1/l/I belgilarsiz). Qo'lda parol
kiritilsa, u ham kamida 15 belgi bo'lishi kerak. Parol **faqat bir marta** ko'rsatiladi (`Cache-Control: no-store`).
Bazada faqat bcrypt hash saqlanadi, parol logga ham, auditga ham yozilmaydi.

### OTP orqali o'zi ro'yxatdan o'tgan ota-ona

Uning paroli tasodifiy va hech kimga ma'lum emas. Shu raqam bilan «Yaratish» bosilsa, `409 … (ID n) — «Parolni
yangilash»dan foydalaning` qaytadi: raqam istalgan formatda kiritilgan bo'lsa ham dublikat yaratilmaydi. Ro'yxatdan shu
ota-onani topib, **«Parolni yangilash»** (`POST /parents/{id}/reset-password`) bosiladi va ko'rsatilgan parol ota-onaga
beriladi. Farzandlar odatdagidek biriktiriladi.

### Parolni unutgan ota-ona

1. Ota-ona markazga keladi yoki ma'lum raqamidan qo'ng'iroq qiladi. Administrator shaxsini tekshiradi: ism-familiya,
   farzand ismi va guruhi, CRM'dagi raqam bilan mosligi. Faqat raqamning o'zi yetarli emas.
2. CRM → Ota-onalar → «Parolni yangilash». Yangi parol bir marta ko'rsatiladi.
3. Parol shaxsan yoki ota-onaning CRM'dagi raqamiga yuboriladi (Telegram/SMS qo'lda). Parolni guruh chatlariga
   yozmang. Ekranni boshqalarga ko'rsatmang.
4. Eski parol va barcha qurilmalardagi sessiyalar darhol bekor bo'ladi. Ota-ona ilovaga kirgach, «Parolni
   almashtirish» orqali o'zi tanlagan parolga o'tishi tavsiya etiladi.

Telefon raqamiga kod yuborish majburiy emas. Ilovada «parolni unutdim» oqimi hozircha yo'q, uning o'rniga admin reset
ishlatiladi.

Har bir reset `audit_logs` jadvaliga yoziladi (`entity_type=parent, action=reset_password`, kim bajargani). Parolning
o'zi yozilmaydi.

## 3. App Store review akkaunti

Hozir: `PARENT_REVIEW_PHONE` + `PARENT_REVIEW_OTP` (4 xonali qat'iy kod) bilan OTP ekranida ham, parol ekranida ham
kiriladi. Bu holat **o'zgarmaydi**: eski build va hozirgi review eslatmalari ishlayveradi.

**Xavf.** 4 xonali kod — atigi 10 000 variant. Login limiti raqam bo'yicha 30/min, ya'ni ko'p IP'dan urinilsa, kodni
taxminan 5,5 soatda terib topish mumkin. Akkauntda faqat xayoliy farzand bor, ammo ochilgan akkauntda review uchun Payme
yoqilgan (haqiqiy to'lov ochilishi mumkin), profil va avatarni o'zgartirish ham mumkin. Bundan tashqari, kod repo/ilova
eslatmalari orqali tarqalib ketsa, uni bekor qilib bo'lmaydi.

**Migratsiya (kodni o'zgartirmasdan, faqat CRM va env bilan):**
1. Review akkaunti CRM'da bor (raqam = `PARENT_REVIEW_PHONE`). Unga «Parolni yangilash» bosiladi va 20 belgili parol
   olinadi. Statik kod ishlashda davom etadi.
2. App Store Connect → App Review Information: login `+998XXXXXXXXX`, parol = yangi kuchli parol. Yangi (password-only)
   build shu ma'lumot bilan yuboriladi.
3. Yangi build tasdiqlanib, eski build'lar majburiy yangilanishdan keyin ishlatilmay qolgach, `.env` dan
   `PARENT_REVIEW_OTP` **olib tashlanadi** (`PARENT_REVIEW_PHONE` qoladi) va konteyner qayta ishga tushiriladi. Shundan
   keyin statik kod hech qayerda qabul qilinmaydi. Review akkaunti esa kuchli parol bilan kirishda davom etadi, faqat
   xayoliy farzandni ko'radi va review uchun to'lov sozlamasi saqlanadi.
4. Oraliq choralar: kodni 6 xonali qilish (`PARENT_REVIEW_OTP=XXXXXX`, App Store eslatmasini ham yangilash) va review
   tugashi bilan statik kodni o'chirib qo'yish.

## 4. OTP endpointlari

`POST /api/auth/phone/request-code`, `/resend-code`, `/verify-code` **o'chirilmagan**, chunki App Store'dagi eski build
ularni ishlatadi. Ularni o'chirish rejasi:
1. Password-only iOS versiyasi chiqadi, minimal versiya majburiy qilinadi.
2. OTP so'rovlari (`otp sent` loglari) bir necha hafta nolga yaqin bo'lib turadi.
3. Shundan keyin router `main.py` dan olib tashlanadi yoki `TELEGRAM_GATEWAY_TOKEN` o'chiriladi (endpoint
   `503 gateway_unavailable` qaytaradi). Bu alohida o'zgarish sifatida qilinadi.
