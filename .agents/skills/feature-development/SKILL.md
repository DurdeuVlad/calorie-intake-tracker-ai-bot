# Feature Development

## Use when

Use for a user-visible behavior change or a bounded bug fix that requires implementation.

## Read

- `AGENTS.md` and `docs/agent-system.md`.
- Relevant product, requirements, architecture, ADR, configuration, and operations docs.
- Existing implementation and tests.

## Procedure

1. Define acceptance criteria and explicit out-of-scope behavior.
2. Identify authorization, idempotency, transaction, retry, time, privacy, and failure requirements.
3. Plan the smallest coherent change.
4. Implement at the strongest trustworthy boundary; do not rely on prompts or clients for security.
5. Add regression tests for success and the most likely counterexample.
6. Update source-of-truth docs when behavior or architecture changes.
7. Run focused checks, then the applicable broad gate.
8. Perform an adversarial review using `.agents/skills/adversarial-review`.
9. Complete `docs/agent-handoff-template.md`.

## Required checks

- Unauthorized access and cross-user data access.
- Duplicate/replayed input when events or jobs are involved.
- Malformed and boundary input.
- Provider failure and partial-failure behavior.
- `Push-Location python-app; python -m pytest tests; Pop-Location` for Python behavior changes.
- The Java sister repository has its own independent build and review path; do not run Java checks from this repository.
- `git diff --check`.

## Do not

- Mix unrelated refactoring into the feature.
- Modify an applied migration.
- Claim a test passed without running it.
- Return a success receipt when durable state is absent or partial.
