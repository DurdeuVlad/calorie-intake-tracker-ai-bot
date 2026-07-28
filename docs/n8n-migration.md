# n8n migration assessment

## What is known

The legacy system is a large n8n Telegram food-journal flow. It accepts meal messages and stores food information, but its size and orchestration model make it unreliable and hard to evolve.

## Deliberate changes

- Replace implicit workflow state with typed application services and PostgreSQL transactions.
- Replace best-effort retries with explicit webhook and scheduler idempotency ledgers.
- Require access control at the application and query layers.
- Treat AI output as untrusted structured input, not executable workflow instructions.
- Discard original media after processing.

## Migration boundary

Do not commit the n8n JSON export, credentials, raw Telegram updates, or user data. Legacy import is deferred until the three legacy table schemas and a separately secured data export are available. The required evidence and mapping gates are tracked in the private-facing [legacy import assessment template](legacy-import-mapping.md). Build an import tool only after mapping identifiers, timezones, deduplication policy, nutrition provenance, and rollback procedure.

## Known risks to resolve before cutover

- Rotate any Telegram token exposed by the legacy export.
- Obtain the separate legacy error workflow and table definitions.
- Reconcile duplicate/partial legacy entries before import.
- Run new and old systems in a bounded verification period, then switch the Telegram webhook once.
