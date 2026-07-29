# Operations runbook

## Health, metrics, and logs

The public application endpoint exposes `GET /health`, which returns only `ok`. Spring Actuator runs on the internal management port (`8081` by default), deliberately not published by Compose: `GET /actuator/health/liveness`, `GET /actuator/health/readiness`, and `GET /actuator/prometheus` are available from inside the application container or a private monitoring network. Do not expose the management port through a public reverse proxy.

Docker uses readiness for its health check. A container is ready only after the application and database health contributors are healthy. The service also uses graceful shutdown with a 30-second phase timeout; stop the application before PostgreSQL during planned maintenance.

## Admin observability

`/admin` requires the local bootstrap administrator and `/api/v1` requires a scoped API key; keep both behind HTTPS. Detailed traces expire after 14 days and exclude prompts, chain-of-thought, raw media, and credentials. Without `ADMIN_TRACE_ENCRYPTION_KEY`, private input/reply retention fails closed while safe metadata remains available.

Collect container stdout/stderr and the Prometheus endpoint privately. Alert on startup or Flyway failures, readiness failures, webhook verification failures, rejected senders, AI-provider and Open Food Facts failures, duplicate-update rates, report delivery failures, outbox retry age, and database health. Do not log tokens, raw media, or full private messages.

Compose retains at most three 10 MB JSON log files per application container. This is only a local guardrail, not a replacement for centralized log retention.

## Backup and restore

Back up PostgreSQL daily with tested point-in-time or dump recovery. Keep backups encrypted and access-controlled. The database is the system of record; original media is intentionally unrecoverable.

For local Compose, run `bash docker/backup-postgres.sh` to create a timestamped, plain-SQL dump under `backups/`. It writes to a restrictive temporary file and publishes the final filename only after `pg_dump` succeeds. Restore only into the separate `foodjournal_restore` database with `RESTORE_CONFIRM=foodjournal_restore bash docker/restore-postgres.sh backups/<dump>.sql`. The restore helper rejects `foodjournal` and recreates only its named restore target; choose another safe target with both `RESTORE_DATABASE=<name>` and a matching `RESTORE_CONFIRM=<name>`. Test restore at least quarterly, verify Flyway's schema history and a sample of journal entries, then securely delete the temporary restore database. Never restore a dump over a live service as an incident shortcut.

## Incident response

If a credential leaks: rotate it locally (and later in Coolify), invalidate the old Telegram webhook/token where relevant, review logs, and document impact. If duplicate updates occur: preserve the idempotency ledger, pause retries if needed, and diagnose before manual repair.

## Cutover

Validate the new deployment using a test user, back up legacy data, register the new webhook once, and observe the first scheduled reports. Keep a reversible DNS/application route, but do not run both bot writers against the same user journal.
