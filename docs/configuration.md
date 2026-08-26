# Configuration Reference

All canonical application settings are declared via environment variables and loaded by the Python `pydantic-settings` configuration.

---

## Complete Environment Variable Reference

### Core Database Configuration

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes | `jdbc:postgresql://localhost:5432/foodjournal` | PostgreSQL JDBC connection URL. |
| `DATABASE_USERNAME` | Yes | `foodjournal` | PostgreSQL database user. |
| `DATABASE_PASSWORD` | Yes | `foodjournal` | PostgreSQL database password. |

---

### Telegram Frontend Configuration

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Yes (if Telegram enabled) | *(none)* | Bot token provided by [@BotFather](https://t.me/BotFather). |
| `TELEGRAM_WEBHOOK_SECRET` | Yes (if Telegram enabled) | *(none)* | High-entropy string expected in `X-Telegram-Bot-Api-Secret-Token` header. |
| `ADMIN_TELEGRAM_USER_IDS` | Yes (if Telegram enabled) | *(empty)* | Comma-separated numeric Telegram IDs used only to bootstrap persistent administrators. |
| `ALLOWED_TELEGRAM_USER_IDS` | Migration only | *(empty)* | Deprecated legacy allowlist imported into persistent grants during migration. Remove after migration. |
| `TELEGRAM_FRONTEND_ENABLED` | No | `true` | Set `false` to disable the Telegram webhook adapter. |

---

### Mattermost Frontend Configuration

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `MATTERMOST_FRONTEND_ENABLED` | No | `false` | Set `true` to enable the Mattermost WebSocket listener frontend. |
| `MATTERMOST_INTERNAL_URL` | No | `http://mattermost:8065` | Base URL used by the app container to reach Mattermost API. |
| `MATTERMOST_PUBLIC_URL` | No | *(empty)* | Public site URL (e.g. Tailscale MagicDNS domain `https://food-chat.tailnet.ts.net`). |
| `MATTERMOST_BOT_TOKEN` | Yes (if Mattermost enabled) | *(empty)* | Personal Access Token created for the Mattermost bot user. |
| `MATTERMOST_BOT_USER_ID` | Yes (if Mattermost enabled) | *(empty)* | Mattermost internal user ID of the bot account. |
| `ALLOWED_MATTERMOST_USER_IDS` | Yes (if Mattermost enabled) | *(empty)* | Comma-separated list of authorized Mattermost user IDs. |

---

### OpenAI & AI Model Configuration

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Yes (for AI features) | *(empty)* | OpenAI API key credential. |
| `OPENAI_MODEL` | No | `gpt-5.6-luna` | Chat completions model for intent interpretation and tool calling. |
| `OPENAI_TRANSCRIPTION_MODEL` | No | `gpt-4o-mini-transcribe` | OpenAI model used for audio voice note transcription. |
| `AGENT_MAX_TOOL_CALLS` | No | `10` | Maximum tool-call turns per agent run; hard-capped at 10. |

---

### Web Lookup & External Tools

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `OPEN_FOOD_FACTS_BASE_URL` | No | `https://world.openfoodfacts.org/api/v2` | Open Food Facts v2 API base endpoint. |
| `SEARXNG_BASE_URL` | No | *(empty)* | Base URL of self-hosted SearxNG instance for `search_web` lookups (requires `formats: [json]` enabled in SearxNG `settings.yml`). |
| `BROWSERLESS_BASE_URL` | No | *(empty)* | Base URL of self-hosted Browserless headless Chrome instance for `fetch_web_page`. |
| `BROWSERLESS_TOKEN` | No | *(empty)* | Authentication token parameter for Browserless. |

---

### System, Scheduling, and Operations

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `DEFAULT_TIMEZONE` | No | `Europe/Bucharest` | Default IANA timezone used prior to user onboarding. |
| `MANAGEMENT_PORT` | No | `8081` | Private Python management port for health checks. |
| `FOOD_JOURNAL_SCHEDULING_ENABLED` | No | `true` | Set `false` to disable background report schedulers and outbox processing. |
| `FOOD_JOURNAL_OUTBOX_DELAY_MS` | No | `5000` | Outbox worker poll frequency in milliseconds. |

---

### Local Terminal Settings

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TERMINAL_TELEGRAM_USER_ID` | No | `123456789` | Simulated user ID (must be present in `ALLOWED_TELEGRAM_USER_IDS`). |
| `TERMINAL_DISPLAY_NAME` | No | `Local developer` | Display name for interactive terminal session. |
| `TERMINAL_EVAL_REPEATS` | No | `3` | Iterations per evaluation scenario when running automated prompt evals. |
| `TERMINAL_EVAL_SCENARIO` | No | *(empty)* | Name of single scenario to run (e.g. `single-meal-simple`). |
| `TERMINAL_EVAL_BASELINE_FILE` | No | *(empty)* | Path to a previous eval JSON output file to compare score deltas. |
| `TERMINAL_EVAL_FULL_REPORT` | No | `true` | Include unredacted input/response text in generated `eval-reports/`. |

---

## Secret Handling Guidelines

1. **Never Commit Secrets**: Never commit `.env` files, production credentials, API keys, or Telegram bot tokens into version control.
2. **Production Secret Injection**: In production (Docker Compose or Coolify), populate runtime variables strictly through container environment settings or secret vaults.
3. **Log Protection**: Application logging filters credentials, HTTP headers, raw prompt text, and original user messages.
