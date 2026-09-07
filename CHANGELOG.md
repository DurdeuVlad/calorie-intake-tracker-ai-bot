# Changelog

All notable changes to this project are documented here. Dates are in UTC.

## v2.0 — 2026-09-07

### The "Agent in your inbox" release

A complete rewrite of the bot's brain: from deterministic state-machine logic to a trust-the-model agent architecture. The model now writes every reply, decides when to clarify vs estimate vs log, and drives onboarding through natural conversation — no if-else stage branches.

### Added

- **Trust-the-model architecture**: the model sees exactly what the user sends. No application-side rewriting, no deterministic semantic guards, no hidden instructions. The model is treated as an agent with authority over conversation; application code owns authorization, validation, mutations, and transactions.
- **Agent-driven onboarding**: `/start` routes through the agent, which greets, explains what the bot does (text/voice/photo logging), and collects name, timezone, and calorie target naturally via `update_settings`. Removed `onboarding_prompt()` and `continue_onboarding()` if-else functions.
- **LiteLLM proxy**: configurable `OPENAI_BASE_URL` with a LiteLLM proxy service in the Docker Compose stack. Production model: `gpt-5.6-luna` (~$0.20/1M input, ~$1.20/1M output). Transcription: `gpt-4o-mini-transcribe`.
- **Feedback system with learning**: users can report bugs conversationally or via `/feedback` and `/bug`. Feedback is persisted with `source`, `kind`, `context`, and `resolved` fields. Recent feedback is loaded into agent context so the model avoids repeating known mistakes.
- **Nutrition label reading**: photos of printed nutrition labels are read directly — the Label line is treated as trusted nutrition, no re-estimation from the photo's visual content.
- **Day-boundary settings**: users can set when their tracking day starts (e.g. 4am) via `update_settings dayBoundaryHour`. Late-night snacks count toward the right day.
- **Budget alerts**: optional notifications when crossing the calorie target in max mode. Wired through `send_budget_alert` callback after `apply_journal_actions`.
- **Tracking nudges**: gentle reminders if a user hasn't logged a meal.
- **Target mode**: `max` (ceiling — frame as remaining budget) or `min` (floor — frame as how much more needed). Reported in `get_today_summary`.
- **Weekly summaries**: 7-day calorie aggregates with per-day totals, daily average, and target.
- **Food-history search**: search past entries by food text and date range, with diacritic-insensitive matching.
- **Custom food aliases**: user-scoped shorthand (e.g. "cafea" → "coffee with milk, 35 kcal") with case-insensitive unique constraint and check constraints.
- **Progressive disclosure**: compact core system prompt (~15 lines) + 7 capability markdown docs loaded on demand via `load_instructions(topic)`.
- **Private foods**: user-created food items with custom calorie/macro definitions.
- **Receipt simplification**: unverified calorie estimates no longer claimed to come from the user's message.
- **Migration-on-boot**: the app container runs `alembic upgrade head` on startup — zero manual migration steps.

### Changed

- `OPENAI_BASE_URL` is now configurable (defaults to LiteLLM proxy in Compose, direct OpenAI in `.env.example`).
- `OPENAI_MODEL` defaults to `gpt-5.6-luna`.
- `AgentContext.romanian` removed — the model decides reply language.
- Deterministic reply templates removed — the model writes full replies from structured tool results.
- Tool modules split into focused files: `journal_actions.py`, `nutrition.py`, `planning.py`, `settings.py`, `instructions.py`, `aliases.py`, `feedback.py`, `shared.py`, `registry.py`.
- `update_settings` now advances onboarding stages (NAME → TIMEZONE → CALORIE_TARGET → COMPLETE) based on which fields the agent sets.
- `get_today_summary` now returns `targetMode` so the model can frame the budget correctly.
- Backfill SQL updated to include `NAME` stage.

### Fixed

- **Idempotent feedback migrations**: both local (`f7a3b9c5d204`) and remote (`b3f7a1c9d4e2`) branches create `user_feedback`. All three feedback migrations are now conditional — they check for existing tables/columns before creating or adding, so a fresh CI database and an existing production database both migrate cleanly.
- **Daily-status flood-control storm**: `MessagingDailyStatus.retry()` now clears `dirty` on failure instead of busy-looping (see `docs/operations.md` incident 2026-08-23).
- **Pinned message unpin**: replaced pinned daily status message is properly unpinned when the edit fails.
- **Onboarding completion**: users stuck mid-onboarding are backfilled to `COMPLETE` by migration `c4a8e2f1b6d9`.
- **Diacritic-insensitive search**: "dulceata" now matches "dulceață" in entry search.

### Migration notes

- Single Alembic head: `e9f5a2b7c8d3`.
- The app container self-migrates on boot. No manual `alembic upgrade` needed for production deployments.
- For fresh databases: replay `flyway_baseline/V1__*.sql` through `V17__*.sql` first, then `alembic upgrade head`.
- For existing databases: just restart the container — it runs `alembic upgrade head` automatically.

### Test results

- **302 tests pass** (unit + integration).
- CI: `build-test`, `build-and-smoke`, `security-scan` all green.
- Ruff clean. No conflict markers. No whitespace errors.

---

## v1.0 — 2026-06-01

Initial production release. Python 3.11+ / FastAPI / PostgreSQL / OpenAI. Telegram webhook + Mattermost WebSocket frontends. Flyway V1–V17 baseline schema. Deterministic onboarding, reply templates, and portion follow-up logic.
