# Configuration reference

| Variable | Required | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | yes | JDBC PostgreSQL connection URL |
| `DATABASE_USERNAME` / `DATABASE_PASSWORD` | yes | database credentials |
| `TELEGRAM_BOT_TOKEN` | yes | rotated bot token |
| `TELEGRAM_WEBHOOK_SECRET` | yes | value Telegram sends in webhook header |
| `ALLOWED_TELEGRAM_USER_IDS` | yes | comma-separated Telegram numeric user IDs |
| `OPENAI_API_KEY` | yes for natural language | OpenAI credential |
| `GEMINI_API_KEY` | yes for voice/image/document | Gemini credential |
| `GEMINI_MODEL` | no | Gemini multimodal model; defaults to `gemini-3.6-flash` |
| `OPENAI_TRANSCRIPTION_MODEL` | no | OpenAI fallback speech-to-text model; defaults to `gpt-4o-mini-transcribe` |
| `DEFAULT_TIMEZONE` | no | IANA timezone used until a user completes onboarding; defaults to `Europe/Bucharest` |
| `OPENAI_MODEL` | no | OpenAI chat-completions model; defaults to `gpt-5.4-mini` |
| `AGENT_MAX_TOOL_CALLS` | no | maximum tool calls in one agent run; capped at `10` |
| `OPEN_FOOD_FACTS_BASE_URL` | no | Open Food Facts API base URL, including `/api/v2`; defaults to the public API |
| `MANAGEMENT_PORT` | no | local-only Actuator port; defaults to `8081` |
| `FOOD_JOURNAL_SCHEDULING_ENABLED` | no | set `false` to disable outbox and report schedulers; defaults to `true` |
| `FOOD_JOURNAL_OUTBOX_DELAY_MS` | no | polling delay for Telegram outbox and pinned-status delivery; defaults to `5000` ms |

There is no global `REPORTS_ENABLED` setting: reports are enabled or disabled per user in `/settings`. `PUBLIC_BASE_URL` is not consumed by the application; register the Telegram webhook separately only when the final deployment is ready.

All runtime secrets belong in local `.env` files until final deployment, then in Coolify environment configuration. They do not belong in GitHub Actions, application properties, Docker images, documentation examples, or logs.
