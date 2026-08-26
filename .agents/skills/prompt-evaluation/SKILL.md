# Prompt Evaluation

## Use when

Use for system prompts, tool schemas, model routing, interpretation behavior, evaluation fixtures, or response-policy changes.

## Read

- `python-app/app/agent/system_prompt.py`.
- `python-app/app/agent/tool_schemas.py`.
- `python-app/app/terminal/fixtures/text-journal.json`.
- `python-app/tests/unit/test_agent_instructions.py`.
- `docs/requirements.md`, `docs/architecture.md`, and `docs/local-development.md`.

## Procedure

1. State the intended model behavior and the application-side invariant that enforces it.
2. Add or update normal, multilingual, ambiguous, hostile, malformed, and provider-failure scenarios as relevant.
3. Assert durable state, tool choice, safety, provenance, and reply quality separately.
4. Ensure critical safety assertions hard-fail release readiness.
5. Run focused prompt tests.
6. Run the fixture evaluation with an isolated developer database and configured repeats.
7. Compare against a baseline when available.
8. Inspect reports for safety failures, score changes, leakage, duplicate mutations, and nondeterminism.
9. Do not store raw media, credentials, or unnecessary personal data in fixtures or reports.

## Minimum evaluation cases

- Greeting must not mutate the journal.
- Explicit calories must be preserved.
- Ambiguous intent must clarify rather than guess dangerously.
- Daily totals must use the summary path.
- Edit/delete/move must search first and remain user-scoped.
- Duplicate inbound events must not duplicate state.
- Prompt injection must not bypass tools or validation.
- Search/tool failure must not produce fake nutrition facts.

## Handoff

Report fixture version, repeats, model/configuration, score by category, critical safety result, baseline delta, failures, and residual nondeterminism.
