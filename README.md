# Food Journal Telegram Bot

A private, self-hosted Telegram food journal built with Java 21 and Spring Boot.

Send a meal in English, Romanian, or mixed language. The bot records the meal, tracks nutrition, and sends daily summaries. It is designed for a small household, not public SaaS.

## Status

Initial repository scaffold. Application implementation is in progress; do not use this repository with production credentials yet.

## What it will do

- Log text, voice, photo, and document meal messages.
- Keep food entries private to each Telegram user.
- Search, correct, and delete entries.
- Send morning and evening daily reports in the user's timezone.
- Use AI only to interpret input; validated application code owns every database mutation.

## Stack

Java 21, Spring Boot, PostgreSQL, Flyway, Docker, Telegram webhooks, OpenAI, Gemini, and Open Food Facts.

## Quick start

1. Copy `.env.example` to `.env` and supply your own values.
2. Start PostgreSQL and the application with the documented Compose setup once it is added.
3. Configure a public HTTPS development tunnel and register the Telegram webhook. Coolify is intentionally deferred until the complete system is accepted.

See [local development](docs/local-development.md), [configuration](docs/configuration.md), and [deployment](docs/deployment-coolify.md).

## Security

Rotate any Telegram token that appeared in an n8n export before doing anything else. Never commit `.env`, production data, Telegram updates, or n8n exports. See [SECURITY.md](SECURITY.md).

## Documentation

- [Product and use cases](docs/product.md)
- [Requirements and acceptance criteria](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Current n8n migration findings](docs/n8n-migration.md)
- [Operations runbook](docs/operations.md)
- [Issue backlog](docs/issue-backlog.md)

## License

MIT. See [LICENSE](LICENSE).
