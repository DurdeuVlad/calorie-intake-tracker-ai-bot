# Data model

| Entity | Purpose | Key constraints |
| --- | --- | --- |
| `users` | Telegram identity and onboarding state | unique Telegram user ID |
| `user_settings` | timezone, calorie target, report schedule/preferences | one row per user; IANA timezone |
| `food_entries` | one eating event | owned by user; meal time and source text |
| `food_items` | structured contents of an eating event | optional generic quantity with `g`, `ml`, `portion`, or `unspecified` unit |
| `journal_change_sets` | reversible mutations produced by one message | owned by user; expires after ten minutes |
| `journal_change_mutations` | ordered before/after snapshots for Undo | belongs to one change set |
| `nutrition_sources` | provenance/cache records | source type, external ID, retrieval time |
| `processed_updates` | Telegram idempotency ledger | unique `update_id` |
| `report_deliveries` | scheduled-report deduplication | user, report type, local report date unique |
| `pinned_status` | current daily Telegram status message | one current status per user/chat |

Use UTC timestamps for instants; retain each user's IANA timezone for local-day queries and scheduling. All foreign keys must preserve ownership paths and use database constraints as a backstop to application authorization.
