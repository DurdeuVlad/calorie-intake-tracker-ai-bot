# Open-source project policy

## Project status

Food Journal AI Bot is an MIT-licensed, self-hostable open-source project. The canonical implementation is the Python application under `python-app/`. The repository is public, but it is not a hosted SaaS: operators are responsible for infrastructure, credentials, backups, provider accounts, and compliance for their deployment.

## What is included

- Source code, tests, migrations, Docker Compose configuration, and operational documentation.
- Telegram and optional Mattermost frontends.
- Agent-driven nutrition logging with text, voice, photo, and nutrition-label inputs.
- Privacy and security boundaries documented in [`SECURITY.md`](SECURITY.md) and [`docs/architecture.md`](docs/architecture.md).

## What is not promised

- Medical, dietary, or clinical advice.
- Accuracy of AI-generated nutrition estimates or third-party nutrition data.
- Hosted availability, support SLAs, or backward compatibility for every release.
- Automatic compliance with the laws or policies applicable to an operator's deployment.

Users should review every estimate that matters to their health and consult a qualified professional for medical or dietary decisions.

## Releases and compatibility

- Releases are cut from protected `master` after required CI checks pass.
- Database changes are delivered as forward-only Alembic migrations.
- The app container applies pending migrations on boot; production operators must back up before upgrades and verify readiness afterward.
- Breaking configuration or behavior changes belong in [`CHANGELOG.md`](CHANGELOG.md), with migration and rollback notes when applicable.

## Contributions

Contributions are welcome when they improve correctness, privacy, security, reliability, usability, or maintainability. Start with [`COLLABORATION.md`](COLLABORATION.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md). Keep changes scoped, tested, documented, and reviewable.

## Support

Use GitHub issues for reproducible bugs and feature requests. Include the release or commit, environment, safe reproduction steps, and expected versus actual behavior. Redact credentials, identifiers, private messages, media, and personal nutrition data.

Security-sensitive reports must use [`SECURITY.md`](SECURITY.md), not a public issue.

## License and dependencies

The project is distributed under the [MIT License](LICENSE). Third-party services and dependencies retain their own terms and licenses. Operators must review OpenAI, Telegram, Mattermost, Open Food Facts, SearxNG, Browserless, and any model-provider terms before production use.

## Status

The project is actively maintained but remains a self-hosted, maintainer-led project. Governance, release cadence, and support commitments may evolve as the contributor community grows.
