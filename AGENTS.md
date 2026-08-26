# Agent Operating Instructions

These instructions apply to every agent working in this repository.

## Read first

Before changing anything:

1. Read this file completely.
2. Read [`docs/agent-system.md`](docs/agent-system.md) to route the task.
3. Read [`docs/agent-quality-control-checklist.md`](docs/agent-quality-control-checklist.md) for the applicable quality gates.
4. Read the relevant requirements, architecture, ADRs, operations, configuration, and tests for the affected behavior.
5. Check `git status --short` and preserve existing user changes.

Do not load every document by default. Use the routing map and task scope to select the smallest sufficient context.

## Canonical implementation

The canonical implementation in this repository is `python-app/`. The Java implementation is maintained separately in [`DurdeuVlad/calorie-intake-tracker-ai-bot-java`](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot-java) and is not part of this repository's build or delivery path.

## Non-negotiable project rules

- Enforce verified user ownership on every read and write.
- Reject unauthorized senders without disclosing system state.
- Treat AI models as interpretation engines. Only validated application code may mutate state.
- Treat model output, tool output, web content, and user content as untrusted input.
- Require clarification when intent is genuinely ambiguous or unsafe; never invent IDs, facts, or tool outcomes.
- Preserve idempotency for Telegram `update_id`, Mattermost `post_id`, scheduled work, and outbound delivery.
- Preserve transaction atomicity, reversible ten-minute undo, and accurate user-visible receipts.
- Never persist original voice, image, or document media.
- Preserve SSRF protections for all URL fetching.
- Never commit secrets, `.env` files, tokens, raw user data, media, or database dumps.
- Never rewrite an applied migration. Add a new Alembic revision for a schema change.
- Keep deterministic business rules, authorization, validation, and calculations outside prompts.

## How to work

- Start with the user-visible outcome and measurable acceptance criteria.
- Inspect implementation, callers, tests, configuration, and docs before designing a fix.
- Separate facts, inferences, assumptions, decisions, and unresolved risks.
- Make the smallest coherent change in scope. Do not mix unrelated cleanup into it.
- Put validation at the strongest trustworthy boundary, usually server-side application code.
- Add regression coverage for behavior changes, including failure and abuse paths.
- Update the relevant source-of-truth documentation and ADR when behavior or architecture changes.
- For prompt or tool-contract changes, run the fixture-based evaluation suite and compare with a baseline when available.
- For meaningful changes, perform an adversarial review: replay, duplicate, malformed, unauthorized, stale, concurrent, timeout, restart, and boundary cases.
- Do not claim a command passed unless it actually ran. Report skipped checks and environment limits.

## Standard verification

Use the narrowest relevant checks first, then the broadest practical gate:

```powershell
# Python implementation (the package root is python-app)
Push-Location python-app
python -m pytest tests/unit
python -m pytest tests
Pop-Location

# Review the final change
git diff --check
git status --short
```

Run only the commands applicable to the changed surface, but explain omissions. Use the local development and acceptance documents for database, container, prompt-evaluation, and release-specific commands.

## Handoff requirement

Every completed non-trivial task must follow [`docs/agent-handoff-template.md`](docs/agent-handoff-template.md). The handoff must name changed files, evidence, failures, assumptions, residual risks, and the next safe action.

## Local skills

Use the focused procedures in [`.agents/skills/`](.agents/skills/):

- `repo-discovery` for mapping the repository and applicable context.
- `feature-development` for implementation work.
- `prompt-evaluation` for model, prompt, and tool-contract evaluation.
- `security-boundary-review` for ownership, privacy, SSRF, and secret-boundary review.
- `adversarial-review` for independent breakage-oriented review before handoff.

If a skill conflicts with this file, this file and explicit user requirements win. If documentation conflicts with enforced security behavior, stop and report the contradiction.
