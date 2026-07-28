# ADR 0001: Spring Boot, PostgreSQL, and Flyway

**Status:** Accepted

Use Java 21/Spring Boot for the service, PostgreSQL as the system of record, and Flyway for immutable schema migrations. This matches the learning goal, supports transactional ownership/idempotency rules, and remains straightforward to self-host. JPA may be used behind repository boundaries; database constraints remain mandatory.
