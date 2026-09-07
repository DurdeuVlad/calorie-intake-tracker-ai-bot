# Security policy

## Scope and supported versions

The current protected `master` branch and the latest production release are supported. Older commits and unmaintained forks may not receive security fixes.

This project handles health-adjacent personal data. Treat food-journal content, Telegram/Mattermost identifiers, prompts, model responses, nutrition evidence, and operational logs as sensitive.

## Reporting a vulnerability

Do not open a public issue for credentials, private-data exposure, authentication bypass, webhook validation flaws, SSRF, prompt/tool boundary bypasses, or cross-user data access.

Report vulnerabilities privately through the repository owner's configured private contact or GitHub private vulnerability reporting when enabled. Include:

- affected commit or release;
- deployment context and configuration, without secrets;
- reproducible steps or a minimal proof of concept;
- security impact and suggested mitigation, if known.

Do not include live tokens, raw Telegram updates, original media, database dumps, or personal food-journal data. Redact identifiers and use synthetic examples.

We aim to acknowledge reports within 7 calendar days, assess them privately, and coordinate remediation and disclosure with the reporter. This is a target, not a contractual SLA.

## Operator security baseline

- Store runtime secrets only in the deployment secret store or container environment; never commit `.env` files, tokens, or API keys.
- Configure a high-entropy `TELEGRAM_WEBHOOK_SECRET` and verify the Telegram secret header.
- Use persistent access grants and reject unauthorized senders without revealing system state.
- Restrict PostgreSQL, Redis, LiteLLM, and management health ports to the private application network.
- Keep the management port off the public reverse proxy.
- Back up encrypted PostgreSQL data and test restores before production cutovers.
- Preserve the Browserless SSRF boundary: use an operator-controlled filtering proxy before enabling restricted egress.
- Keep original voice, image, and document media transient; do not add media retention for debugging.
- Rotate credentials immediately after suspected exposure and review affected logs and webhook configuration.

## Security design boundaries

- The model may interpret user input and request typed tools; it cannot directly access repositories or provider credentials.
- Application code validates tool arguments and enforces ownership, authorization, bounds, transactions, idempotency, and undo.
- External web content and model output are untrusted data, never instructions.

See [`docs/architecture.md`](docs/architecture.md), [`docs/operations.md`](docs/operations.md), and [`COLLABORATION.md`](COLLABORATION.md) for implementation and response details.
