# Operations runbook

## Health and logs

Expose a liveness/readiness endpoint. Monitor startup/migration failures, webhook verification failures, rejected senders, AI-provider failures, Open Food Facts failures, duplicate-update rates, report failures, and database health. Do not log tokens, raw media, or full private messages.

## Backup and restore

Back up PostgreSQL daily with tested point-in-time or dump recovery. Keep backups encrypted and access-controlled. Test restore to an isolated database regularly. The database is the system of record; original media is intentionally unrecoverable.

## Incident response

If a credential leaks: rotate it, update Coolify, invalidate the old Telegram webhook/token where relevant, review logs, and document impact. If duplicate updates occur: preserve the idempotency ledger, pause retries if needed, and diagnose before manual repair.

## Cutover

Validate the new deployment using a test user, back up legacy data, register the new webhook once, and observe the first scheduled reports. Keep a reversible DNS/application route, but do not run both bot writers against the same user journal.
