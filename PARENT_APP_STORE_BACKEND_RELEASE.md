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

## Akkauntni o'chirish jarayoni (2026-10-12 dan: kirish yopiladi, ma'lumot saqlanadi)

Egasi qarori: ilovadan o'chirilganda ma'lumot o'chirilmaydi, faqat kirish yopiladi.

1. `DELETE /parent/account` (Bearer) — bitta tranzaksiyada (`FOR UPDATE`): barcha refresh tokenlar o'chiriladi,
   `parents.is_active=false`, `parents.deleted_at=now()`. Commit'dan keyin **204**. Access token keyingi so'rovda 401
   (ota-ona nofaol). Xatoda rollback + 5xx; token yo'q/eskirgan/allaqachon o'chirilgan — 401.
2. Keyin shu raqam bilan kirish (parol `POST /parent/auth/login` yoki OTP `verify-code`) →
   **401 `account_not_found`** "Bunday raqam bizda mavjud emas. Akkauntni administrator orqali yarating."
   (admin bloklagan, `deleted_at` bo'sh akkaunt — oldingidek `invalid_credentials` / `account_disabled`).
3. Saqlanadi: ota-ona yozuvi, farzand bog'lanishlari, bildirishnomalar, OTP yozuvlari, invoyslar, o'quvchining barcha yozuvlari.
4. Tiklash: CRM'da `POST /parents` shu telefon bilan → o'sha akkaunt tiklanadi (yangi parol, `deleted_at=null`);
   yoki `PATCH /parents/{id} {"is_active": true}`.
5. Audit: `parents.deleted_at` + konteyner logida `AUDIT parent_account_deleted parent_id=<id> mode=deactivated request_id=<id>`.
6. To'liq o'chirish faqat so'rov bo'yicha (privacy'dagi aloqa) — hozircha qo'lda, alohida jarayon belgilanmagan.
7. Review akkaunti (`PARENT_REVIEW_PHONE`): kirishda faqat xayoliy "TEST — App Review" o'quvchi qoldiriladi
   (haqiqiy o'quvchilar bog'lanishi uziladi); o'chirilsa — boshqa akkauntlar kabi kirish yopiladi, admin tiklaydi.

**Ochiq (huquqiy/release egasi):** Apple 5.1.1(v) akkaunt o'chirish ma'lumotni ham o'chirishini kutadi — faqat
kirishni yopish review'da rad etilishi mumkin. Privacy matni shu amaliyotga moslangan, lekin yurist tasdig'idan o'tmagan.

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
