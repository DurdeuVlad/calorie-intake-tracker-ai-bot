# Food Journal AI Bot

> **The AI food journal that lives in your Telegram.**  
> Log meals by text, voice, photo, or nutrition label. Get instant calorie totals, daily summaries, and budget alerts — all through natural conversation. Self-hosted, privacy-first, zero ad-tracking.

[![CI](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/actions/workflows/python-ci.yml/badge.svg)](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/actions/workflows/python-ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](python-app/pyproject.toml)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-blue.svg)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Ready-blue.svg)](python-app/compose.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![302 tests passing](https://img.shields.io/badge/tests-302%20passing-brightgreen.svg)](python-app/tests)

---

## Why this bot?

Most calorie trackers are forms with food databases. This one is a conversation.

| You do this | The bot does that |
|---|---|
| Send *"2 poached eggs on sourdough with avocado"* | Logs it with estimated calories |
| Send a voice note saying what you ate | Transcribes, estimates, logs |
| Send a photo of your plate or a nutrition label | Reads it, extracts calories, logs |
| Say *"cate calorii azi?"* | Shows your daily total vs target |
| Say *"undo that"* | Reverts the last change (10-minute window) |
| Say *"make my day start at 4am"* | Configures your tracking day boundary |
| Report a bug conversationally | Saves it as feedback and learns from it |

**No apps to install. No databases to search. No forms to fill. Just talk.**

---

## What makes it different

### Trust-the-model architecture (v2.0)

The bot is built around a capable AI agent (`gpt-5.6-luna` via LiteLLM proxy), not a state machine with NLP bolted on. The model sees exactly what you send — no rewriting, no preprocessing, no deterministic guards that second-guess it. It decides when to clarify, estimate, log, search, or just talk.

Application code owns what matters: authorization, validation, calculations, transactions, undo, and ownership. The model owns the conversation.

### Privacy-first, self-hosted

- Original voice, photos, and documents are processed in-memory and destroyed immediately — never stored
- Runs on your own server via Docker Compose (PostgreSQL 17, Redis 7, LiteLLM, app)
- No ad-tracking, no cloud lock-in, no data monetization
- SSRF-protected web scraping, read-only root filesystem, `no-new-privileges` container hardening

### Production-grade reliability

- **302 automated tests** (unit + integration), CI green on every PR
- 10-minute reversible undo on every journal mutation
- Idempotent webhook processing (Telegram `update_id` dedup)
- Outbox queue pattern for reliable message delivery
- Self-migrating container (Alembic runs on boot, zero manual migration steps)
- Health checks (liveness + readiness), graceful shutdown, bounded logging

### Features that matter

- **Multi-input logging**: text, voice notes, photos, printed nutrition labels
- **Natural language editing**: *"delete the coffee"*, *"move lunch to yesterday"*, *"change the pasta to 350 kcal"*
- **Smart estimation**: searches Open Food Facts, SearxNG, and web pages before falling back to AI estimation
- **Custom food aliases**: *"cafea"* → your specific coffee with milk, calories included
- **Day-boundary settings**: late-night snacks count toward today, not tomorrow, if you want
- **Budget alerts**: get notified when you cross your calorie target
- **Tracking nudges**: gentle reminders if you haven't logged a meal
- **Weekly summaries**: 7-day calorie trends with daily averages
- **Feedback learning**: the bot remembers what went wrong and adjusts
- **Multi-language**: Romanian, English, or mixed — the model handles it
- **Telegram + Mattermost**: Telegram via webhooks, Mattermost via Tailscale Serve

---

## Quick Start

### 1. Configure

```bash
cp python-app/.env.example python-app/.env
```

Fill in: `DATABASE_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `ADMIN_TELEGRAM_USER_IDS`, `OPENAI_API_KEY`.

### 2. Launch

```bash
docker compose -f python-app/compose.yaml up --build -d
```

The app self-migrates the database on boot. Check readiness:

```bash
docker compose -f python-app/compose.yaml exec app python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8081/health/readiness').read()"
```

### 3. Try it locally (no Telegram needed)

```bash
cd python-app
python -m app.terminal.repl
```

Type meals directly: *"2 eggs and coffee"*, *"cate calorii azi?"*, *":help"*.

### 4. Register the webhook

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook", "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"}'
```

---

## Architecture

```
Telegram/Mattermost → FastAPI webhook → JournalApplicationService
                                              ↓
                                    JournalAgent (ReAct loop)
                                     ↙           ↘
                            OpenAI model      JournalToolExecutor
                            (gpt-5.6-luna        ↙  ↓  ↘
                             via LiteLLM)   journal  settings  feedback
                                              actions   tools     tools
                                                  ↓
                                            PostgreSQL 17
                                            (Alembic migrations)
```

- **Core**: Python 3.11+, FastAPI, asyncio, SQLAlchemy, PostgreSQL 17, Alembic
- **AI**: `gpt-5.6-luna` (chat), `gpt-4o-mini-transcribe` (voice) via LiteLLM proxy
- **Integrations**: Open Food Facts, SearxNG, Browserless (SSRF-protected)
- **Frontends**: Telegram webhooks, Mattermost WebSocket, interactive CLI terminal
- **Deployment**: Docker Compose, Coolify-ready, non-root read-only container

---

## Documentation

**For developers:**
- [Architecture](docs/architecture.md) — system components, data flow, tool execution
- [Data Model](docs/data-model.md) — PostgreSQL schema, migrations, constraints
- [Configuration](docs/configuration.md) — all environment variables
- [Local Development](docs/local-development.md) — workspace setup, terminal mode, testing
- [Cutover Runbook](docs/cutover-runbook.md) — production deployment steps

**For agents (AI assistants working on this repo):**
- [AGENTS.md](AGENTS.md) — non-negotiable rules, verification, handoff
- [Agent System](docs/agent-system.md) — routing map for agent tasks
- [Agent QC Checklist](docs/agent-quality-control-checklist.md) — quality gates
- [Handoff Template](docs/agent-handoff-template.md) — required evidence for non-trivial tasks
- [ADR 0007](docs/adr/0007-progressive-disclosure-agent.md) — progressive disclosure architecture

**For operators:**
- [Operations](docs/operations.md) — health, backup, incident response
- [Product Vision](docs/product.md) — user goals and use cases

**Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## Security & Privacy

- **Allowlist enforcement**: non-allowlisted users rejected at the edge
- **Zero media storage**: images/audio processed in-memory, never persisted
- **SSRF protection**: Browserless validates hostnames, blocks private IPs
- **Per-user isolation**: FK constraints + application-level ownership checks
- See [SECURITY.md](SECURITY.md) for vulnerability reporting

---

## License

[MIT](LICENSE).
