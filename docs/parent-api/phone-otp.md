# Telefon + Telegram OTP login/registratsiya (ota-ona ilovasi)

Kod SMS emas, [Telegram Gateway API](https://core.telegram.org/gateway/api) orqali foydalanuvchining
Telegram akkauntiga yuboriladi. Mobil ilova faqat quyidagi backend endpointlari bilan ishlaydi —
Gateway tokeni ilovaga hech qachon berilmaydi.

Kod: `backend/parent/phone_auth/` — `gateway.py` (TelegramGatewayClient), `service.py`
(PhoneVerificationService), `router.py` (controller). Model: `PhoneVerification`, `Parent.phone_verified_at`.
Migratsiya: `20261007a_phone_verifications`. Testlar: `backend/tests/test_phone_auth.py`.

## Oqim

1. `POST /api/auth/phone/request-code` → `verificationId` (backend yaratgan tasodifiy ID; Telegram `request_id` clientga berilmaydi).
2. Foydalanuvchi Telegram'da kelgan 6 xonali kodni kiritadi.
3. `POST /api/auth/phone/verify-code` → `{access_token, refresh_token}` — parent API'ning odatiy token juftligi
   (`/parent/*` endpointlari va `/parent/auth/refresh` bilan ishlaydi).
   Raqam bo'yicha ota-ona bo'lsa — login (admin biriktirgan farzandlar ko'rinadi); bo'lmasa — yangi ota-ona
   akkaunti yaratiladi (farzandlari bo'sh; admin CRM'da biriktiradi).
4. Kod kelmasa — 60 soniyadan keyin `POST /api/auth/phone/resend-code` (yangi `verificationId` qaytadi, eskisi bekor).

## Shartnoma

### request-code
```http
POST /api/auth/phone/request-code
{"phoneNumber": "+998901234567"}
```
200 (foydalanuvchi bor-yo'qligidan qat'i nazar bir xil):
```json
{"success": true, "verificationId": "Zk3…", "expiresIn": 120, "message": "Tasdiqlash kodi Telegram orqali yuborildi"}
```
Raqam E.164 ga normalizatsiya qilinadi (`+998 90 123-45-67`, `998901234567`, `901234567` ham qabul qilinadi).
Faqat `PHONE_OTP_ALLOWED_PREFIXES` (standart `+998`) raqamlari.

### resend-code
```http
POST /api/auth/phone/resend-code
{"verificationId": "Zk3…", "phoneNumber": "+998901234567"}
```
200 — request-code bilan bir xil shakl, **yangi** `verificationId`. Eski kod Telegram'da ham bekor qilinadi.

### verify-code
```http
POST /api/auth/phone/verify-code
{"verificationId": "Zk3…", "phoneNumber": "+998901234567", "code": "123456"}
```
200: `{"access_token": "…", "refresh_token": "…"}`

### Xatolar
Format: `{"code", "message", "errors", "request_id"}` (parent API bilan bir xil). Gateway'ning xom javobi qaytarilmaydi.

| HTTP | code | Holat |
|---|---|---|
| 400 | `validation_error`, `invalid_json` | Maydonlar noto'g'ri / ortiqcha maydon / kod 6 raqam emas |
| 400 | `invalid_phone_number`, `phone_not_supported` | Raqam formati yoki davlati |
| 400 | `phone_mismatch` | Raqam `verificationId` ga mos emas |
| 400 | `telegram_not_available` | Bu raqamga Telegram orqali kod yuborib bo'lmaydi |
| 401 | `code_invalid` | Kod noto'g'ri (`message`da qolgan urinishlar) |
| 401 | `code_expired` | 120 soniya o'tgan yoki Gateway `expired` |
| 403 | `account_disabled` | Ota-ona akkaunti bloklangan |
| 404 | `verification_not_found` | `verificationId` yo'q |
| 409 | `verification_already_used` | Kod allaqachon ishlatilgan (replay) |
| 409 | `verification_superseded`, `verification_not_active`, `verification_not_ready`, `account_conflict` | Holat konflikti |
| 429 | `resend_cooldown`, `too_many_resends`, `too_many_requests`, `request_in_progress`, `code_max_attempts_exceeded` | Limitlar (`Retry-After` header) |
| 502 | `gateway_error` | Gateway so'rovni rad etdi / kutilmagan javob |
| 503 | `gateway_unavailable` | Gateway ishlamayapti, timeout yoki token sozlanmagan |

## Xavfsizlik qoidalari

| Qoida | Qiymat |
|---|---|
| Kod uzunligi / muddati | 6 raqam / 120 s (Gateway `ttl` ham 120) |
| Noto'g'ri urinishlar | 5 ta, atomik hisoblanadi (6-urinish Gateway'ga bormaydi) |
| Resend | Oraliq ≥ 60 s, bitta zanjirda ko'pi bilan 3 ta |
| Rate limit | Yuborish: IP 10/10 daq., raqam 5/soat; tekshirish: IP 30/10 daq. (Redis bo'lsa konteynerlar orasida umumiy) |
| Faol verification | Bir raqamga bittadan (DB unikal qisman indeksi — parallel so'rovlar ham) |
| Replay | `verified` holatiga atomik o'tish; token berish shu tranzaksiyada |
| Timeout | Gateway so'rovi 10 s. `sendVerificationMessage` qayta yuborilmaydi (ikki kod/to'lov bo'lmasin); `checkVerificationStatus` faqat ulanish xatosida 1 marta |
| Loglar | Telefon maskalanadi (`+998*******67`); kod, Gateway tokeni va access token yozilmaydi |
| Yangi akkaunt | Tasodifiy (noma'lum) parol bilan — parol orqali kirib bo'lmaydi; admin `reset-password` bilan parol berishi mumkin |
| HTTPS | Production faqat `https://crm.minaracademy.uz` (nginx TLS) |

## Environment

```
TELEGRAM_GATEWAY_TOKEN=                       # majburiy; bo'lmasa 503 gateway_unavailable
TELEGRAM_GATEWAY_BASE_URL=https://gatewayapi.telegram.org
PHONE_OTP_ALLOWED_PREFIXES=+998
```

## curl

```bash
B=https://crm.minaracademy.uz/api
curl -s -X POST $B/auth/phone/request-code -H 'Content-Type: application/json' \
  -d '{"phoneNumber":"+998901234567"}'
curl -s -X POST $B/auth/phone/resend-code -H 'Content-Type: application/json' \
  -d '{"verificationId":"<id>","phoneNumber":"+998901234567"}'
curl -s -X POST $B/auth/phone/verify-code -H 'Content-Type: application/json' \
  -d '{"verificationId":"<id>","phoneNumber":"+998901234567","code":"123456"}'
```

## Ochiq qarorlar

* Yangi ro'yxatdan o'tgan ota-ona avtomatik ravishda farzandga bog'lanmaydi (admin CRM'da biriktiradi).
  `students.father_phone`/`mother_phone` bo'yicha avtomatik bog'lash — biznes qarori talab qiladi.
* Gateway `callback_url` (yetkazish hisobotlari) ishlatilmaydi.
* Gateway xato satrlari hujjatda ro'yxatlanmagan — kalit so'zlar bo'yicha guruhlanadi (`gateway.py:_classify`);
  haqiqiy xatolar loglarda (`ithub.telegram_gateway`) kuzatilib, kerak bo'lsa aniqlashtiriladi.

## App Store review akkaunti

`PARENT_REVIEW_PHONE` va `PARENT_REVIEW_OTP` (4–6 raqam) env'da berilganda shu raqam uchun:
Telegram'ga kod yuborilmaydi, `verify-code` faqat shu qat'iy kodni qabul qiladi (boshqa raqamlar uchun
4–5 xonali kod `validation_error`), raqam bo'yicha soatlik limit qo'llanmaydi (IP limitlari qoladi).
`DELETE /parent/account` bu akkauntda faqat sessiyalarni bekor qiladi — akkaunt va xayoliy farzand keyingi
review'lar uchun saqlanadi (log: `mode=review_reset`). Qiymatlar faqat server env'ida
(`/var/www/minar-stack/env/ithub.env`); repoga va loglarga yozilmaydi. Biri bo'sh bo'lsa funksiya o'chiq.

Parol ekrani (`POST /parent/auth/login`) ham qo'llab-quvvatlanadi: shu raqam + qat'iy kod parol sifatida — akkaunt bo'lmasa yaratiladi.
