# Operations runbook

## Health, metrics, and logs

The public application endpoint exposes `GET /health`, which returns only `ok`. Spring Actuator runs on the internal management port (`8081` by default), deliberately not published by Compose: `GET /actuator/health/liveness`, `GET /actuator/health/readiness`, and `GET /actuator/prometheus` are available from inside the application container or a private monitoring network. Do not expose the management port through a public reverse proxy.

Docker uses readiness for its health check. A container is ready only after the application and database health contributors are healthy. The service also uses graceful shutdown with a 30-second phase timeout; stop the application before PostgreSQL during planned maintenance.

Collect container stdout/stderr and the Prometheus endpoint privately. Alert on startup or Flyway failures, readiness failures, webhook verification failures, rejected senders, AI-provider and Open Food Facts failures, duplicate-update rates, report delivery failures, outbox retry age, and database health. Do not log tokens, raw media, or full private messages.

Compose retains at most three 10 MB JSON log files per application container. This is only a local guardrail, not a replacement for centralized log retention.

## Backup and restore

Back up PostgreSQL daily with tested point-in-time or dump recovery. Keep backups encrypted and access-controlled. The database is the system of record; original media is intentionally unrecoverable.

For local Compose, run `bash docker/backup-postgres.sh` to create a timestamped, plain-SQL dump under `backups/`. It writes to a restrictive temporary file and publishes the final filename only after `pg_dump` succeeds. Restore only into the separate `foodjournal_restore` database with `RESTORE_CONFIRM=foodjournal_restore bash docker/restore-postgres.sh backups/<dump>.sql`. The restore helper rejects `foodjournal` and recreates only its named restore target; choose another safe target with both `RESTORE_DATABASE=<name>` and a matching `RESTORE_CONFIRM=<name>`. Test restore at least quarterly, verify Flyway's schema history and a sample of journal entries, then securely delete the temporary restore database. Never restore a dump over a live service as an incident shortcut.

## Incident response

If a credential leaks: rotate it locally (and later in Coolify), invalidate the old Telegram webhook/token where relevant, review logs, and document impact. If duplicate updates occur: preserve the idempotency ledger, pause retries if needed, and diagnose before manual repair.

### 2026-08-23: daily-status flood-control storm delaying all Telegram replies

**Symptom:** replies from the bot arrived with delays ranging from minutes to hours; Grafana/alertmanager reported the service as degraded even though the container was `Up (healthy)` and Coolify itself (proxy, db, redis, sentinel) was fully up.

**Cause:** `daily_status_dispatcher.py` (the provider-neutral per-turn status editor, distinct from the Telegram-only pinned status) left a failed row `dirty=True` on any exception and logged only — no lease or backoff. Its `run_forever()` loop only sleeps when `dispatch_once()` finds nothing to claim, so a persistently failing row (one chat, `EditMessageText` failing repeatedly) was reclaimed and retried on effectively every event-loop tick with no delay. In the Java predecessor this was throttled by `@Scheduled(fixedDelay=...)`, which enforces a floor between invocations regardless of outcome; the asyncio port dropped that floor for the failure path. Over ~2 hours this produced 42,908 failed dispatch attempts against a single chat, which drove Telegram's per-bot flood control from single-digit-second backoffs up to an 86-minute `retry_after` — and because Telegram rate limits are shared per-bot, that storm delayed delivery for every other chat too, not just the stuck one.

**Fix:** `MessagingDailyStatus.retry()` now clears `dirty` on failure instead of leaving the row eligible for immediate reclaim, mirroring the give-up-rather-than-loop-forever semantics `PinnedDailyStatus.retry()` already uses for the same class of problem. This is safe because `messaging_daily_status_service.refresh()` re-marks the row dirty with fresh text on the very next inbound message from that user, so delivery is naturally retried rather than busy-looped. See `app/messaging/daily_status_dispatcher.py` and `app/db/models/messaging.py`.

## Cutover

Validate the new deployment using a test user, back up legacy data, register the new webhook once, and observe the first scheduled reports. Keep a reversible DNS/application route, but do not run both bot writers against the same user journal.
