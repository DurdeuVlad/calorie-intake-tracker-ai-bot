# Local Development & Evaluation Guide

---

## Prerequisites

- **Java 21** (JDK 21 LTS)
- **Maven 3.9+** (or use bundled `./mvnw` / `mvnw.cmd`)
- **Docker Desktop** (or Docker Engine + Docker Compose v2)
- **OpenAI API Key** (for testing natural language, vision, or voice capabilities)

---

## Fast Start: Local Docker Environment

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Start the full application stack (PostgreSQL, App, SearxNG, Browserless, Mattermost):
   ```bash
   docker compose up --build -d
   ```
3. Verify readiness health check on management port:
   ```bash
   docker compose exec app wget -qO- http://localhost:8081/actuator/health/readiness
   ```
4. Stop the stack:
   ```bash
   docker compose down
   ```
   *(Use `docker compose down --volumes` only when intentionally wiping database data).*

---

## Iterative Java Development

When developing Java features, run PostgreSQL in Docker and execute Spring Boot on your host machine:

1. Start local PostgreSQL:
   ```bash
   docker compose up -d postgres
   ```
2. Run Maven build and tests:
   ```bash
   ./mvnw clean verify
   ```

---

## Terminal Interactive Mode (Local Chat without Webhooks)

The `terminal` profile lets you interact with the bot directly via your CLI console without configuring external Telegram webhooks. It reuses the exact production domain services, PostgreSQL database, Flyway migrations, OpenAI reasoning engine, and tool executors.

### 1. Launching Terminal Chat

Start PostgreSQL and run the application with the `terminal` active profile:

**PowerShell (Windows)**:
```powershell
docker compose up -d postgres
Get-Content .env | ForEach-Object { $line=$_.Trim(); if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) { $pair=$line.Split('=',2); [Environment]::SetEnvironmentVariable($pair[0].Trim(),$pair[1].Trim(),'Process') } }
.\mvnw.cmd spring-boot:run "-Dspring-boot.run.profiles=terminal"
```

**Bash (Linux / macOS)**:
```bash
docker compose up -d postgres
export $(grep -v '^#' .env | xargs)
./mvnw spring-boot:run -Dspring-boot.run.profiles=terminal
```

### 2. Console Commands & Tracing

- Type food logs in natural language (e.g. `2 scrambled eggs and coffee`).
- Interactive commands:
  - `:help` — Show available terminal commands.
  - `:trace on` — Enable detailed log tracing of agent tool calls and turn counts.
  - `:trace off` — Disable detailed tracing.
  - `:quit` — Exit terminal session.

---

## Automated Prompt & Agent Evaluation Suite

The codebase includes an automated prompt evaluation suite (`evals/text-journal.json`) that executes real natural language logging scenarios against an isolated developer database (`foodjournal_dev`).

### Running Prompt Evaluations

```powershell
# Windows PowerShell
$env:TERMINAL_EVAL_FILE='classpath:evals/text-journal.json'
.\mvnw.cmd spring-boot:run "-Dspring-boot.run.profiles=terminal"
Remove-Item Env:TERMINAL_EVAL_FILE
```

```bash
# Linux / macOS Bash
TERMINAL_EVAL_FILE='classpath:evals/text-journal.json' ./mvnw spring-boot:run -Dspring-boot.run.profiles=terminal
```

### Evaluation Output & Scoring
- Runs scenarios 3 times by default (configurable via `TERMINAL_EVAL_REPEATS`).
- Evaluates meal extraction accuracy, macro math, tool usage, and safety assertions.
- Generates JSON reports in `eval-reports/` (ignored by Git).
- Computes a 100-point quality score and safety verdict.

