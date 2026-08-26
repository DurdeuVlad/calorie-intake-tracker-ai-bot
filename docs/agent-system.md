# Local Agent System

This document is the routing map for agents working in the repository. It explains which file does what; it is not a replacement for the detailed quality checklist. The canonical implementation is `python-app/`; the Java implementation lives in the standalone sister repository `DurdeuVlad/calorie-intake-tracker-ai-bot-java`.

## Control-plane map

| Need | Read | Outcome |
| --- | --- | --- |
| Global rules | [`AGENTS.md`](../AGENTS.md) | Non-negotiable constraints and working standards |
| Task routing | This document | Smallest sufficient context set |
| Quality gates | [`agent-quality-control-checklist.md`](agent-quality-control-checklist.md) | Required planning, testing, review, and handoff checks |
| Product behavior | [`product.md`](product.md), [`requirements.md`](requirements.md) | User goals and acceptance criteria |
| System boundaries | [`architecture.md`](architecture.md) and relevant ADRs | Ownership, data flow, and deliberate decisions |
| Runtime operation | [`local-development.md`](local-development.md), [`configuration.md`](configuration.md), [`operations.md`](operations.md) | Commands, configuration, health, recovery |
| Release readiness | [`acceptance-test-plan.md`](acceptance-test-plan.md), deployment runbook | Release and production gates |
| Repeatable procedure | [`.agents/skills/`](../.agents/skills/) | Focused workflow and validation instructions |
| Completion evidence | [`agent-handoff-template.md`](agent-handoff-template.md) | Standard handoff |

## Read-routing matrix

| Task | Required context | Required validation |
| --- | --- | --- |
| Bug diagnosis | Requirements, architecture, affected code, tests, relevant operations docs | Reproduction, focused regression test, broader applicable suite |
| Feature change | Product, requirements, architecture, affected tests, relevant ADRs | Unit/integration tests, adversarial cases, docs |
| Prompt/model change | `python-app/app/agent/`, prompt tests, terminal fixture, local-development guide | Prompt eval, safety assertions, baseline comparison |
| Tool or external integration | Architecture, configuration, client tests, security docs | Timeout/error/retry tests, boundary review |
| Database change | Requirements, data model, migrations, affected repositories/services | Migration/integration tests, deployment and recovery review |
| Messaging change | Architecture, operations, inbox/outbox code and tests | Replay, concurrency, restart, delivery and ownership checks |
| Media/privacy change | Requirements, architecture, media tests, security guidance | Retention, cleanup, failure, logging, and unauthorized-access checks |
| Release/deployment | Acceptance plan, configuration, operations, deployment runbook | Full release gate and pre-production acceptance matrix |
| Documentation-only change | Target source-of-truth docs, related links and ADRs | Link/path/command accuracy and contradiction check |
| Control-plane change | This document, checklist, skills, handoff template, root instructions | Representative task run plus adversarial review |

## Source precedence

Resolve conflicts in this order:

1. Explicit user requirements, subject to safety and repository invariants.
2. Security and privacy constraints.
3. Enforced tests, database constraints, and runtime behavior.
4. Accepted ADRs.
5. Requirements and acceptance criteria.
6. Architecture, operations, and configuration documentation.
7. README summaries and historical notes.

Code can be wrong or drift from the intended design. Do not silently normalize a contradiction; record it and either fix the source of truth or report the unresolved risk.

## Agent output contract

For any non-trivial task, the agent must provide:

- outcome and user-visible effect;
- changed files and why they changed;
- tests/checks actually run and their results;
- assumptions and decisions;
- failed, skipped, or unavailable checks;
- residual risks and follow-up work;
- the next safe action, if the task is incomplete.

Use the handoff template. A polished summary without evidence is not a quality result.

## Maintenance rules

- Keep this map short and update it when authoritative files move.
- Add a skill when a procedure is repeated and requires judgment or multiple checks.
- Add a document when agents repeatedly rediscover stable system facts.
- Add an ADR when a decision changes a boundary, persistence model, security property, or operational contract.
- Remove stale or duplicated instructions instead of appending another exception.
- Review the control plane after serious defects, prompt regressions, or repeated agent misunderstandings.
