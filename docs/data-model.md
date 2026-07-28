# Data model

| Entity | Purpose | Key constraints |
| --- | --- | --- |
| `users` | Telegram identity and onboarding state | unique Telegram user ID |
| `user_settings` | timezone, calorie target, report schedule/preferences | one row per user; IANA timezone |
| `food_entries` | one eating event | owned by user; meal time and source text |
| `food_items` | items within an entry | owned through entry; validated quantity/nutrition |
| `nutrition_sources` | provenance/cache records | source type, external ID, retrieval time |
| `processed_updates` | Telegram idempotency ledger | unique `update_id` |
| `report_deliveries` | scheduled-report deduplication | user, report type, local report date unique |
| `pinned_status` | current daily Telegram status message | one current status per user/chat |

Use UTC timestamps for instants; retain each user's IANA timezone for local-day queries and scheduling. All foreign keys must preserve ownership paths and use database constraints as a backstop to application authorization.
