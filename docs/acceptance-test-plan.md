# Release acceptance plan

This is a release gate, not a claim that a green unit-test suite proves a live Telegram deployment.

## Automated gate

The protected `master` build must pass all of the following on the exact commit proposed for release:

- Maven verification, including unit tests, PostgreSQL/Flyway integration tests, and webhook-to-outbox acceptance journeys using mocked provider and Telegram HTTP boundaries.
- Docker image build and Compose startup, with public liveness and private database-aware readiness checks.
- Dependency/configuration security scan.
- No committed `.env`, token, Telegram update, raw media, legacy export, or journal data.

The automated suite must prove allowlist rejection, webhook-secret rejection, one-entry behavior for a repeated Telegram `update_id`, ownership isolation, invalid-model no-write behavior, transient voice/photo/document handling, sourced versus estimate nutrition labels, and report-delivery idempotency.

## Manual pre-production gate

Run this only with a rotated test bot, a disposable database, an allowlisted test Telegram account, and separate non-production OpenAI/Gemini credentials. Record only pass/fail and redacted timestamps; do not commit messages, chat IDs, tokens, or media.

| Scenario | Pass condition |
| --- | --- |
| `/start` onboarding | Timezone and target are stored; invalid values do not advance onboarding. |
| Text meal | One event and one reply appear; `/today` reflects it. |
| Voice, photo, document | Each produces a safe result or clarification; original bytes do not exist in the database, volume, or logs. |
| Search, edit, delete | Results are user-scoped and daily status changes once. |
| Nutrition | Official, private/manual, and estimate values are visibly distinguishable. |
| Duplicate/retry | Replaying the same update produces one journal mutation and one queued reply. |
| Reports | Morning and evening each deliver once in the configured IANA timezone across a restart. |
| Recovery | Backup completes, isolated restore validates, and readiness returns healthy after restart. |

Any failed row is a release no-go. Repeat the affected automated and manual checks after remediation.

## Current authorization status

**NO-GO.** Automated evidence can be produced in CI, but live acceptance cannot yet be executed without a rotated test Telegram token, test allowlist, provider credentials, a public HTTPS test URL, and observed report windows. Coolify must remain disconnected until every automated and manual gate is recorded as passing.
