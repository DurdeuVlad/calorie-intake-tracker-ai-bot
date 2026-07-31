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

## Terminal chat and live prompt evaluation

The `terminal` profile is the local substitute for Telegram. It keeps the production inbox, worker, journal agent, tool executor, outbox, Flyway migrations, and PostgreSQL path. It replaces only Telegram HTTP delivery with terminal output. OpenAI and Open Food Facts calls remain real.

Start PostgreSQL first. The first fresh Compose initialization creates both `foodjournal` and the isolated `foodjournal_dev` database. If the existing volume predates this setup, create it once with `docker compose exec postgres createdb -U foodjournal foodjournal_dev`.

PostgreSQL is bound only to `127.0.0.1:5432` so the host-run terminal app can connect. To reset the disposable terminal database, stop the terminal app, then run `docker compose exec postgres dropdb -U foodjournal foodjournal_dev` followed by `docker compose exec postgres createdb -U foodjournal foodjournal_dev`.

Set `TERMINAL_TELEGRAM_USER_ID` to a value already present in `ALLOWED_TELEGRAM_USER_IDS`, and keep `TERMINAL_DATABASE_*` pointed at `foodjournal_dev`. Start the chat with:

```powershell
docker compose up -d postgres
Get-Content .env | ForEach-Object { $line=$_.Trim(); if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) { $pair=$line.Split('=',2); [Environment]::SetEnvironmentVariable($pair[0].Trim(),$pair[1].Trim(),'Process') } }
.\mvnw.cmd spring-boot:run "-Dspring-boot.run.profiles=terminal"
```

Type normal text as a chat message. `:help`, `:trace on`, `:trace off`, and `:quit` are local terminal commands. Trace output contains model-turn counts plus tool names and outcome codes; it never prints credentials or provider HTTP payloads.

The bundled text suite makes real OpenAI calls only when you explicitly start it. It is not a Maven test and is not run by CI. It resets the configured terminal user's data before every scenario repetition; use only the disposable `foodjournal_dev` database:

```powershell
$env:TERMINAL_EVAL_FILE='classpath:evals/text-journal.json'
.\mvnw.cmd spring-boot:run "-Dspring-boot.run.profiles=terminal"
Remove-Item Env:TERMINAL_EVAL_FILE
```

It runs every isolated scenario three times by default, then reports a weighted 100-point quality score and a strict safety-release verdict. Scenarios marked `startOnboarded` create a fresh user through the normal `/start` flow before their asserted turns; the onboarding scenario starts clean. Safety failures cap the score at 59 and fail the release verdict. Reports under `eval-reports/` are ignored by Git and contain full local input/reply text by default (set `TERMINAL_EVAL_FULL_REPORT=false` to redact it). Use `TERMINAL_EVAL_SCENARIO` to select one scenario, `TERMINAL_EVAL_REPEATS` to change repetitions, and `TERMINAL_EVAL_BASELINE_FILE` to show a score delta from a prior report.
