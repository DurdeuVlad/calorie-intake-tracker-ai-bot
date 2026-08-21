# Coolify Homelab Production Deployment

This guide outlines how to deploy **Food Journal Messaging Bot** on a self-hosted **Coolify** instance (or any PaaS/Docker container platform).

---

## Deployment Prerequisites

1. A running **Coolify** instance connected to your Git repository (GitHub/GitLab).
2. A managed PostgreSQL database service provisioned in Coolify (or external PostgreSQL instance).
3. Registered Telegram bot credentials (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`) and OpenAI API key (`OPENAI_API_KEY`).
4. Public HTTPS domain/URL routed via Coolify reverse proxy (Traefik/Caddy).

---

## Step-by-Step Deployment Procedure

### 1. Create Coolify Project & Application
- Select **New Resource** -> **Application** -> **GitHub Repository**.
- Select the `calorie-intake-tracker-ai-bot` repository and the `master` branch.
- Choose **Dockerfile** as the build mechanism.
- For the Python cutover, set the application **Base Directory / Build Context** to
  `/python-app` and the **Dockerfile** to `Dockerfile` (relative to that directory).
  This makes Coolify build `python-app/Dockerfile` while leaving the root Java
  `Dockerfile` intact for the legacy implementation. Do not point Coolify at the
  repository root until the Java-to-Python cutover has been intentionally completed.

### 2. Configure Environment Variables
In the Coolify Application Environment settings, populate all required variables (see [Configuration Reference](configuration.md)):

```env
DATABASE_URL=jdbc:postgresql://postgres-service:5432/foodjournal
DATABASE_USERNAME=foodjournal
DATABASE_PASSWORD=your-secure-db-password

TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_SECRET=your-random-webhook-secret
ADMIN_TELEGRAM_USER_IDS=123456789

OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5.6-luna
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe

DEFAULT_TIMEZONE=Europe/Bucharest
```

### 3. Health Check Configuration
Configure Coolify liveness/readiness health probes to point to the Python management port:
- **Port**: `8081`
- **Path**: `/health/readiness`
- **Interval**: `10s`

### 4. Deploy & Verify Alembic Migrations
- Click **Deploy** in Coolify.
- After the container is running, run `alembic upgrade head` once against the
  shared database (from the app container or a one-off migration job). If this
  is the first Python deployment and the database is still stamped at the
  baseline, this applies the persistent Telegram access-grants migration.
- Monitor application logs to confirm the container starts and the existing PostgreSQL
  schema is compatible. The Python image does not run the Java Flyway migrations;
  its baseline Alembic revision is intentionally a no-op against the existing V1–V17
  schema. Apply future Python migrations through the normal Alembic migration process.
  Verify readiness with:
  ```text
  GET http://<internal-host>:8081/health/readiness
  ```
- Confirm readiness returns a healthy status before registering the webhook.

The old `ALLOWED_TELEGRAM_USER_IDS` value is used only during migration to
preserve existing users. Set `ADMIN_TELEGRAM_USER_IDS` to the initial admin ID(s)
before the first Python deployment, then remove the deprecated allowlist after
confirming the grants table contains the expected users. In a private Telegram
chat, administrators can use `/adduser <numeric-id>` and `/removeuser
<numeric-id>`; these commands are ignored as management operations in group
chats and never echo user IDs.

### 5. Register Telegram Webhook
Once Coolify provisions the public HTTPS URL (e.g., `https://foodbot.yourdomain.com`), set your Telegram bot webhook:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://foodbot.yourdomain.com/webhook",
           "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
         }'
```

Verify Telegram response:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

### 6. Configure the GitHub Auto-Deploy Webhook
Coolify exposes a single, shared webhook endpoint (`/webhooks/source/github/events/manual`) that identifies the target application from the push payload and validates it against that application's own secret — so every app on the instance points at the same URL:

```
https://webhooks.<yourdomain>.com/webhooks/source/github/events/manual
```

In the repository's GitHub webhook settings, set this URL, content type `application/json`, and the app's manual webhook secret from Coolify's application settings. Use a stable ingress (a permanent named Cloudflare Tunnel, not an ephemeral quick tunnel) so deploys keep firing after reboots/restarts — a dead quick-tunnel URL here will fail silently (GitHub still reports the delivery, but every request 502s) and pushes will stop deploying without any error surfaced in the app itself.

---

## Operations & Upgrades

- **Stateless App Container**: The application container is non-root and read-only with a temporary `/tmp` mount. All persistent state lives in PostgreSQL.
- **Upgrades**: Pushing updates to `master` triggers zero-downtime redeployments in Coolify. Keep the Python application context and health-check settings attached to the Coolify application when upgrading.
