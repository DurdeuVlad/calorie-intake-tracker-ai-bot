# Local development

## Prerequisites

Java 21, Maven (or Maven Wrapper), Docker Desktop, and a PostgreSQL instance.

## Setup

1. Copy `.env.example` to `.env` and use non-production credentials.
2. Start PostgreSQL using the project Compose configuration once available.
3. Run `mvn spring-boot:run`.
4. Run `mvn verify` before opening a PR.

Webhook testing requires a public HTTPS tunnel or a deployed development environment. Do not point a development bot at a production database.
