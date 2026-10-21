# Isolated Paycom certification endpoint

The Paycom Web-cashbox sandbox endpoint is independently editable in Payme
Business Developer Tools. Set it to
`https://crm.minaracademy.uz/api/payme-sandbox` only after the isolated service
and reverse proxy are healthy. The separate active virtual-terminal cashbox
must retain its production endpoint and key.

## Boundaries

- `backend.paycom_sandbox_app` serves only `POST /payme` and a loopback-only
  health check. It refuses to start unless `PAYCOM_SANDBOX_MODE=enabled`, the
  database name is exactly `paycom_sandbox`, and the Paycom account field is
  `order_id` (matching this Web-cashbox).
- The sandbox must have its own PostgreSQL role and database. It must never
  reuse the live CRM `DATABASE_URL`, live payment key, or parent data. Put its
  credentials in `/var/www/minar-stack/env/paycom-sandbox.env` with mode 0600;
  do not put credentials in Git, shell history, or terminal output.
- Save the test cashbox merchant ID and **test_key** in separate root-readable
  files with mode 0600. Run `deploy/provision_paycom_sandbox.py` on the server:

  ```sh
  sudo python3 deploy/provision_paycom_sandbox.py \
    --db-container <postgres-container> --pg-user <postgres-superuser> \
    --db-host <docker-db-service> \
    --merchant-id-file /root/paycom-merchant-id \
    --test-key-file /root/paycom-test-key
  ```

  It creates only a new `paycom_sandbox` database and `paycom_sandbox_role`,
  refusing any existing role, database, or env file. It writes a mode 0600
  `paycom-sandbox.env`, with sandbox-only `DATABASE_URL`, `PAYME_KEY=test_key`,
  `PAYME_ACCOUNT_FIELD=order_id`, refunds enabled, and all CRM payments and
  schedulers disabled. Never use the live `PAYME_KEY` or CRM database URL.
- Do **not** apply the full CRM Alembic chain to a fresh sandbox database. Its
  existing `20260826b_metodist_to_support_teacher` revision exceeds Alembic's
  default `version_num varchar(32)` and fails on fresh PostgreSQL. Instead,
  run `python -m backend.scripts.init_paycom_sandbox_db` once through a Compose
  `run --rm --no-deps --entrypoint python paycom-sandbox -m ...` command. This
  refuses nonempty databases and installs the current model schema plus only
  required system rows. Then run the same Compose `run` command with
  `backend.scripts.create_paycom_sandbox_invoices --amount 7000 --count 6`.
  The command prints disposable
  `{order_id: ...}` account values and the amount in tiyin. Use one new account
  per Create/Perform/Cancel scenario. Generate fresh ones when they expire.

## Deployment order

1. Pin and load the reviewed backend image. Provision the isolated database,
   role, and env file. Keep the live CRM Compose service running.
2. Copy these four files from this reviewed commit into
   `/var/www/minar-stack/paycom-sandbox-code/` as regular, read-only files:
   `backend/parent/payments/payme.py`, `backend/paycom_sandbox_app.py`,
   `backend/scripts/init_paycom_sandbox_db.py`, and
   `backend/scripts/create_paycom_sandbox_invoices.py`. Match their SHA-256
   hashes on Mac and server before starting. This overlays the installed
   `8178fe0` image without rebuilding on the I/O-sensitive production VM.
   Ensure every mount source exists as a **file** before invoking Compose.
3. Place `paycom-sandbox.compose.yml` beside the stack's existing compose file.
   With both Compose files, run the one-time sandbox database initializer and
   create fresh invoices, then start only `paycom-sandbox`. Its
   `entrypoint` explicitly starts `backend.paycom_sandbox_app`, bypassing the
   image's normal CRM entrypoint and migrations. The container binds only to
   `127.0.0.1:8011` and has a 256 MiB memory limit.
4. Add `paycom-sandbox.nginx.conf` inside the existing CRM HTTPS server block,
   run `nginx -t`, then reload Nginx. The exact location exposes only Paycom's
   POST callback. Existing `/api/` requests still route to the live CRM API.
5. Verify `/readyz` through loopback and verify that an unauthenticated POST to
   the public sandbox URL returns Paycom JSON-RPC error `-32504` over HTTP 200.
6. Change the **inactive Web-cashbox** test Endpoint URL in Payme Business and
   run its test panel. Keep a record of each scenario and resulting transaction
   state. Roll back the endpoint URL if the sandbox service is unhealthy.

The production deployment currently points its checkout at the real Paycom
checkout while using the Web-cashbox test key. Fix the active production
merchant ID/key/endpoint pairing separately before claiming real Payme payments
work; do not copy the test key into the production callback after certification.
