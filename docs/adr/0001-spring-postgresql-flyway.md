# ADR 0001: Spring Boot, PostgreSQL, and Flyway

> **Historical / superseded in this repository.** This decision describes the former Java implementation, which now lives in the standalone sister repository. The canonical implementation here is Python/FastAPI with SQLAlchemy and Alembic. See ADR 0006.

**Status:** Accepted

Use Java 21/Spring Boot for the service, PostgreSQL as the system of record, and Flyway for immutable schema migrations. This matched the original learning goal and remains the architectural record for the Java sister repository. It is no longer the implementation decision for this Python repository.
