# Agent Quality Control System

## Purpose

This checklist defines the local operating system for agents working in this repository. It is intended to make future agent work predictable, evidence-based, safe, reviewable, and useful.

The system must answer five questions for every task:

1. What is the agent actually trying to accomplish?
2. What must the agent read before making decisions?
3. What constraints may not be violated?
4. What evidence proves the work is correct?
5. What remains uncertain, risky, or unfinished?

This document is a build-and-maintain checklist. It describes the target system; unchecked items are work still to be completed.

---

## 1. Goals

### Primary goals

- [ ] Agents inspect the relevant repository context before proposing or changing anything.
- [ ] Agents use authoritative local documentation instead of guessing from stale memory.
- [ ] Agents distinguish requirements, design decisions, implementation facts, assumptions, and hypotheses.
- [ ] Agents make the smallest coherent change that solves the stated problem.
- [ ] Agents protect user data, secrets, ownership boundaries, and external integrations.
- [ ] Agents validate behavior with appropriate tests, checks, and adversarial cases.
- [ ] Agents report evidence honestly, including failed tests, skipped checks, and unresolved risk.
- [ ] Reviewers can reconstruct why a change was made and how it was verified.
- [ ] Repeated work becomes a reusable local skill or documented workflow instead of being reinvented.
- [ ] Prompt and agent behavior can be evaluated against repeatable scenarios rather than judged only by intuition.

### Success criteria

- [ ] A new agent can locate the repository rules, architecture, requirements, development commands, and acceptance gates without asking where they are.
- [ ] A new agent can determine which documents apply to a task from the task type and affected component.
- [ ] An agent cannot declare a task complete without recording changed files, validation performed, and remaining risks.
- [ ] Safety-critical behavior has executable tests or a documented manual verification path.
- [ ] Prompt regressions are detected by evaluation scenarios before they reach production.
- [ ] The control-plane documents remain short enough to route work, while detailed procedures live in focused skills and docs.
- [ ] Contradictions between documents have an explicit resolution process.

### Non-goals

- [ ] Do not create a giant prompt containing every implementation detail.
- [ ] Do not replace tests with prose, checkboxes, or agent confidence.
- [ ] Do not make agents blindly follow stale documentation.
- [ ] Do not make an agent ask for confirmation for every low-risk, reversible action.
- [ ] Do not hide uncertainty behind polished language or a green-looking checklist.
- [ ] Do not use the agent framework as a reason to expand the scope of unrelated changes.
- [ ] Do not treat generated output as authoritative merely because it is fluent.

---

## 2. Repository constraints that every agent must respect

These are the current project invariants. If implementation changes one of them, update the relevant requirements, architecture documentation, ADR, tests, and this checklist in the same change.

### Product and platform

- [ ] Preserve the privacy-first food journaling purpose.
- [ ] Support the supported input modes: text, voice, image, and nutrition-label/document input.
- [ ] Preserve the Telegram and Mattermost frontend boundary.
- [ ] Preserve terminal mode as a local path through the real domain services.
- [x] Use Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL 16+, and Alembic for the canonical implementation.
- [x] Treat the Java implementation as a separate sister repository, not a second source tree in this repository.

### Authorization and ownership

- [ ] Verify the sender before processing an inbound message.
- [ ] Reject non-allowlisted Telegram and Mattermost users without disclosing system state.
- [ ] Scope every read by the verified application user identity.
- [ ] Scope every mutation by the verified application user identity.
- [ ] Test ownership at the application boundary and repository/database boundary where applicable.
- [ ] Treat account linking as an authenticated, expiring, single-use flow.

### AI boundary

- [ ] Treat AI models as interpretation engines, not authorities over application state.
- [ ] Permit mutations only through typed, application-controlled tools.
- [ ] Validate every model-produced argument before execution.
- [ ] Reject malformed, ambiguous, incomplete, or unsafe output rather than guessing.
- [ ] Keep deterministic business rules in application code.
- [ ] Keep macro calculations and persisted state changes outside the model.
- [ ] Record enough structured trace information to evaluate behavior without retaining prohibited media.

### Data integrity and reversibility

- [ ] Claim Telegram `update_id` and Mattermost `post_id` atomically for idempotency.
- [ ] Ensure replayed inbound updates do not create duplicate journal entries or replies.
- [ ] Preserve transaction atomicity for multi-action requests.
- [ ] Create a reversible change set for every journal mutation.
- [ ] Enforce the ten-minute undo window and test expiration behavior.
- [ ] Never alter an applied migration; add a new Alembic revision for persisted-schema changes.
- [ ] Preserve outbox durability and retry behavior.

### Privacy and security

- [ ] Never commit `.env` files, tokens, API keys, Telegram secrets, user data, media, or database dumps.
- [ ] Process original voice, image, and document media transiently.
- [ ] Delete original media immediately after extraction and never persist it in PostgreSQL.
- [ ] Preserve SSRF protections for web search and page fetching.
- [ ] Block loopback, private-network, metadata-service, and other forbidden targets.
- [ ] Do not weaken container, network, or deployment security to make a test pass.
- [ ] Treat external API responses and web content as untrusted input.

### Verification baseline

- [ ] Run `python -m pytest tests` from `python-app` for Python behavior changes.
- [ ] Run relevant focused tests before the full suite when debugging or iterating.
- [ ] Run prompt evaluations for changes to prompts, tool schemas, model routing, or interpretation behavior.
- [ ] Run container/build checks when Docker, configuration, or deployment behavior changes.
- [ ] Use the acceptance plan for release or production-impacting changes.
- [ ] Never report a check as passed if it was not actually run.

---

## 3. Target control-plane system

The system consists of four layers. Each layer has a different job and should not absorb the responsibilities of the others.

| Layer | Job | Primary artifact |
| --- | --- | --- |
| Routing | Tell the agent what to read and which rules apply | `AGENTS.md` files |
| Principles | Define judgment, safety, scope, and evidence standards | `AGENTS.md`, principles doc |
| Procedures | Explain how to perform repeatable work | Local skills with `SKILL.md` |
| Truth | Describe product, architecture, operations, and decisions | `docs/` and ADRs |

### Recommended repository layout

- [ ] Add a root `AGENTS.md` containing only global rules, routing, and non-negotiable invariants.
- [ ] Add scoped `AGENTS.md` files only where a directory has materially different rules.
- [ ] Create a dedicated local skills directory with one focused skill per repeatable workflow.
- [ ] Keep skills procedural: inputs, steps, checks, failure handling, and handoff format.
- [ ] Keep `docs/` as the source of truth for system behavior and operational knowledge.
- [ ] Keep architectural changes in ADRs when they affect boundaries, persistence, security, or operations.
- [ ] Add a concise documentation index that maps task types to the files agents must read.
- [ ] Add an agent handoff template so every completed task has the same minimum evidence.
- [ ] Add prompt evaluation scenarios for critical natural-language behavior.
- [ ] Add a change log or ownership record for the control-plane artifacts themselves.

### Routing rules

- [ ] Root instructions apply to every task unless a more specific instruction explicitly narrows or extends them.
- [ ] A scoped instruction file may add constraints but may not silently weaken root security or privacy rules.
- [ ] The nearest applicable scoped instructions are read before editing files in that scope.
- [ ] The root file points to detailed docs instead of copying their entire contents.
- [ ] Each route names the reason the document matters, not just its path.
- [ ] Routes are maintained when files move or are renamed.
- [ ] Agents record which instructions and docs materially influenced their decisions.

### Source-of-truth precedence

When sources conflict, agents must stop treating the conflict as a minor wording issue.

- [ ] Explicit user requirements define the requested outcome, subject to safety and repository constraints.
- [ ] Security and privacy rules override convenience.
- [ ] Executable tests and database constraints describe current enforced behavior.
- [ ] Accepted ADRs describe intentional architecture decisions.
- [ ] Requirements describe intended business behavior and acceptance criteria.
- [ ] Architecture and operations docs describe the current system and runbooks.
- [ ] Code is evidence of implementation, but may also contain bugs or undocumented drift.
- [ ] README summaries and historical notes are useful indexes, not final authority when they conflict with deeper sources.
- [ ] An unresolved contradiction is reported and either resolved or explicitly carried as a risk.

---

## 4. Agent principles

These principles should be written into the root agent instructions and reinforced by skills and review.

- [ ] Understand the user’s actual goal before optimizing the requested wording.
- [ ] Inspect before editing.
- [ ] Prefer evidence over assumptions.
- [ ] Separate facts, inferences, decisions, and open questions.
- [ ] Make the smallest change that creates durable value.
- [ ] Preserve existing behavior unless the task explicitly changes it.
- [ ] Keep boundaries explicit: frontend, application service, AI, tools, persistence, and delivery.
- [ ] Put deterministic rules in deterministic code.
- [ ] Treat untrusted input as untrusted at every boundary.
- [ ] Fail closed for authorization, privacy, and SSRF decisions.
- [ ] Prefer reversible operations and incremental changes.
- [ ] Do not broaden scope because adjacent cleanup is tempting.
- [ ] Do not confuse a passing unit test with proof of end-to-end correctness.
- [ ] Do not confuse a successful tool call with a successful outcome.
- [ ] State what was not checked.
- [ ] Surface the highest-risk assumption early.
- [ ] Leave the repository more understandable than it was, when the task warrants documentation.
- [ ] Optimize for the next agent’s ability to continue the work.

---

## 5. Standard agent lifecycle

Every non-trivial task should follow this lifecycle. A task may skip a step only when the handoff explicitly explains why.

### Phase A — Intake and framing

- [ ] Restate the requested outcome in concrete terms.
- [ ] Identify whether the task is answer-only, investigation, diagnosis, implementation, review, release, or operations.
- [ ] Identify the user-visible behavior that must change or be preserved.
- [ ] Define what is explicitly in scope.
- [ ] Define what is explicitly out of scope.
- [ ] Identify affected components, integrations, data, and environments.
- [ ] Identify whether the work is reversible.
- [ ] Identify whether the work touches secrets, personal data, migrations, external systems, or production.
- [ ] Write measurable acceptance criteria before implementation when the task is ambiguous or high-risk.
- [ ] Call out consequential ambiguity instead of hiding it in an assumption.

### Phase B — Context discovery

- [ ] Read the applicable `AGENTS.md` files.
- [ ] Read the relevant README or documentation index.
- [ ] Read the requirements for the affected behavior.
- [ ] Read the architecture document for the affected boundary.
- [ ] Read relevant ADRs.
- [ ] Read configuration and operations docs when runtime behavior is involved.
- [ ] Read existing tests before changing behavior.
- [ ] Locate the actual implementation and its callers.
- [ ] Search for duplicate implementations, feature flags, migrations, and prompt references.
- [ ] Check git status before editing.
- [ ] Check for existing user changes and avoid overwriting them.
- [ ] Record the key facts discovered.
- [ ] Record any documentation/code drift found.

### Phase C — Design and plan

- [ ] Describe the current behavior.
- [ ] Describe the desired behavior.
- [ ] Identify the smallest safe design that bridges the two.
- [ ] Define the API, domain, persistence, prompt, or documentation changes required.
- [ ] Define failure behavior before implementing the happy path.
- [ ] Define authorization and ownership behavior.
- [ ] Define idempotency and retry behavior if messages or jobs are involved.
- [ ] Define transaction and rollback behavior if state changes are involved.
- [ ] Define privacy and retention behavior if media or user content is involved.
- [ ] Define observability needed to diagnose failure without exposing secrets or raw media.
- [ ] Decide which tests must be added or updated.
- [ ] Decide which docs, ADRs, skills, or prompts must be updated.
- [ ] Record design decisions that future agents would otherwise have to rediscover.

### Phase D — Implementation

- [ ] Make changes only in the authorized scope.
- [ ] Preserve local style and established abstractions unless there is a stated reason to change them.
- [ ] Keep domain validation outside the model.
- [ ] Keep persistence changes behind the application/domain boundary.
- [ ] Enforce user ownership in every relevant query and mutation.
- [ ] Validate external and model input at the boundary.
- [ ] Handle null, empty, malformed, repeated, delayed, and partial inputs.
- [ ] Handle provider timeout, rate limit, malformed response, and unavailable-service cases.
- [ ] Avoid logging secrets, tokens, raw media, or unnecessary personal content.
- [ ] Add focused tests alongside behavior changes.
- [ ] Update migrations without modifying applied migrations.
- [ ] Update docs when behavior, configuration, or decisions change.
- [ ] Keep unrelated formatting and refactors out of the change.

### Phase E — Validation

- [ ] Run formatting, linting, compilation, and focused tests applicable to the change.
- [ ] Run integration tests when boundaries, persistence, transactions, or external adapters change.
- [ ] Run the full Python verification gate before handoff when feasible.
- [ ] Run prompt evaluations when interpretation behavior changes.
- [ ] Test unauthorized access.
- [ ] Test duplicate/replayed input.
- [ ] Test malformed input.
- [ ] Test provider failure and timeout paths.
- [ ] Test transaction rollback or partial-failure behavior.
- [ ] Test time-window and timezone boundaries where relevant.
- [ ] Test cleanup and retention behavior for media.
- [ ] Test SSRF and network boundary behavior for URL tools.
- [ ] Test restart/retry behavior for outbox and scheduled delivery changes.
- [ ] Inspect the final diff for accidental scope expansion.
- [ ] Inspect generated files and artifacts for secrets or private data.
- [ ] Record exact commands and outcomes.

### Phase F — Adversarial review

- [ ] Assume the happy path is insufficient.
- [ ] Try to bypass user ownership through alternate IDs, null IDs, linked accounts, or repository paths.
- [ ] Try replaying the same inbound event concurrently.
- [ ] Try malformed tool arguments and model outputs.
- [ ] Try ambiguous user intent that should produce clarification rather than mutation.
- [ ] Try stale undo requests, cross-user undo, and repeated undo.
- [ ] Try private, loopback, metadata, redirect, DNS-rebinding, and malformed URLs where web fetching is involved.
- [ ] Try provider failures after partial work has started.
- [ ] Try process restart between database commit and outbound delivery.
- [ ] Try timezone and daylight-saving boundaries for scheduled reports.
- [ ] Try inputs containing secrets, prompt injection, or hostile external content.
- [ ] Verify that failures do not leak system state.
- [ ] Verify that tests prove durable outcomes, not only method calls.
- [ ] Document risks that remain after the attack attempts.

### Phase G — Handoff

- [ ] State the outcome in the first sentence.
- [ ] List changed files and the reason for each.
- [ ] List tests and checks actually run.
- [ ] Report failures, skips, flaky behavior, and environment limitations.
- [ ] Report assumptions made.
- [ ] Report unresolved risks and follow-up work.
- [ ] Report documentation or prompt changes separately from code changes.
- [ ] Provide the next safe action if the task is incomplete.
- [ ] Never say “done,” “verified,” or “production-ready” without evidence.

---

## 6. Prompt quality-control checklist

Use this for system prompts, tool descriptions, evaluator prompts, terminal prompts, and prompt-related configuration.

### Prompt purpose and boundary

- [ ] The prompt has one clearly stated job.
- [ ] The prompt identifies what the model may decide.
- [ ] The prompt identifies what the model must never decide.
- [ ] The prompt says when to ask for clarification.
- [ ] The prompt says when to refuse or return a safe error.
- [ ] The prompt does not imply that the model has authority to mutate state directly.
- [ ] The prompt distinguishes user content from instructions.
- [ ] The prompt treats tool results and web content as untrusted data.
- [ ] The prompt does not depend on undocumented hidden state.
- [ ] The prompt does not make claims the application does not enforce.

### Structured output and tools

- [ ] Output schemas are explicit.
- [ ] Required fields are defined.
- [ ] Units and allowed enum values are defined.
- [ ] Bounds and precision rules are defined in application validation and reflected in the prompt.
- [ ] Tool purposes and limitations are explicit.
- [ ] The model is told not to invent unavailable nutrition facts.
- [ ] Provenance is preserved for every nutrition result.
- [ ] Tool failures have a defined fallback or clarification path.
- [ ] The application rejects unknown fields or unsafe values where appropriate.
- [ ] Prompt instructions do not substitute for server-side authorization.

### Prompt tests and evaluations

- [ ] Add normal examples for each supported input mode.
- [ ] Add multilingual examples relevant to English, Romanian, and mixed-language input.
- [ ] Add ambiguous quantity and unit examples.
- [ ] Add multi-item meal examples.
- [ ] Add direct-calorie and derived-calorie examples.
- [ ] Add clarification cases.
- [ ] Add unsupported or unsafe request cases.
- [ ] Add prompt-injection and hostile-content cases.
- [ ] Add tool failure cases.
- [ ] Add duplicate and retry cases where the prompt participates in action selection.
- [ ] Assert structured behavior, not wording alone.
- [ ] Assert no unauthorized mutation.
- [ ] Assert provenance and confidence behavior.
- [ ] Run repeated evaluations to detect nondeterministic regressions.
- [ ] Store reports without secrets, raw media, or unnecessary personal data.
- [ ] Define a minimum score and hard-fail safety assertions.
- [ ] Compare results against a baseline before accepting a prompt change.

---

## 7. Local skill quality-control checklist

Each skill should make a recurring task easier without turning into an opaque second codebase.

- [ ] The skill has a single primary purpose.
- [ ] The skill has a clear trigger condition.
- [ ] The skill states when it must not be used.
- [ ] The skill identifies required inputs and expected outputs.
- [ ] The skill identifies required docs and source-of-truth files.
- [ ] The skill gives concrete discovery commands or navigation guidance.
- [ ] The skill defines safe operating boundaries.
- [ ] The skill defines validation commands.
- [ ] The skill defines failure handling and escalation conditions.
- [ ] The skill defines what evidence belongs in the handoff.
- [ ] The skill avoids duplicating global principles.
- [ ] The skill avoids hard-coded paths that are not stable.
- [ ] The skill does not authorize destructive actions without explicit scope.
- [ ] The skill does not claim access to tools or systems that may be unavailable.
- [ ] The skill includes examples of good and bad outcomes where ambiguity is likely.
- [ ] The skill has an owner or maintenance responsibility.
- [ ] The skill has a review date or freshness signal.
- [ ] The skill has at least one validation or usage example.
- [ ] The skill is tested by having an agent follow it on a bounded task.
- [ ] The skill is revised when repeated failures expose a missing instruction.

### Suggested initial skills

- [ ] `repo-discovery`: map the repository, applicable instructions, and relevant docs.
- [ ] `feature-development`: plan, implement, test, document, and hand off a feature.
- [ ] `prompt-evaluation`: run and interpret the terminal prompt evaluation suite.
- [ ] `security-boundary-review`: inspect ownership, secrets, media retention, and SSRF behavior.
- [ ] `database-change`: assess schema changes, write Alembic revisions, and verify rollback implications.
- [ ] `messaging-reliability`: test idempotency, inbox claiming, outbox delivery, and retries.
- [ ] `release-acceptance`: execute the automated and manual release acceptance matrix.
- [ ] `incident-diagnosis`: collect evidence, narrow the fault, and avoid unsafe production changes.
- [ ] `documentation-maintenance`: update source-of-truth docs and ADRs without drift.
- [ ] `adversarial-review`: attack changed behavior and report durable risks.

---

## 8. Local documentation quality-control checklist

- [ ] Every important subsystem has one obvious source-of-truth document.
- [ ] Every document states its scope and intended audience.
- [ ] Every document distinguishes current behavior from planned behavior.
- [ ] Every document links to related requirements, code boundaries, tests, and ADRs.
- [ ] Commands are runnable from the repository root or clearly identify their working directory.
- [ ] PowerShell and Bash commands are both provided when platform differences matter.
- [ ] Configuration docs identify required, optional, secret, and unsafe values.
- [ ] Operational docs include health checks, failure symptoms, safe recovery, and escalation.
- [ ] Data-model docs identify migration ownership and applied-migration rules.
- [ ] Acceptance docs contain pass criteria and verification methods.
- [ ] Prompt docs identify model boundaries, tools, schemas, and evaluation coverage.
- [ ] Privacy docs identify collection, processing, retention, and deletion behavior.
- [ ] Architecture docs identify ownership of each decision and mutation.
- [ ] ADRs record context, decision, alternatives, consequences, and status.
- [ ] Dead, duplicate, or contradictory docs are removed or marked clearly.
- [ ] Links are checked after renames or moves.
- [ ] Documentation changes are reviewed for operational accuracy, not only grammar.
- [ ] Documentation is updated in the same change as behavior whenever practical.

### Suggested documentation additions

- [ ] `docs/agent-system.md`: concise map of instructions, skills, docs, and source precedence.
- [ ] `docs/agent-principles.md`: durable reasoning, safety, scope, and evidence principles.
- [ ] `docs/agent-handoff-template.md`: required completion report format.
- [ ] `docs/prompt-contracts.md`: model boundaries, tool contracts, validation, and failure behavior.
- [ ] `docs/evaluation-strategy.md`: datasets, assertions, scoring, baselines, and regression policy.
- [ ] `docs/quality-metrics.md`: quality, safety, reliability, and documentation-health measures.

---

## 9. Quality gates by change type

### Documentation-only change

- [ ] Validate links and referenced paths.
- [ ] Check commands and configuration examples for current accuracy.
- [ ] Check for contradictions with requirements and ADRs.
- [ ] Confirm the change does not accidentally redefine an enforced invariant.

### Application behavior change

- [ ] Add or update unit tests.
- [ ] Add or update integration tests for affected boundaries.
- [ ] Verify authorization and ownership.
- [ ] Verify transaction behavior and failure paths.
- [ ] Verify idempotency if the change handles inbound or scheduled events.
- [ ] Run the full Python verification gate and the relevant Compose/schema checks.
- [ ] Update docs and ADRs when behavior or architecture changes.

### Prompt, model, or tool-contract change

- [ ] Review the AI boundary and typed-tool contract.
- [ ] Add normal, ambiguous, hostile, and failure evaluation cases.
- [ ] Verify application-side validation still rejects unsafe output.
- [ ] Run prompt evaluations against a baseline.
- [ ] Confirm no raw media or sensitive content enters reports.
- [ ] Review cost, latency, retry, and provider-failure implications.

### Database or migration change

- [ ] Confirm the schema change is necessary.
- [ ] Add a new Alembic revision; never rewrite an applied migration.
- [ ] Verify indexes, constraints, ownership columns, and nullability.
- [ ] Verify existing data and deployment ordering.
- [ ] Verify rollback or forward-recovery procedure.
- [ ] Run migration and integration tests against PostgreSQL.
- [ ] Update data-model, operations, and release docs.

### Security, privacy, or integration change

- [ ] Define the threat or privacy model affected.
- [ ] Test denial paths, malformed input, and provider failures.
- [ ] Test logging and retention behavior.
- [ ] Test retry and replay behavior.
- [ ] Perform an independent adversarial review.
- [ ] Document residual risk and monitoring requirements.

### Release or production change

- [ ] Pass the automated release gate.
- [ ] Run the relevant pre-production acceptance matrix.
- [ ] Confirm configuration and secrets are supplied through approved channels.
- [ ] Confirm migration and rollback implications.
- [ ] Confirm backups and restore procedures where data changes are involved.
- [ ] Confirm health checks and observability.
- [ ] Record release evidence and owner sign-off.

---

## 10. Quality metrics and feedback loop

Metrics must improve decisions, not create vanity dashboards.

### Agent work quality

- [ ] Track task completion rate against explicit acceptance criteria.
- [ ] Track reopened tasks and the reason they were reopened.
- [ ] Track defects found after agent handoff.
- [ ] Track tests claimed versus tests actually run.
- [ ] Track scope expansion and unrelated-file changes.
- [ ] Track unresolved-risk quality in handoffs.
- [ ] Track documentation drift discovered during work.

### Product and runtime quality

- [ ] Track duplicate inbound event rate.
- [ ] Track unauthorized access rejection behavior.
- [ ] Track failed and retried outbox delivery.
- [ ] Track undo success and expiration behavior.
- [ ] Track prompt evaluation safety failures separately from quality-score changes.
- [ ] Track nutrition provenance coverage.
- [ ] Track media cleanup failures without retaining media itself.
- [ ] Track SSRF rejection behavior and blocked-target attempts safely.

### Control-plane health

- [ ] Review root instructions when recurring agent mistakes appear.
- [ ] Convert repeated procedural fixes into skills.
- [ ] Convert repeated factual rediscovery into docs.
- [ ] Convert important architectural decisions into ADRs.
- [ ] Remove instructions that conflict, duplicate, or no longer reflect the system.
- [ ] Review skills and docs periodically for freshness.
- [ ] Keep a small regression set of tasks that previously failed.
- [ ] Re-run the regression set after material changes to prompts, skills, or routing.

---

## 11. Rollout plan

### Stage 1 — Establish the foundation

- [ ] Add root `AGENTS.md` with routing, principles, non-negotiable constraints, and handoff requirements.
- [ ] Add `docs/agent-system.md` as the map of the control plane.
- [ ] Add `docs/agent-handoff-template.md`.
- [ ] Link the control-plane docs from `README.md`.
- [ ] Decide the local skills directory and naming convention.
- [ ] Define ownership and review responsibility for agent-control files.

### Stage 2 — Encode repeatable workflows

- [ ] Create `repo-discovery`.
- [ ] Create `feature-development`.
- [ ] Create `prompt-evaluation`.
- [ ] Create `security-boundary-review`.
- [ ] Create `database-change`.
- [ ] Create `messaging-reliability`.
- [ ] Create `release-acceptance`.
- [ ] Create `documentation-maintenance`.
- [ ] Create `adversarial-review`.

### Stage 3 — Add measurable evaluation

- [ ] Define a baseline prompt-evaluation dataset.
- [ ] Add safety assertions that hard-fail on unauthorized or unsafe behavior.
- [ ] Add multilingual and ambiguity coverage.
- [ ] Add regression cases from real defects, sanitized of personal data.
- [ ] Define score thresholds and release policy.
- [ ] Store evaluation reports in a safe, reproducible format.
- [ ] Add a command that a future agent can run without rediscovering setup.

### Stage 4 — Integrate with the Flux framework

- [ ] Define the boundary between repository-local control rules and Flux orchestration.
- [ ] Decide which instructions live in Flux and which remain local to this repository.
- [ ] Prevent duplicate or contradictory policy between Flux and local `AGENTS.md` files.
- [ ] Define how Flux selects skills and required docs.
- [ ] Define how Flux records task state, evidence, and handoffs.
- [ ] Define how Flux invokes adversarial review.
- [ ] Define how Flux consumes prompt-evaluation results.
- [ ] Define failure and escalation behavior when Flux lacks context or tools.
- [ ] Test the integration with representative feature, bug, prompt, migration, and release tasks.
- [ ] Document the final boundary in an ADR.

### Stage 5 — Operate and improve

- [ ] Review the first ten agent tasks using this checklist.
- [ ] Record where agents still guessed, missed context, or overstated confidence.
- [ ] Fix the smallest control-plane layer that would have prevented each failure.
- [ ] Add regression tasks for high-value failures.
- [ ] Review the system monthly or after any serious defect.
- [ ] Retire obsolete instructions instead of endlessly appending new ones.

---

## 12. Definition of done for the control plane

The agent quality-control system is operational only when all of the following are true:

- [ ] A root routing document exists and is discoverable.
- [ ] The source-of-truth hierarchy is explicit.
- [ ] The project’s security, privacy, ownership, AI, data, and reliability invariants are encoded.
- [ ] Agents have a standard lifecycle from intake through adversarial review and handoff.
- [ ] At least the highest-value repeatable workflows have local skills.
- [ ] Prompt changes have repeatable evaluation coverage.
- [ ] Documentation has clear ownership and freshness expectations.
- [ ] The README points agents to the system.
- [ ] A representative agent can complete a bounded task using the system without undocumented tribal knowledge.
- [ ] An independent reviewer can verify the result from the handoff and repository evidence.
- [ ] Known gaps, unresolved risks, and Flux integration boundaries are documented.
- [ ] The system itself has been tested against at least one success case and one failure case.

## Current status

- [x] This design checklist is created.
- [x] Root agent routing is implemented.
- [x] Local skills are implemented.
- [x] Agent-specific supporting docs are implemented.
- [ ] Prompt evaluation policy is implemented.
- [ ] Flux integration boundary is decided and documented.
- [ ] Control-plane rollout is complete.
