# Legacy import assessment template

**Status: BLOCKED — no legacy schemas or secured export supplied.** No importer exists and none may be written from the n8n JSON alone.

Complete this document in a private, access-controlled workspace before any import implementation.

| Legacy source/table | Candidate target | Required mapping decisions | Evidence |
| --- | --- | --- | --- |
| users | `users`, `user_settings` | Telegram ID, display name, IANA timezone, onboarding defaults | pending |
| entries | `food_entries`, `food_items` | event timestamp/timezone, text evidence, quantities, calories/macros, nutrition provenance | pending |
| workflow errors | none by default | operational evidence only; never import secrets or raw updates | pending |

## Import gates

- Obtain the three source schemas, row counts, data dictionary, error workflow, and a securely transferred export.
- Hash and inventory the export outside Git; redact credentials and raw Telegram payloads before analysis.
- Define owner mapping, timezone conversion, duplicate/partial-entry policy, nutrition source mapping, and rejected-record quarantine.
- Build a dry-run importer with deterministic IDs, row-level validation, audit counts, and an explicit no-write mode.
- Test dry-run and import against an isolated PostgreSQL database. Reconcile source/target counts and sampled entries before any production decision.
- Keep production rollback as application/webhook rollback; do not overwrite a live journal with legacy data.
