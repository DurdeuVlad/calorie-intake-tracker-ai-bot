# ADR 0005: Persist outbound Telegram messages before delivery

## Decision

Journal mutations, report claims, and Telegram replies use a PostgreSQL outbox. The application persists a pending outbound message in the same transaction as the business change. A scheduled dispatcher sends pending messages and retries failures with bounded backoff.

## Why

Calling the Telegram API inside a database transaction makes delivery failures interfere with journal writes and makes duplicate webhook retries hard to reason about. The outbox gives journal state and the reply a durable handoff boundary.

## Consequences

Delivery is asynchronous and may be delayed briefly. Dispatch claims one message at a time with a 60-second lease; the Telegram client has 5-second connect and 10-second read limits. Delivery is at-least-once at the transport boundary, while incoming Telegram updates and scheduled reports are atomically deduplicated before messages are enqueued.
