# Food Journal AI Bot

> 🥗 **Zero-friction, privacy-first AI nutrition & calorie tracker for Telegram and Mattermost.**  
> *Log meals naturally via text, voice notes, photos, or nutrition labels. The canonical implementation is Python 3.11+ with FastAPI, PostgreSQL, OpenAI, Open Food Facts, SearxNG, and Browserless.*

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](python-app/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-ready-009688.svg)](python-app/app/main.py)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%2B-blue.svg)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Ready-blue.svg)](python-app/compose.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

The Java implementation is maintained separately in the [Java sister repository](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot-java). It is not a second implementation path in this repository.

---

### Why Food Journal AI Bot?

- 🚀 **Zero-Friction Logging**: Forget tapping through 10 screens in MyFitnessPal or LoseIt. Send a 5-second voice message, take a picture of your plate, or text *"2 poached eggs on sourdough with avocado"*.
- 🔒 **100% Private & Self-Hosted**: Run on your own homelab or server. Original audio files, photos, and label documents are processed in-memory and destroyed immediately after extraction. No ad-tracking, no cloud database lock-in.
- 🧠 **AI Reasoning + Industrial Transaction Safety**: OpenAI (`gpt-5.6-luna` / `gpt-4o-mini-transcribe`) acts strictly as an interpretation engine. Validated Python domain code owns every PostgreSQL mutation, macro calculation, and schema integrity check.
- ↩️ **10-Minute Instant Undo**: Made a typo or logged the wrong meal? Just say *"undo that"* or run `/undo` to revert previous message mutations in one click.
- 🌐 **Telegram & Mattermost Integration**: Use Telegram via webhooks or run privately on Mattermost over **Tailscale Serve**. Seamlessly link identities across frontends with `/link`.
- 🔍 **Autonomous Tool Ecosystem**: Automatically queries **Open Food Facts API** for official product barcodes, performs self-hosted web search via **SearxNG** for menu nutrition, and scrapes web pages via **Browserless** with strict SSRF guards.

---


## The Problem

- **High-Friction Manual Logging**: Traditional fitness apps (MyFitnessPal, LoseIt) force you to search bloat-filled databases, select exact portion sizes, and tap through multiple screens for every single snack or meal.
- **Privacy & Data Monetization**: Commercial apps monetize your dietary patterns and health metrics, while storing raw voice recordings and meal photos on external servers indefinitely.
- **Fragile Automations**: Low-code workarounds (such as n8n or Make workflows) quickly break when handling complex multi-item meals, lack transactional safety, duplicate entries on webhook retries, and mix application state into visual node boxes.

---

## The Solution

**Food Journal Messaging Bot** bridges the gap between natural human conversation and robust, database-backed nutrition tracking:

1. **Natural Language Messaging**: Text, speak, or take a picture of your food in English, Romanian, or mixed language.
2. **AI Reasoning + Deterministic Execution**: OpenAI (`gpt-5.6-luna` / `gpt-4o-mini-transcribe`) acts strictly as an interpretation engine. It invokes structured tools to look up nutrition, while validated Python application code owns every database mutation.
3. **Multi-Frontend Support**: Run over **Telegram** (via HTTPS webhooks) or private **Mattermost** (via WebSocket over Tailscale). Link accounts seamlessly with `/link`.
4. **Rich Tool Ecosystem**:
   - **Open Food Facts API**: Resolves official barcodes and branded product nutrition.
   - **SearxNG Web Search**: Self-hosted web search for restaurant menus and meal nutrition.
   - **Browserless Web Scraping**: Fetches web page content with strict SSRF protections.
5. **Data Integrity & Reversible Undo**: 
   - Strict per-user isolation enforced at application and database layers.
   - 10-minute reversible change sets: mistake in logging? Undo instantly with `/undo` or natural language.
   - Idempotent webhook processing and outbox queue pattern prevent duplicate writes during network retries.
6. **Privacy First**: Zero retention of original uploaded media. Voice notes and meal photos are processed and immediately discarded.
7. **Daily Summaries**: Automatically pinned live daily status message plus scheduled morning and evening reports delivered in each user's local timezone.

---

## Architecture Stack

- **Core**: Python 3.11+, FastAPI, asyncio, SQLAlchemy, PostgreSQL 16+, Alembic
- **AI & Vision**: OpenAI Chat Completions (`gpt-5.6-luna`), OpenAI Audio (`gpt-4o-mini-transcribe`), Vision/Media Extraction
- **Integrations**: Open Food Facts API, SearxNG (JSON search API), Browserless (headless chrome fetching)
- **Frontends**: Telegram Bot Webhook API, Mattermost Client WebSocket Engine, Interactive CLI Terminal
- **Deployment**: Python Docker image, Docker Compose, Coolify-ready, non-root read-only container architecture

---

## Quick Start

### 1. Configure Environment

Copy `python-app/.env.example` to `python-app/.env` and fill in your credentials:

```bash
cp python-app/.env.example python-app/.env
```

Key required variables:
- `DATABASE_PASSWORD`: Strong password for PostgreSQL.
- `TELEGRAM_BOT_TOKEN`: Token from [@BotFather](https://t.me/BotFather).
- `TELEGRAM_WEBHOOK_SECRET`: High-entropy random secret header for webhook verification.
- `ADMIN_TELEGRAM_USER_IDS`: Comma-separated bootstrap administrator Telegram IDs. Runtime user access is stored in PostgreSQL and managed with private-chat `/adduser <id>` and `/removeuser <id>` commands.
- `OPENAI_API_KEY`: OpenAI secret API key.

### 2. Run with Docker Compose

Start PostgreSQL, the Python application, and the optional Mattermost services:

```bash
docker compose -f python-app/compose.yaml up --build -d
```

Check system health on the internal management port:
```bash
docker compose -f python-app/compose.yaml exec app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health/readiness').read()"
```

### 3. Local Interactive Terminal Chat

Test the bot locally without exposing a Telegram webhook:

```powershell
Push-Location python-app
python -m app.terminal.repl
Pop-Location
```

Type natural language meals directly into the CLI console. Use `:help`, `:trace on`, `:trace off`, or `:quit` for interactive debugging.

---

## Documentation Index

- [Product & Use Cases](docs/product.md): Vision, user pain points, input modes, and core workflows.
- [Architecture](docs/architecture.md): System components, data flow, tool execution, security, and outbox delivery.
- [Configuration Reference](docs/configuration.md): Complete guide to all application properties and environment variables.
- [Data Model](docs/data-model.md): Detailed schema description for the PostgreSQL baseline and Alembic revisions.
- [Requirements & Acceptance Criteria](docs/requirements.md): Business rules, transaction safety, and acceptance gates.
- [Local Development Guide](docs/local-development.md): Workspace setup, terminal mode, prompt evals, and testing.
- [Mattermost & Tailscale Setup](docs/mattermost-tailscale.md): Private frontend installation, Tailscale Serve, and account linking.
- [Coolify Deployment Runbook](docs/deployment-coolify.md): Production deployment on private homelab infrastructure.
- [Operations Runbook](docs/operations.md): Health checks, private metrics, backup/restore scripts, and incident response.
- [Acceptance Test Plan](docs/acceptance-test-plan.md): Pre-release automated & manual test suite verification.
- [Local Agent System](docs/agent-system.md): Routing map for agent instructions, source-of-truth docs, skills, and handoffs.
- [Agent Quality Control System](docs/agent-quality-control-checklist.md): Goals, constraints, agent lifecycle, quality gates, local skills, prompts, docs, and rollout checklist.
- [Agent Handoff Template](docs/agent-handoff-template.md): Required evidence and risk report for non-trivial tasks.
- [Cutover Runbook](docs/cutover-runbook.md): Launch and migration instructions.
- [n8n Migration Assessment](docs/n8n-migration.md): Technical analysis and findings from legacy low-code migration.
- [Issue Backlog](docs/issue-backlog.md): Milestone progress and roadmap features.

---

## Security & Privacy

- **Allowlist Enforcement**: Non-allowlisted user IDs are rejected at the edge before any processing.
- **Zero Media Storage**: Images and audio are processed transiently in-memory/tmpfs and never stored on disk or database.
- **SSRF Protection**: Web scraping via Browserless validates target hostnames and blocks internal/private IP subnets.
- See [SECURITY.md](SECURITY.md) for vulnerability reporting guidelines.

---

## License

[MIT License](LICENSE).
