# Collaboration

## Project model

Food Journal AI Bot is maintained as a public, open-source repository with a single primary maintainer today. The project is intentionally small: contributions should improve the product without adding process that the codebase does not need.

## How work is coordinated

- Open an issue before substantial work so the problem and intended outcome are visible.
- For focused fixes, a pull request with clear scope is enough.
- Keep one user-visible outcome per pull request when practical.
- The maintainer owns release decisions, production access, security response, and changes to privacy or data-retention behavior.
- Contributors own the correctness of their proposed changes and the evidence in their pull request.

## Pull request expectations

Every pull request should state:

1. The user or operator outcome.
2. The implementation and affected boundaries.
3. Tests and checks actually run.
4. Configuration, migration, security, privacy, and rollback impact.
5. Any unresolved assumptions or follow-up work.

Required checks are defined by repository branch protection and GitHub Actions. Do not bypass failing checks. Schema changes require a new Alembic revision; never rewrite an applied migration.

## Decision boundaries

- The model owns conversation, semantic interpretation, clarification, and language choice.
- Application code owns authorization, ownership, validation, calculations, transactions, persistence, idempotency, and undo.
- Contributors must not add message rewriting, hidden prompt injection, cross-user reads, raw-media retention, or deterministic semantic guards without an explicit architectural decision.

See [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and [`docs/agent-system.md`](docs/agent-system.md) for repository-specific working rules.

## Communication

Use GitHub issues for reproducible bugs, feature proposals, and documentation gaps. Use the private security process in [`SECURITY.md`](SECURITY.md) for vulnerabilities. Do not include tokens, private messages, raw media, database dumps, or personal food-journal data in issues or pull requests.

## Status

This is a lightweight collaboration policy. If the project gains multiple regular maintainers or sustained outside contributions, record roles, review ownership, and escalation paths in a dedicated governance change rather than assuming them.
