# Minar Parents — CRM backend App Store release gate

> Draft backend work only. **Production server has not been accessed, deployed, or restarted.**
> Audit date: 2026-10-11. Do not merge without staging/production validation and privacy-owner approval.

## Implemented in this PR

1. `DELETE /parent/account` (public via `/api/parent/account` through Nginx), authenticated by an existing parent JWT:
   - Locks and rechecks the account row.
   - Deletes all related refresh tokens, parent-specific notifications and parent↔student links.
   - If no parent invoice exists, permanently deletes the account row.
   - If invoices exist, retains a non-login, **anonymized** invoice owner (`deleted-parent-<id>`, no phone/name/avatar/profile, random unusable password and `is_active=false`) to preserve ledger referential integrity. The student, attendance, grades, salary and payment history remain untouched.
   - Returns 204 only after database commit. On error rolls back; the iOS client must only clear session on success.
   - Old access tokens are rejected because parent is inactive/deleted, old refresh tokens no longer exist.
2. `POST /parent/children/{id}/pay` returns **503** after normal authorization and input checks instead of writing a fake invoice and returning a nonexistent `/stub/` checkout URL. **Payme, Click, Uzum are NOT integrated.**
3. Pytest covers parent account deletion success/authorization, existing refresh invalidation, invoice retention/anonymization and failure-closed checkout.

## Conditions before enabling the iOS Delete Account button

- Review the data-retention requirements for payments and minor students. An invoice still includes `student_id`; retention must be justified and disclosed in the public privacy policy.
- Decide whether the invoice owner tombstone approach meets current legal/compliance rules; alternatively migrate invoice references to a separate anonymized ledger with a retention schedule.
- Ensure the CRM website can explain parent data deletion and has a reliable privacy-contact channel.
- Run `pytest backend/tests/test_parent.py -q` and all backend tests in a staging environment; smoke-test the real endpoint with a **throwaway** parent+test student. Never test destructive deletion on a live customer's account.
- Confirm privacy policy coverage of minor student data, educational history, payment processors, retention and backups.
- Only after production backend deployment and verification set `ACCOUNT_DELETION_ENABLED=YES` in the Swift `Minar-Production` build. Apple's review team must have working test account access.
- No DB migration is required for this implementation; it uses existing schema.

## Real payment integration remains BLOCKED

The old implementation created `STUB-` invoices and invented a placeholder checkout URL. This is **disabled**; parents will see a temporary-unavailable message. A real provider integration needs:
- Merchant accounts and sandbox credentials managed in server secrets **not in Git**.
- Provider-issued checkout URLs, signature/transaction verification, callback authentication, amount/currency correctness, idempotency, expiry and replay protection.
- Atomic updates to invoice, receipt, `Payment` records and student debt after verified server-to-server callback.
- Tests for cancel, failure, duplicate callbacks, race with account deletion, payment return from external browser, and gateway outages.
- Separate legal review of App Store 3.1.3(e) (tuition for in-person teaching versus digital services).

Do not claim checkout is complete until all items are implemented and provider-certified.

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
3. GitHub Actions is configured to auto-deploy on pushes to `main` using `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`. It expects `/opt/it-hub`, while screenshot shows `/var/www/it-hub` — mismatch must be resolved BEFORE merging.
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
