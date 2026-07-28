# Functional requirements and acceptance criteria

## Business rules

- Each Telegram update is idempotent by `update_id`; retries create no duplicate entries or notifications.
- Every query and mutation is scoped to the authenticated Telegram user ID. A user cannot see or change another user's data.
- One inbound meal message creates one eating event with zero or more food items only after deterministic validation succeeds.
- Store processed text/structured extraction, not original media bytes or files.
- Nutrition is labelled `OFFICIAL_SOURCE`, `PRIVATE_RECORD`, `MANUAL`, or `AI_ESTIMATE` and retains source/provenance metadata.
- AI providers may interpret content but cannot directly execute database actions. Invalid, incomplete, or ambiguous outputs require clarification or a safe failure.
- Defaults: reports enabled, morning 08:00, evening 22:00; timezone and calorie target are collected during onboarding.
- English is the default reply language; English, Romanian, and mixed messages are accepted.

## Commands

`/start`, `/help`, `/settings`, `/today`, and `/report` are explicit. Natural-language logging, history, correction, deletion, and ordinary chat are supported.

## Acceptance criteria

- An allowlisted user can log supported input types, receives a confirmation, and only processed content is retained.
- A non-allowlisted sender cannot access or mutate private data.
- Replayed webhook updates result in exactly one persisted eating event.
- Search, edit, and delete enforce ownership and leave no partial writes on validation failure.
- Report delivery is recorded and prevents duplicate delivery across retries/restarts.
- A fresh deployment starts from migrations and documented environment variables alone.
