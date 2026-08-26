# Adversarial Review

## Use when

Use before declaring a meaningful implementation, prompt, security, data, messaging, or release change ready.

## Procedure

1. Read the final diff and surrounding callers, tests, stores, queues, and configuration.
2. State the intended behavior and invariants.
3. Trace input through validation, business logic, persistence, delivery, readback, and observability.
4. Attack empty, malformed, duplicate, reordered, stale, concurrent, boundary, timezone/DST, timeout, retry, restart, permission, hostile-input, and partial-failure cases relevant to the change.
5. Check that tests assert durable outcomes rather than only response text or mock calls.
6. Re-run the smallest relevant tests and inspect the final diff for scope expansion.
7. Report blockers before polish.

## Merge gate

Do not recommend merge when the change is untested, silently claims success while durable state is absent or inconsistent, violates ownership/privacy/security, or leaves a release-blocking finding unresolved.

## Handoff

Return: findings with priority, file/symbol, trigger, impact, remediation; commands run; cases considered; residual risks; and a precise recommendation.
