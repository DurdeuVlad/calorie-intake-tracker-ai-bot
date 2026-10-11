# Mission Phase 1 — Audit & Architecture Proposal

**Mission**: Transform this open-source Telegram food-journal bot into a production-ready, **voice-first mobile nutrition companion** (iOS + Android, React Native) with three experiences:

- **(A)** Speak-your-meals logging with web nutrition research, provenance, and corrections
- **(B)** A companion with long-term, user-controlled memory
- **(C)** Configurable reminders/check-ins and deterministic on-device app restrictions

Hard constraints: Romanian + English + mixed input; photo/camera meal recognition is **out of scope**; existing Telegram data preserved via secure account linking; the existing OSS product and its regression tests must be preserved.

**Method**: Read-only audit of this repository (code, schema, docs, CI, git history) plus cited public sources for competitor and platform facts. Everything not directly verified is marked **[uncertain]**.

---

## 1. Current-State Audit

### 1.1 Repository shape — two implementations, one product

The repository contains **two complete implementations of the same product**, not a Java backend plus a Python agent:

| Path | What it is | Stack |
| --- | --- | --- |
| `src/` | Original application | Java 21, Spring Boot 3.5 (`pom.xml` → `spring-boot-starter-parent` 3.5.16), Spring Web + Data JPA + Validation + Actuator/Prometheus, Flyway migrations `V1`–`V17` |
| `python-app/` | Full Python rewrite merged via PR #63 (`feature/python-rewrite`, ~Aug 2026) | FastAPI + uvicorn, SQLAlchemy 2 async + asyncpg, Alembic, aiogram 3, raw-httpx OpenAI client, pytest |

Evidence that `python-app/` is the **newer, actively maintained line**:

- Git history after the merge works on `python-app/` only: persistent Telegram access grants (PR #64, new Alembic migration `7e9f2c4a1b6d`) and the cached web-search grounding (`15f03a1`, the HEAD commit).
- `python-app/compose.yaml` carries a comment explaining the 512 MB memory cap exists because of a prior host-wide OOM incident in the Java app — the Python service is the operational successor.
- `python-app/Dockerfile`, `python-app/run.py`, and `python-app/app/main.py` are a self-contained deployable (public app on 8080, management app on 8081, all background workers as asyncio tasks in one process).

**However**, the root `compose.yaml`, `Dockerfile`, `README.md`, and all of `docs/` still describe the Spring Boot monolith, and root CI (`ci.yml`) still builds/tests/ships the Java container. So the repo is in a **dual-implementation transitional state**: both CI pipelines are green-path required, both containers build. Which binary actually serves production traffic is not stated anywhere in the repo — **[open question, §5]**.

The two implementations share the **same PostgreSQL schema** (Alembic baseline `585aef501d2c` is a no-op snapshot of Flyway V17), the **same env-var contract** (`config.py` "mirrors BotProperties/application.yml exactly... so Coolify deployment config carries over"), the same `/webhook` route, and the same 8080/8081 port split.

Unless stated otherwise, the rest of this audit describes **`python-app/`** — the line any new work would extend. The Java side matters mainly as (a) the source of truth the port was verified against and (b) the owner of the Flyway migration chain.

### 1.2 Component interaction (python-app)

```
Telegram ──HTTPS webhook──▶ POST /webhook (secret-token check)
                                │  normalize to InboundMessage
                                ▼
                        messaging_inbox  (idempotent on provider+event_id, leased, 3 attempts)
                                │  inbox_worker polls every 500 ms
                                ▼
              access check (telegram_access_grants) → admin cmds → /link
                                │  media? → OpenAI transcribe / vision
                                ▼
                JournalApplicationService ──▶ JournalAgent (ReAct loop ≤10 tool calls)
                                │               │
                                │               ▼
                                │      JournalToolExecutor (deterministic, validated)
                                │        Open Food Facts │ SearxNG │ Browserless │ DB
                                ▼
        conversation_memory (≤10 turns) + messaging_daily_status + outbox reply
                                ▼
                        messaging_outbox ──▶ TelegramFrontend (aiogram)
```

Key properties:

- **Inbox/outbox reliability**: webhook → `messaging_inbox` row (unique `provider, event_id`, `IntegrityError` swallow = dedup) → leased claim (`lease_token`, 60 s lease) → retry with exponential backoff up to 3 attempts → `FAILED` with payload scrubbed. Replies go through `messaging_outbox` with the same lease/backoff shape. This gives at-least-once processing with idempotent edges — directly reusable for mobile API calls if the same enqueue path is kept.
- **Single-process workers**: `run.py` runs the inbox worker, outbox dispatcher, daily-status dispatcher, pinned-status dispatcher, report scheduler, and cleanup jobs as `asyncio` tasks alongside two uvicorn servers. There is no external queue — the DB *is* the queue. This is fine for a household-scale deployment; it does not scale horizontally without work on the claim protocol (leases exist, so multi-replica claiming is mostly safe already, but untested — **[uncertain]**).
- **Frontend abstraction**: `InboundMessage.provider` ∈ `{telegram, mattermost, terminal}`; `FrontendRegistry` maps provider → send/edit/pin/download adapter. Adding a `mobile` provider is architecturally anticipated — but mobile needs *request/response* semantics, not store-and-forward, so see §4.2.

### 1.3 Telegram bot surface

- **Ingress**: `POST /webhook`, verifies `X-Telegram-Bot-Api-Secret-Token` via `hmac.compare_digest`, silently 200s malformed/non-message updates. Only public route besides `/health`.
- **Access control**: DB-backed `telegram_access_grants` (telegram_user_id PK, `is_admin`, `active`). Bootstrap admins/legacy allowlist are seeded from env on each access check (`seed_bootstrap_grants`, upserts). Admins manage users via private-chat `/adduser <id>` / `/removeuser <id>` (`telegram_admin_service`).
- **Commands** (`JournalApplicationService.command`): `/start` (onboarding prompt), `/help`, `/today`, `/report`, `/settings`, `/cancel`, `/privacy`, plus `/link` (Mattermost linking) and `/undo` (handled inside the agent, not the command table).
- **Media**: voice → `OpenAiVoiceTranscriber` (`/audio/transcriptions`, model `gpt-4o-mini-transcribe`, ≤20 MB in-memory); photo/document → `OpenAiFoodMediaExtractor` (vision). Media is downloaded transiently and never persisted. (Photo logging exists today but is out of mission scope.)
- **Replies**: plain text ≤4096 (Telegram limit), no Markdown (system-prompt enforced), outbox-delivered; pinned daily status maintained via `pinned_daily_status` desired-version/lease protocol; morning/evening reports via `report_deliveries` dedup claim with a pre-2 a.m. catch-up window.
- **Other frontends**: Mattermost WebSocket listener (`mattermost_websocket_listener`, off by default) and a Terminal REPL/eval profile that drives the *same* agent wiring (`builder.py` is shared between `run.py` and the harness).

### 1.4 Agent + nutrition tools (the reusable core)

`JournalAgent` is a bounded ReAct loop (`agent_max_tool_calls`, clamped 1–10) over OpenAI Chat Completions (`OPENAI_MODEL`, default `gpt-5.6-luna`; raw httpx, not the SDK). The model **cannot touch the DB** — it emits calls against 20 typed tools (`tool_schemas.py`, transcribed verbatim from the Java definitions "the model was tuned against"):

- **Journal reads**: `get_today_summary`, `search_entries` (today/yesterday/ieri/ISO/range), `get_entry`, `get_settings`.
- **Nutrition resolution**: `resolve_nutrition`/`lookup_food` → `nutrition_resolver.resolve` priority chain: declared kcal → barcode via `nutrition_source_cache` (30-day TTL, global) → live Open Food Facts → user `private_foods`. `search_packaged_food` → OFF `/search` ranked (exact match → token overlap → source order) → persisted `pending_nutrition_quotes` (server-owned UUIDs, 30-min TTL) → `select_packaged_food` re-reads a locked owned quote before logging.
- **Web grounding (the recent addition)**: `search_web` → self-hosted SearxNG JSON API, with an **in-process result cache** (1-day TTL, 256-entry cap, query-normalized, response fields bounded to 256/1024/1024 chars); `fetch_web_page` → Browserless `/content` text extraction (≤4000 chars) behind a **manual SSRF guard**: DNS-resolve host, reject loopback/private/link-local/unspecified, then walk ≤5 redirects re-validating every hop without auto-following. `estimate_food` is the validated fallback (name + grams + kcal/100 g, 1–10000) producing a `AI_ESTIMATE` quote.
- **Mutations**: `apply_journal_actions` — batched CREATE/EDIT/MOVE/DELETE (≤20), each validated independently (calories 1–10000, quantity bounds, no future dates, DST-gap detection via fold/round-trip, owner-scoped entry lookup), wrapped in a `JournalChangeSet` (before/after JSONB snapshots, 10-min expiry) powering `undo_last_change`. A change set with zero successful mutations is never persisted.
- **Planning/misc**: `plan_todos`, `complete_todo` (ephemeral), `save_private_food`, `update_settings` (IANA timezone validation, calorie target 1200–5000).

The **system prompt** encodes RO/EN/mixed behavior ("ieri"/"azi" words, typo tolerance), search-before-mutate, combo-meal-is-one-CREATE, daily-total-uses-`get_today_summary`-only, untrusted-web-content-is-data-not-instructions, no-Markdown, and canonical correction semantics ("do 150 kcal" = absolute EDIT, not delta). Language detection is a diacritic/keyword regex (`language.py`); a per-user `preferred_language` (ro/en) is persisted.

**This whole layer is the product's moat** — deterministic validation around an interpretation-only LLM, with provenance fields (`nutrition_source` ∈ manual/private/open_food_facts_estimate/ai_estimate/mixed; `confidence` ∈ high/estimate/unknown) already stored on every entry/item. It satisfies mission requirement (A) almost as-is.

### 1.5 Data model

Schema = Flyway `V1`–`V17` (Java-owned) + Alembic `7e9f2c4a1b6d` (`telegram_access_grants`). ~24 tables in four groups:

- **Journal**: `food_users` (telegram_user_id unique, nullable), `user_settings` (timezone, calorie_target, report times, onboarding stage, preferred_language), `food_entries` (soft-delete via `deleted_at`, eaten_at timestamptz, calories, nutrition_source, confidence), `food_items` (quantity + unit ∈ g/ml/portion/unspecified, macros).
- **Undo**: `journal_change_sets` + `journal_change_mutations` (JSONB before/after, 10-min).
- **Messaging infra**: `messaging_identities` (provider + external_user_id → user), `messaging_routes`, `messaging_inbox`, `messaging_outbox`, `messaging_daily_status`, `pinned_daily_status`, `frontend_link_codes` (8-char codes, 10-min TTL), `telegram_access_grants`, `processed_telegram_updates`, `report_deliveries`.
- **Agent/nutrition state**: `conversation_memory` (**hard cap 10 rows/user, pruned** — short-term context only), `pending_nutrition_quotes`, `private_foods`, `nutrition_source_cache`, plus legacy `pending_food_drafts`, `pending_agent_actions`, `journal_undo_actions`, `outbound_telegram_messages` (superseded by V13–V17 generic tables but still migrated).

Ownership isolation is `user_id`-scoped at the repository layer (`find_by_id_and_user` everywhere); macros exist on `food_items`/`private_foods`/`nutrition_source_cache` but the agent path only writes calories (macro population is partial today — noted for §5).

### 1.6 Auth model — the single biggest gap for mobile

There is **no user-facing authenticated API**. Authorization = "is this numeric Telegram ID in `telegram_access_grants`" + webhook-secret transport. `FoodUser` rows are keyed by `telegram_user_id`; `messaging_identities` then maps `(provider, external_user_id) → user_id`, which is exactly the seam a mobile account plugs into — but there is no password/OAuth/token machinery anywhere in either codebase, no signup flow, and no session model. Cross-provider identity today is a one-way link code (Telegram `/link` → code → Mattermost `link CODE`).

### 1.7 Test coverage

- **Python** (`python-app/tests/`, 76 test functions): unit tests for agent instructions, DST resolution, eval scorer, Mattermost frontend, OFF client, SSRF guard, web clients, web-search cache; integration tests run **against real PostgreSQL with the actual Flyway V1–V17 scripts replayed** (`scripts/setup_test_db.sh`; `test_schema_fidelity` guards drift), covering account linking, agent `apply_journal_actions`, conversation memory call-site, media handling, full messaging pipeline, schedulers, Telegram access management, terminal harness.
- **Java** (`src/test/`, 31 files): mix of unit, H2, and Testcontainers-Postgres tests across agent, tool executor, web search, webhook, eval runner, and a `src/main/resources/evals/text-journal.json` prompt-eval suite.
- **Evals**: both implementations ship a terminal eval harness (scored prompt scenarios) — the closest existing thing to a logging-accuracy benchmark (see §5.1).

### 1.8 CI & deployment

- `ci.yml` (Java): `mvn verify` → Docker build → compose up → health checks → Trivy fs scan on PRs.
- `python-ci.yml`: pytest against a Postgres 17 service (schema via real Flyway scripts) → Docker build → compose up → `/health` + readiness on 8081 → Trivy on PRs. Triggers on `python-app/**` and migration changes.
- **Deployment**: Docker Compose (postgres + app + optional SearxNG/Browserless endpoints configured by env; Mattermost behind a compose profile). App is non-root, read-only rootfs, tmpfs `/tmp`, 512 MB cap; ports bound to `127.0.0.1`. Docs describe Coolify homelab deployment and Tailscale-fronted Mattermost — i.e., **the product is currently private-network, not internet-facing**, and has no TLS-terminating public API. `docker/backup-postgres.sh` / `restore-postgres.sh` exist.

---

## 2. Reuse Map

| Component | Verdict | Rationale |
| --- | --- | --- |
| **JournalAgent + `tool_schemas` + `system_prompt`** | **Reuse as-is** | Mission experience (A) *is* this loop: NL/voice-transcript → validated mutations with RO/EN handling already tuned. Extend, don't rewrite. |
| **`JournalToolExecutor` (validation, ownership, change sets, undo)** | **Reuse** | Deterministic guardrails; corrections ("do 150 kcal") already supported — directly serves the "corrections" requirement. |
| **Nutrition resolution + web grounding** (OFF client/cache, SearxNG, Browserless, SSRF guard, quote flow, `estimate_food`) | **Reuse** | Delivers "web nutrition research + provenance" today, incl. the in-process search cache. Caveat: cache is per-process (won't share across replicas) and provenance isn't yet surfaced to a UI. |
| **Journal data model** (`food_entries/items`, `journal_change_sets`, `private_foods`, `user_settings`) | **Reuse** | Existing user data preserved by definition; migrations additive only. |
| **Inbox/outbox + idempotency + leased claiming** | **Reuse pattern; extend** | Mobile write path should reuse `messaging_inbox` semantics for retry-safe uploads (or a parallel `api_inbox`); outbox generalizes to push payloads. |
| **`messaging_identities` + `FrontendLinkCode` linking** | **Reuse & extend** | Same mechanism works for Telegram→app linking (see §4.5). |
| **Conversation memory service** | **Reuse for short-term; add new store for (B)** | 10-turn window is working context, not the mission's long-term companion memory — see §4.4. |
| **Report scheduler / daily status / pinned status** | **Reuse scheduling pattern; replace delivery** | Morning/evening reports become push-delivered check-ins (C); pinned-message UX is Telegram-shaped and doesn't port to mobile UI. |
| **FastAPI app + config + workers (`run.py`)** | **Reuse as the API host** | Already the HTTP entrypoint; add routers. |
| **Telegram/Mattermost/Terminal frontends** | **Keep** (OSS preservation) | They must keep working; mobile becomes a fourth provider conceptually. |
| **Vision/photo extractor (`OpenAiFoodMediaExtractor`)** | **Keep but unexposed** in the mobile app | Out of mission scope; harmless to retain for Telegram users. |
| **Auth model (Telegram-ID allowlist)** | **Replace for mobile** | Add a real account system; keep grants for the Telegram surface. |
| **Java Spring Boot implementation** | **Preserve, don't extend** | Keep its tests green (OSS preservation), but building the mobile API on the Python line avoids a second port. Flag for founder: declare python-app canonical (§5.2). |
| **Flyway as schema owner** | **Replace ownership** | New tables must come from Alembic on the Python line; document that Flyway V1–V17 is frozen history (see §5 risks). |

---

## 3. Competitor Evidence (public, cited)

How real nutrition apps handle voice/natural-language logging today — named competitors with publicly citable facts; anything not verifiable is marked **[uncertain]**.

### MyFitnessPal — "Voice Log" (Premium)

- Launched **December 11, 2024** for Premium members on iOS + Android, **English-only**, per the official [press release](https://www.prnewswire.com/news-releases/say-it-log-it-myfitnesspal-unveils-voice-log-302329040.html) and [support FAQ](https://support.myfitnesspal.com/hc/en-us/articles/30332897072269-Voice-Logging-FAQ) (app ≥24.35.0; requires mic + speech-recognition permissions; cannot voice-log custom foods/recipes/quick-add).
- Architecture (per [Tribe AI's case study](https://www.tribe.ai/case-studies/myfitnesspal), a vendor involved in the build): **on-device voice recognition** → **Claude 3.5 Sonnet on AWS Bedrock** converts the description into structured food data (items, quantities, serving units, brands, meal context) → matched against MFP's food database (claimed 20M+ foods) → **user reviews each match and serving size before tapping "Log"**.
- Takeaway for us: the market leader chose *speech-to-structured-data → database match → human review*, not end-to-end audio→estimate. Our differentiator vs. MFP: multilingual (RO/EN/mixed), corrections by voice, web grounding for foods absent from a fixed DB, and no Premium gate. Their review-before-commit step is worth copying in the app UI even though our agent commits immediately by design (we have 10-min undo instead).

### MacroFactor — "Describe" + AI photo logging

- **Describe** ([MacroFactor knowledge base](https://help.macrofactorapp.com/en/articles/216-log-foods-with-describe)): type a meal description, **or dictate it via the keyboard microphone** (i.e., they reuse the OS dictation surface rather than shipping their own STT) → natural-language search against a **"common foods" database** (explicitly *not* the branded-foods DB — "Applebee's cheeseburger" returns a generic cheeseburger) → results land on an editable **Plate** for review → "Log Items". Five logging methods are unified in one interface.
- Separately, MacroFactor AI photo logging ([April 2025 monthly](https://macrofactorapp.com/mm-april-2025/)) builds editable entries from a photo, "using real, research-based entries from our food database" rather than pure LLM guesses — the same interpret-then-validate philosophy as our AI boundary. (Photo is out of our scope; the positioning is still instructive.)
- Takeaway: even a "log everything" app constrains NL logging to a curated generic-foods corpus and keeps an editable review step. Our SearxNG-grounded lookup covers the long tail MacroFactor's Describe deliberately skips — a real, demonstrable differentiator.

### Healthify — "Ria Voice" realtime AI coach

- Launched **December 2025** ([TechCrunch](https://techcrunch.com/2025/12/02/healthify-upgrades-its-ai-assistant-ria-with-real-time-conversation-capabilities/), [Analytics India Magazine](https://analyticsindiamag.com/ai-news-updates/healthify-openai-launch-ria-voice-realtime-multimodal-ai-health-coach)): **speech-to-speech** assistant on **OpenAI's Realtime API**, claiming 60+ languages including code-mixed input (e.g., Hinglish), meal logging by voice description or camera, and a persistent coaching companion that pulls from logged data and joins human coach calls.
- Takeaway for experience (B): the industry frontier for the *companion* is realtime audio + long-context personalization. We don't need speech-to-speech at launch (transcribe→agent→reply is our proven path), but user-controlled long-term memory is our differentiator vs. a black-box coaching profile.
- **[Uncertain]** Healthify's exact logging-accuracy methodology and how Ria resolves nutrition values are not publicly documented — don't cite specifics beyond the above sources.

### WhatsApp-bot class (validates the interaction model, weaker evidence)

A cluster of startups (e.g., [Olivka](https://olivka.app/), [Weightbot](https://weightbot.ai/), [Kcaly](https://kcaly.ai/), [HeyCoach](https://heycoach.chat/)) sells "send a voice note/text/photo to a WhatsApp bot, get calories + macros in ~10–15 s" — the same shape as our Telegram product. Olivka publicly describes a pipeline matching ours almost exactly (vision/transcription → match against USDA FoodData Central + Open Food Facts + web lookup → itemized card with Confirm/Edit). **[Uncertain]**: these are marketing pages; sub-15-second and accuracy claims are unverified. Useful signal only: the chat-first logging UX is commercially validated, and "correction by reply" ("it was only half the bowl") is table stakes — our change-set undo + EDIT actions already cover it.

---

## 4. Architecture Proposal

This section proposes the target architecture for the mobile product: an authenticated FastAPI mobile API extending `python-app`, a React Native client, a voice pipeline, a companion memory store, a deterministic on-device restriction engine, and Telegram account linking. Each decision below is justified against the audit findings in §1–§2 and the competitor evidence in §3.

### 4.0 Decision summary

| Decision | Recommendation | One-line rationale |
| --- | --- | --- |
| API host | **Extend `python-app` FastAPI** | Same process/deps/agent wiring; async throughout; Java line stays frozen for OSS preservation |
| Mobile client | **React Native (Expo + config plugins / bare where required)** | One codebase for iOS+Android; native modules needed anyway for Screen Time/Accessibility |
| Voice STT | **Server-side OpenAI transcription first**; evaluate on-device later | Reuses proven path, uniform RO/EN/mixed behavior, keeps "no media retention" |
| Long-term memory | **New Postgres store + retrieval layer, separate from `conversation_memory`** | User-controlled CRUD + explicit consent; short-term window untouched |
| Restrictions engine | **Deterministic, on-device, per-platform native modules** | Only place enforcement can be deterministic; server can't block apps |
| Account linking | **Extend existing link-code flow, both directions** | Reuses `frontend_link_codes` + `messaging_identities`; preserves Telegram data |
| Push | **APNs + FCM via a new notification outbox consumer** | Reuses outbox pattern; Telegram reports keep working |

### 4.1 Why extend FastAPI (vs. the alternatives)

**Alternatives considered:**

- **Extend the Java Spring Boot app**: rejected. It means re-porting every new mobile feature to the implementation the team already rewrote and is actively replacing; splits effort across two stacks forever; Java app's only HTTP surface is the same Telegram webhook — no API advantage either.
- **New standalone API service (third runtime)**: rejected. The agent, tool executor, nutrition services, and repositories are Python modules — a separate service would need RPC into them or a fork. A router inside the existing FastAPI app reaches `JournalApplicationService` in-process with zero serialization seams and inherits `session_scope`, settings, and workers for free.
- **Extend `python-app` (chosen)**: the FastAPI app already owns the public port, the management port, and the worker pool. Add a versioned `app/mobile/` router package. **Caveat to accept**: the workers and API share one process — fine at current scale, and the DB-lease pattern means a later split into `api`/`worker` replicas is a deployment change, not a rewrite.

**Proposed new surface (sketch — `app/mobile/`):**

- `POST /api/v1/auth/{signup,login,refresh}` — account creation + token issue.
- `POST /api/v1/messages` — `{text}` or `multipart` audio → normalize to `InboundMessage(provider="mobile")` → same ingress → **synchronous agent run** (mobile wants a reply in-request, not outbox delivery; reuse `handle_message` minus frontend reply, or run `deps.journal.handle` directly and return the text + structured `apply_journal_actions` results for the review UI).
- `GET /api/v1/journal/today`, `GET /api/v1/journal/entries?from&to`, `PATCH /api/v1/journal/entries/{id}` (structured correction alternative to voice), `POST /api/v1/journal/undo`.
- `GET/PUT /api/v1/settings`, `GET/POST/DELETE /api/v1/memory` (experience B surface), `POST /api/v1/link/telegram` (issue code) / `POST /api/v1/link/redeem`, `POST /api/v1/devices` (push token registry).
- Rate limiting + request-size caps on the new router (the current app has neither — it relies on Telegram as the rate limiter).

### 4.2 Auth design (the replacement for the allowlist)

- **Identity**: add `auth_accounts` (email + password-hash, or "Sign in with Apple"/Google subject — Apple **requires** Sign in with Apple if you offer third-party social login on iOS) → links 1:1 to `food_users`. Then a `messaging_identities(provider='mobile', external_user_id=account_id)` row plugs the account into the *existing* identity-resolution path — the agent, ownership scoping, and repositories don't change at all.
- **Tokens**: short-lived JWT access (15–60 min) + rotating refresh token (opaque, hashed at rest, `device_id`-bound). RS256/ES256, keys from env/secret store. Authorization stays `user_id`-scoped — unchanged.
- **Access gating**: keep `telegram_access_grants` for the Telegram surface (it's an allowlist product); mobile accounts self-register (the mission is a public mobile product). **[Open question]** whether signups are open or waitlisted — see §5.2.
- **Threat notes**: webhook-secret pattern doesn't transfer — mobile needs TLS, token binding, brute-force rate limiting on auth endpoints, and (for store release) attestation (Play Integrity / App Attest) if abuse becomes real. Mark as phase-2 hardening.

### 4.3 Voice pipeline

- **Path**: app records audio (opus/m4a, ≤ ~60 s) → `POST /api/v1/messages` multipart → server transcribes via **existing `OpenAiVoiceTranscriber`** (`gpt-4o-mini-transcribe`, ≤20 MB) → transcript flows into the *unchanged* agent path → reply + structured result. Audio processed transiently, never stored — same privacy contract as Telegram voice notes, which also means App Store privacy-label story stays clean.
- **On-device vs. cloud**: on-device STT (iOS `SFSpeechRecognizer` on-device mode, Android `SpeechRecognizer` on-device) would cut latency/cost, but on-device locale support is device- and OS-dependent and **Romanian on-device availability is [uncertain]** — mixed RO/EN utterances are the mission's hard case, so start server-side (proven, uniform), keep a pluggable `transcribe()` seam, and A/B on-device later for EN users.
- **Correction loop**: agent already supports corrections ("undo", "do 150 kcal", delete-duplicate phrasing). For the app, additionally return structured action results (already in `apply_journal_actions` output) so the UI can render an editable confirmation card — matching MFP/MacroFactor's review step without blocking the fast path.

### 4.4 Companion memory (experience B)

- **Separate store, don't stretch `conversation_memory`**: the existing table is a pruned 10-turn working buffer. Add `companion_memory` (id, user_id, kind ∈ {fact, preference, goal, plan_note}, content, source ∈ {user_explicit, agent_extracted}, created_at, updated_at, deleted_at) — user-scoped, soft-deletable, fully listable (`GET /api/v1/memory`) and forgettable (hard-delete endpoint). "User-controlled" means: user sees everything the companion knows and can delete any item; agent-extracted facts are marked as such.
- **Retrieval**: start deterministic — inject top-N memories (recency + pinned) into the system prompt alongside `memory_recent`. Vector/semantic retrieval is a phase-2 optimization **[decision deferred — measure context usage first]**; don't add an embedding pipeline to the critical path on day one.
- **Extraction**: two safe options — (a) explicit user action ("remember this") via a new agent tool (`save_memory`/`forget_memory`, same validated-tool pattern as `save_private_food`); (b) a background extraction pass over `conversation_memory` proposals that the user approves in-app. Recommend (a) first: it's deterministic, auditable, and matches the AI-boundary doctrine (model proposes, code commits).

### 4.5 Account linking for existing Telegram users

Reuse the existing machinery, extended symmetrically:

- `GET/POST /api/v1/link/telegram` (authenticated app user) → issue `frontend_link_codes` row → user sends `/link CODE` to the bot → a new bot-side redeem path (mirror of Mattermost's `link CODE`) creates `messaging_identities(provider='telegram') → *the app's* FoodUser`. **Direction A: app → Telegram.**
- Direction B (Telegram-first user joining the app): user runs existing `/link` in Telegram → gets code → signs into the app → `POST /api/v1/link/redeem` consumes the code → creates `provider='mobile'` identity on the *existing* FoodUser. All journal data, settings, private foods, and `nutrition_source_cache` participation carry over untouched — **zero data migration**, satisfying "existing Telegram data preserved via secure account linking."
- Security: codes stay 8-char/10-min/single-use (`secrets.choice`, ambiguous-alphabet-excluded); rate-limit redeem attempts; never expose whether an identity exists via error oracles (mirroring current "invalid, expired, or already used" single-message behavior).

### 4.6 React Native client shape

- **Expo** for the managed workflow + dev-client; bare escape hatches are unavoidable anyway because the restriction engine needs custom native modules on both platforms (§4.7). A single `modules/` native layer: `VoiceRecorder`, `ScreenTimeBridge` (iOS), `AppBlocker` (Android).
- Screens map to API surface 1:1: Talk (record → send → reply + editable result card), Journal (day list, edit, undo), Companion (chat + memory review screen), Settings (target, timezone, reminders, restrictions, linked accounts). Romanian + English UI strings via i18n from day one.
- Push: `expo-notifications` (FCM/APNs) → device tokens registered via `POST /api/v1/devices`; server-side a new `push_dispatcher` consumes `messaging_outbox`-like rows with `provider='apns'|'fcm'` — same lease/retry pattern, so reminders reuse `report_scheduler`'s due-check + `report_deliveries` dedup claim, just delivering to devices instead of chat routes. Local-scheduled notifications as the offline-safe fallback for hard reminders.

### 4.7 Deterministic on-device restriction engine — platform feasibility

**Android — feasible, well-trodden.** A native module combining `AccessibilityService` (or `UsageStatsManager` polling) for foreground-app detection + a full-screen overlay/lock screen for enforcement runs entirely on-device, deterministic, no server. Caveats: `AccessibilityService` requires explicit user enablement and a Play Console declaration with justification (policy restricts its use; app-blockers are an accepted category but approval is discretionary — **[uncertain, founder risk]**); battery-optimization whitelisting needed for reliable detection.

**iOS — feasible but bounded by Apple's Screen Time API; "deterministic" has a ceiling.** Per Apple's docs/WWDC22 and developer-forum evidence: `Family Controls` (authorization — individual, iOS 16+, requires a **privileged entitlement Apple must approve** for TestFlight/App Store) + `ManagedSettings` (apply shields/blocks) + `DeviceActivity` (schedule/monitor without the app running). Hard facts to plan around:

- Apps are selected by the *user* via `FamilyActivityPicker` and handed to the app as **opaque tokens** — we cannot enumerate installed apps, can't see names/usage, and can't block a specific app programmatically; the user must pick them.
- Shielding overlays a block screen; true blocking hides the app. Either way, **the user can deauthorize the app in Settings at any time** — enforcement is "deterministic while authorized," not tamper-proof (explicitly different from parental-control mode).
- Schedules/events run via `DeviceActivity` extensions (native code, separate target).

**Consequence for the mission**: restriction rules must live on-device (local SQLite/defaults) with optional server sync for config backup — never server-enforced. Product should set expectations: Android = hard blocking; iOS = shield-style friction within Apple's framework, pending entitlement approval. This is a **founder decision** (pursue entitlement vs. ship Android-only enforcement at launch) — §5.2.

### 4.8 Deployment & data continuity

- Same single-container shape on Coolify, plus a **public TLS ingress** for `/api/v1/*` (today everything is Tailscale-private — first internet-facing surface; add reverse proxy + TLS + rate limiting).
- Schema: continue Alembic (`python-app/alembic/`) for all new tables; freeze Flyway. One-time decision to record in docs: Flyway owns history, Alembic owns future — already the de-facto split since `7e9f2c4a1b6d`.
- Telegram + Mattermost keep running unchanged in the same process; OSS product/tests untouched (mission constraint).

---

## 5. Risks + Open Questions

### 5.1 Measurable benchmark candidates

- **Logging speed**: end-to-end voice-note → committed entry latency (p50/p95). Competitor claims to beat: Kcaly/Olivka marketing "~10–15 s per meal" **[unverified]**; MFP's multi-tap baseline minutes. Target candidate: p50 ≤ 10 s, p95 ≤ 20 s including STT + agent + grounding.
- **Accuracy**: (a) STT WER on RO/EN/mixed utterance corpus — build one; none exists in repo today (evals are text-only). (b) Interpretation correctness via the **existing eval harness** (`terminal/eval_runner.py` + `text-journal.json` scenarios) extended with voice-transcript fixtures and grounding assertions (did it search before estimating? correct provenance label?). (c) Nutrition error: % of logged entries within ±20% of a human-labeled reference set.
- **Reliability**: tool-call budget exhaustion rate, `apply_journal_actions` per-action failure rate, undo success rate, inbox `FAILED` rate, push delivery rate (APNs/FCM ack).
- **Cost**: $/logged-day = chat-completions tokens + transcription minutes + SearxNG/Browserless infra share. Instrument per-turn token counts now; cache-hit rate of the web-search cache directly moves this.
- **Companion**: memory precision/recall on a labeled "things users expect remembered" set; % of agent-extracted memories users keep vs. delete.

### 5.2 Founder decisions needed

- **Canonical implementation**: declare `python-app` the production line (update README/docs/CI primacy) or maintain dual parity — the repo currently doesn't say which binary serves production.
- **Spending**: Apple Developer ($99/yr), Google Play ($25), Apple **Family Controls entitlement application** (approval discretionary — gates the iOS restriction engine), SearxNG/Browserless hosting at mobile scale, OpenAI budget for public users, possible paid STT fallback.
- **Credentials/access**: production Postgres access for linking validation; OpenAI org-level decisions (Realtime API for Ria-style speech-to-speech later?); APNs keys + FCM project; Sentry/analytics choice under the privacy-first brand.
- **Legal/compliance**: GDPR/Romanian-EU data export+delete endpoints (mission's "user-controlled memory" makes this non-optional), health-adjacent disclaimers, App Store nutrition-app review rules, privacy nutrition labels (voice audio processed server-side must be declared even if transient), Play `AccessibilityService` declaration.
- **Production/public release**: open signup vs. waitlist; whether Telegram bot stays free/OSS while mobile is the product; support/abuse ownership for a public API (rate limits, attestation, content moderation for companion chat).
- **Scope call**: whether iOS restrictions ship without entitlement (Android-first) and whether companion speech-to-speech (Realtime API) is a launch or post-launch target.

### 5.3 Technical risks

| Risk | Mitigation |
| --- | --- |
| Dual schema-migration systems (Flyway + Alembic) drift | Freeze Flyway; extend `test_schema_fidelity` to cover Alembic-only tables; document ownership |
| Per-process web-search cache + single-process workers don't scale to mobile traffic | Acceptable at launch scale; DB-lease pattern already supports a future api/worker split |
| `conversation_memory` (10 turns) conflated with companion memory by future devs | Separate table + repo module + explicit naming; document the boundary |
| Auth is greenfield — first credential-holding surface in a privacy-branded product | Standard OIDC-style JWT+refresh, bcrypt/argon2, no custom crypto; security review before launch |
| Romanian/mixed STT quality unknown | Benchmark corpus before committing to on-device; server-side path already proven in Telegram |
| Mobile request/response vs. store-and-forward pipeline mismatch | Run agent synchronously inside `POST /messages` (agent already returns a reply string); keep inbox only for audit/idempotency |
| App Review: health claims + Screen Time entitlement scrutiny | Keep copy to "tracking" not "advice"; prepare entitlement justification; fallback = ship restrictions Android-only |
| Macros exist in schema but agent writes calories only | Decide whether mobile surface fills protein/carbs/fat (OFF data already carries them) or stays calories-first |

---

## Appendix — evidence map

- Agent/tools: `python-app/app/agent/{journal_agent,tool_schemas,system_prompt,openai_model_client}.py`, `python-app/app/services/journal_tool_executor.py`, `python-app/app/services/nutrition_resolver.py`
- Pipeline: `python-app/app/messaging/{ingress,inbox_worker,outbox*}.py`, `python-app/app/telegram_bot/webhook_router.py`, `python-app/run.py`
- Auth/linking: `python-app/app/repositories/telegram_access_repo.py`, `python-app/app/services/{telegram_admin_service,message_link_service}.py`, `python-app/app/db/models/messaging.py`
- Schema: `src/main/resources/db/migration/V1–V17`, `python-app/alembic/versions/`, `docs/data-model.md`
- Tests/CI: `python-app/tests/` (76 test fns), `src/test/` (31 files), `.github/workflows/{ci,python-ci}.yml`, `python-app/tests/integration/test_schema_fidelity.py`
- Deployment: `Dockerfile`, `compose.yaml`, `python-app/{Dockerfile,compose.yaml}`, `docs/deployment-coolify.md`, `docker/`
- Competitor/platform sources linked inline in §3 and §4.7.
