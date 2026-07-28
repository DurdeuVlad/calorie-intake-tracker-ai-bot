# Configuration reference

| Variable | Required | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | yes | JDBC PostgreSQL connection URL |
| `DATABASE_USERNAME` / `DATABASE_PASSWORD` | yes | database credentials |
| `TELEGRAM_BOT_TOKEN` | yes | rotated bot token |
| `TELEGRAM_WEBHOOK_SECRET` | yes | value Telegram sends in webhook header |
| `ALLOWED_TELEGRAM_USER_IDS` | yes | comma-separated Telegram numeric user IDs |
| `PUBLIC_BASE_URL` | yes | public HTTPS webhook URL (development tunnel until final Coolify rollout) |
| `OPENAI_API_KEY` | yes for natural language | OpenAI credential |
| `GEMINI_API_KEY` | yes for voice/image/document | Gemini credential |
| `OPEN_FOOD_FACTS_BASE_URL` | no | API base URL; defaults to public instance |
| `REPORTS_ENABLED` | no | global report switch; defaults true |

All runtime secrets belong in local `.env` files until final deployment, then in Coolify environment configuration. They do not belong in GitHub Actions, application properties, Docker images, documentation examples, or logs.
