# Minar Parents: besh yangi imkoniyat — backend release

## API shartnomasi

All `/parent/*` routes require the parent's bearer access token; child-scoped routes return 404 when the child is not linked to that parent. Staff routes require an authenticated CRM attendance editor. Teachers can act only for their own current group; broader CRM roles use existing role dependencies.

| Capability | Endpoint | Contract |
|---|---|---|
| Push device | `POST /parent/push-devices` | `{ "token": "64 lowercase hex", "platform": "ios", "environment": "production" | "sandbox" }` → 204 |
| Remove device | `DELETE /parent/push-devices/{token}` | 204; a token owned by another parent is untouched |
| Preferences | `GET/PATCH /parent/notification-preferences` | Partial PATCH and full response: `attendance`, `schedule`, `payments`, `homework`, `announcements`, `weekly_summary`, `teacher_messages` booleans |
| Absence | `GET/POST /parent/children/{child_id}/absence-explanations` | POST `{lesson_date, group_name?, reason: sick|travel|family|other, note}`. A recorded absence is required. A rejected explanation can be resubmitted. Notes belong to the submitting guardian, even when two guardians share a child. |
| Weekly summary | `GET /parent/children/{child_id}/weekly-summary?week_start=YYYY-MM-DD` | Monday date; attendance from recorded lessons, homework and grade percentage from CRM, plus staff recommendation. |
| Teacher question | `GET/POST /parent/children/{child_id}/teacher-questions` | POST `{subject,body}`; response has `status` and `replies`. Each guardian sees only their own questions. |
| Verified receipt | `GET /parent/children/{child_id}/payments/{payment_id}/receipt` | Authenticated `application/pdf`, under 1 MB, only for this parent's provider-confirmed online invoice. Manual/refunded/unconfirmed payments return 404. PDF is an academy payment confirmation, **not** a fiscal/tax receipt. |

CRM staff workflow: `GET /parent-engagement/absence-explanations`, `PATCH /parent-engagement/absence-explanations/{id}` with `{status:approved|rejected,staff_note?}`; `GET /parent-engagement/teacher-questions`, `POST /parent-engagement/teacher-questions/{id}/replies` with `{body}`; `GET /parent-engagement/students`, `GET /parent-engagement/students/{id}/weekly-summary`, and `PUT /parent-engagement/students/{id}/weekly-recommendations/{monday}` with `{text}`.

`GET /parent/app-config` adds `push_enabled`, `absence_explanations_enabled`, `weekly_summary_enabled`, `teacher_questions_enabled`, `receipts_enabled`. All default to `false`; iOS should hide each module until enabled.

## Feature flags and events

The independent environment flags `PARENT_ABSENCE_EXPLANATIONS_ENABLED`, `PARENT_WEEKLY_SUMMARY_ENABLED`, `PARENT_TEACHER_QUESTIONS_ENABLED`, and `PARENT_RECEIPTS_ENABLED` control the four corresponding app-config values. API endpoints remain callable for authorized smoke tests when flags are false.

`PARENT_EVENT_NOTIFICATIONS_ENABLED=false` by default controls new schedule and homework event creation. `PARENT_DIGESTS_ENABLED=false` by default controls day 5/15 payment-status reminders and prior-week summary notifications. Both should remain false until in-app notification behavior has been reviewed with test data. Existing absence, grade and provider-confirmed payment events continue as before. APNs sends only a generic title/body plus a route and child ID; names, grades, debt, question content and transaction data never enter the push payload.

For production APNs, set `PARENT_PUSH_ENABLED=true`, `PARENT_APNS_TEAM_ID`, `PARENT_APNS_TOPIC`, `PARENT_APNS_PRODUCTION_KEY_ID`, `PARENT_APNS_PRODUCTION_KEY_PATH`, and `PARENT_PUSH_NOT_BEFORE_UTC=YYYY-MM-DDTHH:MM:SSZ`. The key file is outside the repo at `/var/www/it-hub/data/apns/`, readable by worker UID 1001 only. The cutoff is mandatory: without it push remains disabled; older in-app notifications are not replayed. TestFlight and App Store devices use the production APNs host. Optional separate sandbox key variables are `PARENT_APNS_SANDBOX_KEY_ID/PATH`; omit them until a sandbox key exists.

Push delivery retries APNs 429/5xx and network failures up to five attempts with backoff; documented invalid device tokens are removed. Parent account deletion removes registered devices. The iOS client removes the device token on logout; if offline, generic old alerts can continue until the token is reassigned or ages out after 90 days.

Account deletion erases the parent's profile name, phone, login, credential hash and avatar, and removes sessions, device tokens, preferences, notifications, OTP records, parent-child links, absence notes and teacher questions/replies. A non-identifying parent tombstone remains because provider invoices and accounting records reference its ID; student, group and transaction details in those financial records remain for reconciliation. CRM creation with the same phone creates a new parent ID, and CRM edit/reset/link endpoints reject the erased row. Public privacy copy in Uzbek, Russian and English describes these limits and states that backups and technical logs expire on their own retention schedule. Smoke-test deletion only with a disposable fictional account and verify that a paid invoice and provider transaction remain.

## Migration and rollback

The additive revision is `20261014a_parent_engagement`, based on `20261013a_parent_release_config`. It adds six tables and four push status columns to `parent_notifications`. Take a PostgreSQL backup before deployment. The additive schema is compatible with older application images, but image tag `5847152` has the old deactivation-only deletion handler and must not serve public traffic while account deletion is available. Restore an image that retains erasure behavior or patch that handler before restoring traffic. **Do not downgrade the database as the first rollback step:** the Alembic downgrade drops explanations, questions, replies, preferences, recommendations, tokens and push status. Downgrade only after data export and an explicit decision to discard those records.

Production deployment uses `/var/www/minar-stack/scripts/deploy.sh` against the committed isolated worktree. Build/API/frontend and migration must pass before enabling flags. Smoke-test with fictional App Review data only; do not create a real charge. For receipts, use an already provider-confirmed fictional payment if one exists. Verify teacher role scope and the parent-visible result after staff approval/reply/recommendation. APNs delivery requires a registered **production** device token; key validity alone does not prove delivery.
