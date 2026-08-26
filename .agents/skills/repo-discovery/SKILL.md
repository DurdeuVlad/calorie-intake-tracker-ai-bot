# Repo Discovery

## Use when

Use this skill before non-trivial implementation, diagnosis, review, or documentation work.

## Read

- Root `AGENTS.md`.
- `docs/agent-system.md`.
- `docs/agent-quality-control-checklist.md`.
- The task-specific documents selected by the routing matrix.

## Procedure

1. Run `git status --short`.
2. List relevant files with `rg --files`.
3. Search symbols, configuration keys, routes, migrations, prompts, and tests with `rg`.
4. Trace the affected path from input to validation, persistence, queue/external side effect, read path, and user-visible result.
5. Read callers and tests, not only the first matching implementation.
6. Record current behavior, desired behavior, invariants, and evidence gaps.

## Stop conditions

Stop and report when ownership, persistence, migration, prompt boundary, or source-of-truth behavior is contradictory and the task cannot be completed safely by a local decision.

## Handoff

Return a concise context map: relevant files, current flow, applicable constraints, likely change surface, tests to run, and unresolved questions.
