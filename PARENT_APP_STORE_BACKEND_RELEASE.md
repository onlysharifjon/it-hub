# Minar Parents — CRM backend App Store release gate

> Holat 2026-10-11 dan yangilangan. Prod `/var/www/minar-stack` (Docker) dan ishlaydi; deploy —
> `sudo scripts/deploy.sh ithub --ref <commit>`. Aniq commit, deploy vaqti va smoke-test natijalari
> pastdagi "Production tekshiruvi" bo'limida. **Kod merge qilingani prod ishlayapti degani emas** —
> har deploy'dan keyin shu bo'limni yangilang.

## Endpointlar (nginx orqali `https://crm.minaracademy.uz/api/...`)

| Endpoint | Auth | Javob |
|---|---|---|
| `GET /parent/privacy.html` | yo'q | 200 `text/html`, redirectsiz (uz/ru/en) |
| `GET /parent/app-config` | Bearer (ota-ona) | 200 `{payments_enabled, payment_providers, account_deletion_enabled, privacy_policy_url}`; authsiz 401 |
| `DELETE /parent/account` | Bearer (ota-ona) | 204 faqat commit'dan keyin; authsiz/eskirgan/o'chirilgan token 401; xatoda 5xx (rollback) |

### app-config flag'lari (fail closed, env orqali qo'lda yoqiladi)

- `payments_enabled` / `payment_providers` — faqat `PARENT_PAYMENTS_ENABLED=true` **va** provayderning barcha
  merchant o'zgaruvchilari berilganda. Kalit o'chiq bo'lsa `false` / `[]`, `POST /parent/children/{id}/pay` esa
  invoys yaratmasdan 503 `payment_provider_unavailable` qaytaradi. Callback endpointlari kalitga bog'liq emas
  (mavjud invoyslar yakunlanishi uchun).
- `account_deletion_enabled` — `PARENT_ACCOUNT_DELETION_ENABLED=true` bo'lganda. Endpoint flag'dan qat'i nazar
  ishlaydi (ilovaning eski build'lari va qo'lda so'rovlar uchun); flag faqat ilovadagi tugmani boshqaradi.
- Ikkala flag ham prod'da real sinov va release egasi tasdig'idan keyingina yoqiladi.

## Akkauntni o'chirish jarayoni

Bitta tranzaksiyada (`SELECT ... FOR UPDATE` bilan parallel login/refresh'dan himoyalangan):

1. Barcha refresh tokenlar o'chiriladi; access token ota-ona yo'q/nofaol bo'lgani uchun keyingi so'rovda 401.
2. Ota-ona bildirishnomalari, ota-ona↔bola bog'lanishlari, telefon tasdiqlash (OTP) yozuvlari (telefon, IP) o'chiriladi.
3. `parent_invoices` bo'lmasa — `parents` qatori butunlay o'chiriladi (`erased`).
   Bo'lsa — buxgalteriya uchun shaxssiz "tombstone" qoladi (`anonymized`): `deleted-parent-<id>` login/telefon,
   ism/rasm yo'q, tasodifiy yaroqsiz parol, `is_active=false`. Invoys (summa, provayder, `student_id`) saqlanadi.
4. **Saqlanadigan yozuvlar** (ota-onaga emas, akademiyaga tegishli): o'quvchi kartasi, davomat, baholar, uy
   vazifalari, to'lovlar (`payments`), o'qituvchi izohlari, sertifikatlar.
5. Commit'dan keyin 204. Xatoda rollback va 5xx; ilova sessiyani faqat 204 da tozalashi kerak (404/5xx — muvaffaqiyat emas).
6. **Audit**: konteyner logida `AUDIT parent_account_deleted parent_id=<id> mode=erased|anonymized request_id=<id>`
   (shaxsiy ma'lumotsiz). `audit_logs` jadvali `users`ga majburiy FK talab qiladi, shuning uchun DB'ga yozilmaydi;
   docker log retention'i alohida belgilanishi kerak (ochiq masala).
7. **Backup**: `minar-stack` backup servisi `BACKUP_KEEP_DAYS` (compose default — 14 kun) dan eski dump'larni
   o'chiradi. O'chirilgan ma'lumot shu muddatgacha zaxirada qoladi; zaxiradan tiklansa, o'chirilgan akkauntlar
   audit logi bo'yicha qayta o'chirilishi kerak. Prod'dagi haqiqiy qiymatni operator tasdiqlasin.
8. Jarayon to'liq avtomatik — qo'lda davom etadigan bosqich yo'q, shuning uchun alohida muddat/yakun xabari kerak emas;
   204 javobining o'zi yakun tasdig'i.

**Ochiq (huquqiy/release egasi):** tombstone + invoysdagi `student_id` saqlanishi qonuniy asosi va muddati;
Apple 5.1.1(v) talabiga mosligi; privacy siyosatidagi operator (yuridik shaxs nomi, manzil, email/telefon) —
hozir faqat "minaracademy.uz orqali" deyilgan. Siyosat matni privacy egasi/yurist tasdig'idan o'tmagan.

## Onlayn to'lov

Payme/Click/Uzum checkout va imzolangan callback'lar kodda bor (`backend/parent/payments/`, testlar:
idempotency, dublikat, noto'g'ri summa/guruh, imzo, cancel/refund, muddati o'tgan). Lekin merchant sertifikatsiyasi
va prod'da real to'lov sinovi o'tkazilmagan — shuning uchun `PARENT_PAYMENTS_ENABLED` o'rnatilmagan va ilovada
to'lov o'chiq. Yoqishdan oldin: har provayder sandbox + real kichik summa, cancel/refund, kechikkan callback,
ilovaga qaytish to'lov tasdig'i emasligi (holat faqat callback'dan). App Store 3.1.3(e) — akademiya kurslari
ilovadan tashqarida iste'mol qilinadigan xizmat ekanini release egasi tasdiqlasin.

## High-priority public-repository security findings (not automatically remediated on live server)

`docker-compose.yml` currently contains a hard-coded database password and camera API key default, and `SECRET_KEY` defaults to `change-me-in-production`. The GitHub Actions workflow also includes a fixed example database password. Because the repository is **public**, assume these secrets are compromised if they were ever reused in production.

**Required production operations by an authorized server operator:**
1. Confirm current server compose/PM2/systemd environment and that backups can be restored.
2. Determine whether any published credentials are actually active. If active, rotate the database role password, application secret and camera API key **in a coordinated sequence** with all dependent services.
3. Remove secret literals and fallback values from production deployment configuration; use environment/secrets manager, enforce least privilege, bind Postgres to localhost/private network instead of `0.0.0.0:5432`, and restrict `.env` access. Merely removing Git history does **not** revoke compromised credentials.
4. Review access logs for abuse and make sure GitHub Actions `production` has mandatory environment approval.
5. Verify monitoring, backup, restore, rollback and availability; only then deploy.

Changing the DB password/SECRET_KEY blindly could disconnect the CRM or invalidate every session. This PR intentionally does **not** restart live services.

## Predeployment infrastructure checklist

1. Map running code location: server screenshot shows `/var/www/it-hub`, owned by `ubuntu:ubuntu`; repository contains Docker Compose and `.venv`. **Do not assume the code runs from this checkout** without inspecting `docker compose ps`, systemd, Docker labels, and Nginx.
2. SSH access: user created `minar-deploy` without sudo, and `/home/minar-deploy/.ssh/authorized_keys` is empty. Provision a **new, separate deployment public key** via a trusted client. Do not share private keys or passwords in chat.
3. This PR changes GitHub Actions production image build/deployment to **manual `workflow_dispatch` only**, so a push/merge to `main` runs checks but will not automatically touch the server. Deployment job now points at `/var/www/it-hub`; verify actual running service and workflow before any manual dispatch. If the server uses PM2, do not assume a Docker job deploys its process.
4. Avoid putting `minar-deploy` in `docker` group or unrestricted `sudo`. Prefer a tightly constrained deployment wrapper with explicit services, one authenticated job, and environment approval.
5. Safely deploy on staging first. Preserve a Git SHA rollback plan.

## Useful commands to be run by the server operator (read-only)

```sh
cd /var/www/it-hub
git status -sb
git remote
sudo docker compose ps
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
systemctl list-units --type=service --all | grep -Ei 'minar|crm|uvicorn|gunicorn|supervisor|docker'
sudo ls -l /etc/nginx/sites-enabled
```

Never paste `.env`, database passwords, private keys, full credential-bearing git remote URLs, or live student records.

## Repo links

- iOS draft PR: https://github.com/onlysharifjon/minar-parents-swift/pull/1
- Apple guidelines: https://developer.apple.com/app-store/review/guidelines/
- Parent API source: `backend/parent/router_parent.py`

## Production deploy (server operator)

Prod `/var/www/it-hub` checkout'idan emas, `/var/www/minar-stack` Docker stekidan ishlaydi.

```bash
cd /var/www/minar-stack
sudo scripts/deploy.sh status          # joriy ITHUB_TAG; deploy qilinadigan ref shu commit'ni o'z ichiga olsin
sudo scripts/deploy.sh ithub --ref <commit>     # crm-api, space-api, worker + alembic migratsiya
sudo scripts/deploy.sh crm-web --ref <commit>   # CRM frontend
```

Rollback — oldingi ishlagan tag bilan (`--ref <oldingi tag>`). `docker compose down -v`, seed skriptlari va
o'chirish testlarini haqiqiy ota-ona akkauntlarida ishlatmang.
