# Contributing

Thanks for helping improve Food Journal AI Bot. This is a maintainer-led open-source project; keep changes small, tested, secure, and reviewable.

Read [`COLLABORATION.md`](COLLABORATION.md) for ownership and pull-request expectations. Read [`AGENTS.md`](AGENTS.md) before working with an AI coding agent.

## Before opening a pull request

- Never commit tokens, `.env` files, user data, Telegram updates, media, database dumps, or legacy exports.
- Use Python 3.11+.
- From `python-app`, run `python -m pytest tests/unit` and `python -m pytest tests` for behavior changes.
- Run `ruff check .` and `git diff --check` before requesting review.
- Add or update regression tests for behavior, security, privacy, or reliability changes.
- Add a new Alembic migration for persisted-schema changes; never alter an applied migration.
- Update the relevant source-of-truth documentation and ADR when behavior, configuration, or architecture changes.
- Preserve the model/application boundary: the model owns conversation and semantic interpretation; application code owns authorization, validation, calculations, persistence, and mutations.

## Pull requests

Describe:

1. The user-visible or operator-visible outcome.
2. The implementation and affected boundaries.
3. Tests and checks actually run.
4. Configuration, migration, security, privacy, and rollback implications.
5. Assumptions, unresolved risks, and follow-up work.

Keep unrelated formatting, refactors, and generated files out of the same pull request. Do not bypass required branch protection or CI checks.

## Design and security rules

- Enforce verified user ownership on every read and write.
- Treat model output, tool output, web content, and user content as untrusted input.
- Do not rewrite user messages before sending them to the model.
- Do not persist original voice, image, or document media.
- Preserve SSRF protections, webhook idempotency, transaction atomicity, and reversible ten-minute undo.
- Keep secrets in deployment secret stores or environment configuration only.

Report vulnerabilities privately through [`SECURITY.md`](SECURITY.md), not in a public issue.
