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

## v2.0 — "Agent in your inbox"

**Milestone:** [v2.0 Agent in your inbox](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/milestone/7)

The bot stops feeling like a state machine with an LLM bolted on and starts feeling like a real AI agent. Progressive-disclosure prompts, model-driven replies, tool reorganization, and new capabilities.

### Phase 1 — Foundation (model-driven replies)

1. [x] [#97 — v2.0-1.1: Enrich tool results with receipt-ready structured data](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/97) (P0)
2. [x] [#98 — v2.0-1.2: Remove deterministic reply templates, model writes full replies](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/98) (P0, depends on 97)
3. [x] [#99 — v2.0-1.3: Remove context.romanian, model decides language fully](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/99) (P0, depends on 98)
4. [x] [#100 — v2.0-1.4: Update eval fixtures and tests for model-driven replies](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/100) (P0, depends on 97-99)

### Phase 2 — Progressive disclosure

5. [x] [#101 — v2.0-2.1: Split monolithic system prompt into core + capability docs](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/101) (P1, depends on 98)
6. [x] [#102 — v2.0-2.2: Add load_instructions(topic) tool for progressive disclosure](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/102) (P1, depends on 101)
7. [x] [#103 — v2.0-2.3: Add capability index to core system prompt](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/103) (P1, depends on 101-102)

### Phase 3 — Tool reorganization

8. [x] [#104 — v2.0-3.1: Group tools into categories](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/104) (P1, depends on 101)
9. [x] [#105 — v2.0-3.2: Split journal_tool_executor.py into focused tool modules](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/105) (P1, after Phases 1-2)

### Phase 4 — New capabilities

10. [x] [#106 — v2.0-4.1: Add get_weekly_summary tool](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/106) (P1, depends on 105)
11. [x] [#107 — v2.0-4.2: Add search_food_history tool](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/107) (P1, depends on 105)
12. [x] [#108 — v2.0-4.3: Add custom food aliases](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/108) (P1, depends on 105)

### Phase 5 — Safety, eval, and release

13. [x] [#109 — v2.0-5.1: Comprehensive eval suite for v2.0](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/109) (P0, depends on 100, 102, 106-108)
14. [x] [#110 — v2.0-5.2: Adversarial review of v2.0 changes](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/110) (P0, depends on all)
15. [x] [#111 — v2.0-5.3: ADR 0007 — Progressive disclosure architecture](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/111) (P1, write first)
16. [x] [#112 — v2.0-5.4: Update all source-of-truth docs for v2.0](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot/issues/112) (P1, done last)

### Execution order

```
Phase 1 (foundation)      → #97 → #98 → #99 → #100
Phase 2 (disclosure)      → #101 → #102 → #103
Phase 3 (reorganization)  → #104 → #105
Phase 4 (new capabilities)→ #106, #107, #108
Phase 5 (safety + release)→ #111 (write first), #109, #110, #112 (last)
```

Merge everything into the v2.0 branch, then merge v2.0 to master.

---

## Future Roadmap & Enhancements

1. [ ] **Multi-Language Expansion**: Add native localization support for additional languages beyond English and Romanian.
2. [ ] **Micronutrient Tracking**: Expand macro tracking to include detailed micronutrients (sodium, fiber, sugar, saturated fats).
3. [ ] **Custom Export Tools**: Export user journal records to CSV, JSON, or HealthKit/Google Fit formats.

