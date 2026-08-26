# Production Cutover & Deployment Runbook

This runbook guides operators through launching a new production instance of **Food Journal Messaging Bot** or executing a cutover from a legacy automation flow.

---

## 1. Pre-Deployment Checklist

Before registering the live webhook or enabling user traffic, ensure all prerequisites are met:

- [ ] Protected `master` commit passed the current Python and Docker CI checks.
- [x] PostgreSQL 16 database provisioned with persistent storage volume and daily backup schedule configured.
- [x] High-entropy `TELEGRAM_WEBHOOK_SECRET` generated.
- [ ] Bootstrap administrator ID configured in `ADMIN_TELEGRAM_USER_IDS`; keep the old `ALLOWED_TELEGRAM_USER_IDS` only until its grants are migrated.
- [x] Valid `OPENAI_API_KEY` supplied.
- [x] Public HTTPS endpoint (Coolify, Caddy, Traefik, or Cloudflare Tunnel) configured to forward `/webhook` to app port `8080`.

---

## 2. Execution Steps

### Step 1: Deploy Database & Run Migrations
1. Deploy PostgreSQL and the application container (`app`).
2. If the database already contains the PostgreSQL V1–V17 schema, run the Alembic revisions:
   ```text
   Alembic upgrade head completed successfully
   ```
   For a fresh database, first replay `python-app/alembic/flyway_baseline/V1__*.sql`
   through `V17__*.sql` in numeric order with `psql` from a controlled migration
   runner, then run `alembic upgrade head`. Never run the baseline replay against
   a non-empty production database.
3. Verify the Python management readiness probe returns HTTP 200 OK:
   ```bash
    curl -i http://localhost:8081/health/readiness
   ```

### Step 2: Register Telegram Webhook
Register the public HTTPS URL with Telegram using your bot token and secret header:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://your-domain.com/webhook",
           "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
         }'
```

Confirm Telegram response:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

### Step 3: Verify User Onboarding & Integration
1. Send `/start` from an allowlisted Telegram account. Set timezone (e.g. `Europe/Bucharest`) and daily calorie goal (e.g. `2000`).
2. Log a natural language test meal (e.g., `"2 eggs and coffee"`).
3. Send `/today` to verify entry persistence and pinned daily status message updates.
4. Verify `/undo` reverts the test entry cleanly.

---

## 3. Rollback & Emergency Procedures

If an operational anomaly occurs post-cutover:

1. **Disable Webhook Routing**: Remove the Telegram webhook or pause container ingress to prevent new update ingestion:
   ```bash
   curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook"
   ```
2. **Preserve PostgreSQL Volume**: Do **NOT** drop PostgreSQL database volumes or delete migration history during incident handling.
3. **Inspect Outbox & Logs**: Query `messaging_inbox`, `messaging_outbox`, and application logs to diagnose issues.
