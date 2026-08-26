# Security Boundary Review

## Use when

Use when a change touches authentication, ownership, account linking, model/tool execution, URL fetching, media, secrets, logging, persistence, or external integrations.

## Procedure

1. Identify every trust boundary and the identifier used to authorize access.
2. Trace untrusted input through parsing, validation, service logic, persistence, logs, and external calls.
3. Try alternate, missing, malformed, stale, linked, and cross-user identifiers.
4. Try prompt injection, hostile web content, SSRF targets, redirects, and provider failures where relevant.
5. Verify denial is fail-closed and does not disclose system state.
6. Verify original media, secrets, and unnecessary personal data are not retained or logged.
7. Verify retries, concurrency, and restart behavior do not duplicate or partially expose state.
8. Add the smallest regression test for each credible failure mode.

## Project-specific checks

- Telegram and Mattermost allowlists are enforced at ingress.
- Every read and write is filtered by verified application `user_id`.
- AI cannot directly mutate the database.
- Browserless rejects loopback, private, metadata, and forbidden targets.
- Original voice, image, and document media are deleted after extraction.
- Link codes expire after ten minutes and are single-use.

## Handoff

Report threat cases attempted, evidence, findings by priority, tests added, and residual risk. Do not approve a change with an unresolved P0/P1 security, privacy, authorization, or data-integrity issue.
