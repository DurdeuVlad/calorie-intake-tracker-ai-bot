# Project Milestones & Issue Backlog

---

## Completed Milestones (Production Release)

1. [x] **Bootstrap & Governance**: Python Docker architecture, FastAPI service, security scanning, and configuration template.
2. [x] **Database Schema & Migrations**: PostgreSQL 16+ baseline plus Alembic schema evolution.
3. [x] **Multi-Frontend Ingestion**: Telegram HTTPS Webhook API with secret header verification and Mattermost WebSocket client over Tailscale.
4. [x] **User Isolation & Idempotency**: Atomic update claiming (`messaging_inbox`), strict user-level authorization, and outbox messaging worker (`messaging_outbox`).
5. [x] **Onboarding & Pinned Status**: Timezone-aware user settings, daily calorie targets, and dynamic pinned daily status updates.
6. [x] **Natural Language & Vision Logging**: OpenAI interpretation (`gpt-5.6-luna`), audio transcription (`gpt-4o-mini-transcribe`), and image/document vision extraction.
7. [x] **External Tool Integrations**: Open Food Facts API (`CachedNutritionResolver`), self-hosted SearxNG web search (`SearxngClient`), and Browserless web scraping (`BrowserlessClient` with SSRF protection).
8. [x] **Reversible Undo System**: 10-minute snapshot change set undo (`JournalChangeSet` / `/undo`).
9. [x] **Timezone-Aware Reports**: Morning and evening scheduled report delivery with per-day deduplication (`report_deliveries`).
10. [x] **Interactive CLI & Eval Suite**: Terminal interactive profile and automated prompt evaluation framework (`evals/text-journal.json`).

---

## Future Roadmap & Enhancements

1. [ ] **Multi-Language Expansion**: Add native localization support for additional languages beyond English and Romanian.
2. [ ] **Micronutrient Tracking**: Expand macro tracking to include detailed micronutrients (sodium, fiber, sugar, saturated fats).
3. [ ] **Custom Export Tools**: Export user journal records to CSV, JSON, or HealthKit/Google Fit formats.

