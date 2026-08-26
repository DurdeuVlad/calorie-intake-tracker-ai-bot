# Local Development & Evaluation Guide

The canonical application lives in `python-app/`. Run Python commands from that directory unless a command explicitly says otherwise.

## Prerequisites

- **Python 3.11+**
- **Docker Desktop** (or Docker Engine + Docker Compose v2)
- **PostgreSQL 16+**
- **OpenAI API key** for real model, vision, or voice checks

## Fast Start: Local Docker Environment

1. Copy `python-app/.env.example` to `python-app/.env` and fill in credentials:
   ```bash
   cp python-app/.env.example python-app/.env
   ```
2. Start the Python application stack:
   ```bash
   cd python-app
   docker compose up --build -d
   ```
3. Verify the public and management health endpoints:
   ```bash
   curl --fail http://localhost:8080/health
   docker compose exec app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health/readiness').read()"
   ```
4. Stop the stack:
   ```bash
   docker compose down
   ```
   Use `docker compose down --volumes` only when intentionally wiping local database data.

## Iterative Python Development

Run PostgreSQL in Docker and execute the application or tests from `python-app/`:

```bash
cd python-app
docker compose up -d postgres
python -m pytest tests/unit
python -m pytest tests
```

The integration suite expects a PostgreSQL database using the credentials in the test environment. The CI workflow creates a clean database and runs `scripts/setup_test_db.sh`, which replays the retained V1–V17 PostgreSQL baseline and then applies Alembic revisions.

## Terminal Interactive Mode

The terminal REPL uses the real domain services and tool boundary without exposing a Telegram webhook:

```powershell
Push-Location python-app
python -m app.terminal.repl
Pop-Location
```

Use `:help`, `:trace on`, `:trace off`, or `:quit`.

## Automated Prompt Evaluation

The opt-in evaluation runner makes real model calls. Run it only with an isolated test database and an intentional API budget:

```powershell
Push-Location python-app
$env:TERMINAL_EVAL_FILE='app/terminal/fixtures/text-journal.json'
$env:TERMINAL_EVAL_REPEATS='3'
python -m app.terminal.repl
Remove-Item Env:TERMINAL_EVAL_FILE
Remove-Item Env:TERMINAL_EVAL_REPEATS
Pop-Location
```

```bash
cd python-app
TERMINAL_EVAL_FILE='app/terminal/fixtures/text-journal.json' TERMINAL_EVAL_REPEATS=3 python -m app.terminal.repl
```

Evaluation reports are written to `eval-reports/`, which is ignored by Git. Reports must not contain credentials, raw media, or unnecessary personal data.

## Evaluation Quality Gate

- Run the focused prompt tests before changing the prompt or tool schemas.
- Include normal, Romanian, ambiguous, hostile, malformed, provider-failure, and no-mutation cases as relevant.
- Assert durable database state and tool choice, not only response wording.
- Treat critical safety failures as release blockers.
- Compare quality and category scores with a baseline when one exists.
- Record fixture version, model, repeats, score, safety verdict, failures, and residual nondeterminism.

## Database Schema Workflow

The canonical Python app owns schema evolution through Alembic. The retained V1–V17 SQL files under `alembic/flyway_baseline/` are the PostgreSQL baseline needed to bootstrap an existing deployment and clean CI database. Do not edit an applied baseline or Alembic revision; add a new Alembic revision.

To bootstrap a clean local test database, set `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE`, install `postgresql-client`, then run:

```bash
cd python-app
bash scripts/setup_test_db.sh
```
