# Data Model Reference

The canonical Python application uses PostgreSQL 16+ with the retained V1–V17 PostgreSQL baseline under `python-app/alembic/flyway_baseline/` and schema evolution managed strictly through Alembic revisions.

---

## Core Domain Entities

| Table | Migration | Purpose & Key Constraints |
| --- | --- | --- |
| `users` | V1 | Primary user record. Stores numeric Telegram ID and registration timestamp (`id` PK). |
| `user_settings` | V1 | Per-user configuration: IANA `timezone`, `daily_calorie_target`, preferred language, report schedule/preferences (`user_id` FK, 1:1). |
| `food_entries` | V1 | Represents one eating event (timestamp, meal type, original text evidence, total calories/macros, `user_id` FK). |
| `food_items` | V1 | Structured food item within an entry (food name, quantity value, unit: `g`, `ml`, `portion`, `unspecified`, calories, protein, carbs, fat, nutrition source provenance). |
| `journal_change_sets` | V17 | Message-level change set holding snapshots for 10-minute reversible undo (`user_id`, `created_at`, `expires_at`). |
| `journal_change_mutations` | V17 | Ordered before/after state diffs (INSERT, UPDATE, DELETE) belonging to a `journal_change_set`. |
| `nutrition_sources` | V5 | Cached provenance records for Open Food Facts, private foods, and web lookups (`source_type`, `external_id`, payload JSON). |
| `private_foods` | V5 | Custom user-created food items and custom calorie/macro definitions (`user_id` FK). |

---

## Frontend Messaging & Outbox Infrastructure

| Table | Migration | Purpose & Key Constraints |
| --- | --- | --- |
| `processed_telegram_updates` | V1 | Legacy Telegram idempotency ledger retained for schema compatibility. Current Python ingress deduplicates through `messaging_inbox`. |
| `messaging_identities` | V13 | Unified messaging identity mapping Telegram and Mattermost accounts (`user_id` FK, platform, platform_user_id). |
| `frontend_link_codes` | V13 | Temporary 10-minute one-time authentication codes for linking Mattermost accounts (`code` UNIQUE, `user_id` FK, `expires_at`). |
| `messaging_inbox` | V14 | Inbound platform-agnostic messaging queue (`id`, provider, event_id, payload, retry state). |
| `messaging_outbox` | V14 | Provider-neutral outbox queue for outbound platform replies (`provider`, conversation, text, retry state). |
| `messaging_routes` | V14 | Maps user messaging routing preferences to active frontend adapters. |
| `messaging_daily_status` | V15 | Outbox ledger for sending and updating daily status summary messages across frontends. |
| `pinned_status` | V3 | Stores the current pinned Telegram daily status message reference (`user_id` FK, `chat_id`, `message_id`). |

---

## Agent Memory & Transient State

| Table | Migration | Purpose & Key Constraints |
| --- | --- | --- |
| `conversation_memory` | V8 | Recent agent conversation turn history (`user_id` FK, message role, content summary, updated timestamp). |
| `pending_food_drafts` | V6 | Transient multi-turn clarification state for uncommitted meal extractions. |
| `pending_agent_actions` | V7 | Pending user confirmations for ambiguous agent actions. |
| `pending_nutrition_quotes` | V10 | Temporary quotes for nutrition calculations before user confirmation. |
| `report_deliveries` | V1 | Deduplication table for scheduled morning/evening reports (`user_id`, `report_type`, `local_date` UNIQUE). |

---

## Key Architectural Principles

1. **Ownership Isolation**: Foreign key constraints enforce `user_id` ownership on all food entries, settings, change sets, and messaging identities.
2. **Timezone Awareness**: Instants are stored as `TIMESTAMP WITH TIME ZONE` (UTC). User queries group entries according to the user's configured IANA timezone (`user_settings.timezone`).
3. **No Media Retention**: Original images, audio files, and documents are never stored in PostgreSQL tables.

