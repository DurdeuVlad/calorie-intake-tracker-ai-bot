# n8n cutover and rollback runbook

## Hard preconditions

Do not begin cutover unless all are true:

- The exact protected `master` commit passed the [acceptance plan](acceptance-test-plan.md).
- The Telegram token exposed by the n8n export was rotated; the old token is invalid.
- Legacy schemas, secured export, and separate error workflow were assessed against [legacy import mapping](legacy-import-mapping.md). An import is optional; unreviewed legacy data is never imported.
- A tested PostgreSQL backup and isolated restore exist for the target database.
- A public HTTPS endpoint, a private management network, persistent PostgreSQL storage, runtime secrets, and backup retention have been prepared. This is a future Coolify configuration step, not authorization to connect it now.
- The user explicitly authorizes the production webhook switch.

## Cutover

1. Record the release commit, redacted backup location, and current Telegram webhook configuration outside Git.
2. Stop n8n from writing journal data. Do not operate the old and new systems as concurrent writers.
3. Deploy the release only after Coolify is explicitly authorized; confirm Flyway completion and private readiness.
4. Register the Telegram webhook once, using the HTTPS URL and the new webhook secret. Verify Telegram reports the expected URL without exposing the token in logs or shell history.
5. From one allowlisted test account, run `/start`, one text meal, `/today`, and a duplicate-update test. Check the outbox and application logs for safe delivery.
6. Observe the configured report schedule and health/metrics. Declare cutover complete only after the manual acceptance rows pass.

## Rollback

Rollback means stopping the new application and routing Telegram back to the previously known-good writer. It does **not** mean deleting PostgreSQL volumes or reversing Flyway migrations.

1. Disable the new webhook route and preserve logs, outbox rows, idempotency ledger, and database volume for diagnosis.
2. If the old n8n writer is still valid and contains the authoritative journal, register its webhook once. Otherwise leave the bot unavailable rather than risk dual writers.
3. If data repair is required, restore only to an isolated database and reconcile from there. Never overwrite the live journal with a dump during an incident.
4. Document the incident, token/webhook state, affected update IDs, and decision to retry cutover.

## Prohibited actions

- Do not connect Coolify before the acceptance gate passes and the user authorizes it.
- Do not commit exports, secrets, Telegram updates, backups, or live data.
- Do not run n8n and this service as simultaneous writers for the same household journal.
- Do not roll back schema migrations by deleting data.
