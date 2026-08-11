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

### 2. Configure Environment Variables
In the Coolify Application Environment settings, populate all required variables (see [Configuration Reference](configuration.md)):

```env
DATABASE_URL=jdbc:postgresql://postgres-service:5432/foodjournal
DATABASE_USERNAME=foodjournal
DATABASE_PASSWORD=your-secure-db-password

TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_SECRET=your-random-webhook-secret
ALLOWED_TELEGRAM_USER_IDS=123456789,987654321

OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe

DEFAULT_TIMEZONE=Europe/Bucharest
```

### 3. Health Check Configuration
Configure Coolify liveness/readiness health probes to point to the Spring Actuator port:
- **Port**: `8081`
- **Path**: `/actuator/health/readiness`
- **Interval**: `10s`

### 4. Deploy & Verify Flyway Migrations
- Click **Deploy** in Coolify.
- Monitor application logs to confirm Flyway migration execution:
  ```text
  Successfully applied 17 migrations to schema "public"
  ```
- Confirm readiness check passes (`UP`).

### 5. Register Telegram Webhook
Once Coolify provisions the public HTTPS URL (e.g., `https://foodbot.yourdomain.com`), set your Telegram bot webhook:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://foodbot.yourdomain.com/telegram/webhook",
           "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
         }'
```

Verify Telegram response:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

---

## Operations & Upgrades

- **Stateless App Container**: The application container is non-root and read-only with a temporary `/tmp` mount. All persistent state lives in PostgreSQL.
- **Upgrades**: Pushing updates to `master` triggers zero-downtime redeployments in Coolify. Flyway executes new migrations automatically upon startup.

