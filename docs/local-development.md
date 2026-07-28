# Local development

## Prerequisites

Java 21, Maven (or Maven Wrapper), Docker Desktop, and a PostgreSQL instance.

## Setup

1. Copy `.env.example` to `.env` and use non-production credentials.
2. Start the local stack with `docker compose up --build`. The app is available on `http://localhost:8080/health`; PostgreSQL data remains in the named `postgres-data` volume.
3. For iterative Java development, run only `docker compose up -d postgres`, then run `mvn spring-boot:run` with values from `.env` loaded into your shell.
4. Run `mvn verify`, `docker build .`, and `docker compose up --build --detach` before opening a PR. Check `http://localhost:8080/health`, then run `docker compose down` when finished. Use `docker compose down --volumes` only when intentionally discarding local database data.

The Compose app container is non-root, read-only apart from an in-memory `/tmp`, and has no public management port. Its application port is bound to `127.0.0.1` only. Internal liveness, readiness, and Prometheus endpoints use port `8081`; inspect them with `docker compose exec app wget -qO- http://localhost:8081/actuator/health/readiness`.

Webhook testing requires a public HTTPS tunnel or a deployed development environment. Do not point a development bot at a production database.
