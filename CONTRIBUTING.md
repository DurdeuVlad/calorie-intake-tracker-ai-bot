# Contributing

Thanks for helping. Keep changes small, tested, and reviewable.

## Before opening a pull request

- Never commit tokens, `.env` files, user data, Telegram updates, media, or n8n exports.
- Use Java 21 and run `mvn verify` before requesting review.
- Add or update tests for behavioural changes.
- Add a Flyway migration for persisted-schema changes; never alter an applied migration.
- Update the relevant `docs/` page and ADR when a design decision changes.

## Pull requests

Describe the user-visible result, tests run, configuration changes, and migration/rollback implications. Keep unrelated formatting or refactors out of the same PR.

## Design rules

- Enforce Telegram user ownership on every read and write.
- Treat AI output as untrusted input and validate it before mutation.
- Do not persist original voice, image, or document media.
- Keep secrets in GitHub/Coolify configuration only.
