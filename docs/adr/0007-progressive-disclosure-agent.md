# ADR 0007: Progressive disclosure agent architecture

## Status

Accepted

## Context

The v1 agent used a monolithic system prompt (~30 lines containing every rule for every capability) and deterministic reply templates in `journal_agent.py`. The deterministic templates rendered receipts with `if context.romanian` branches, causing a mixed-language bug: the model and the deterministic wrapper used two different language-detection mechanisms (`is_romanian()` regex vs. the model's own judgment), and they disagreed on language for mixed-language input.

The v1 architecture also made the bot feel like a "state machine with an LLM bolted on": the model triggered a tool, and a hardcoded template wrote the reply. This prevented the model from adapting tone, context, or language naturally.

The flat tool list (20+ tools in one list) and the 990-line `journal_tool_executor.py` made it hard to add new capabilities without touching unrelated code.

## Decision

v2.0 adopts a **progressive disclosure** architecture with three pillars:

### 1. Core prompt + capability docs

The system prompt is split into:
- **Core prompt** (~15 lines): role, safety boundaries, tool-use principles, language rule, receipt format, and a one-line capability index.
- **Capability docs** (markdown files in `app/agent/capabilities/`): `nutrition.md`, `portions.md`, `combos.md`, `editing.md`, `daily_totals.md`, `onboarding.md`, `aliases.md`. Each covers one concern and is independently readable.

The model fetches capability docs on demand via the `load_instructions(topic)` tool. This keeps the core prompt small and lets the model load detailed rules only when the current message falls into a specific category.

Capability docs are server-trusted content (stored as files, not model-generated), so they are not subject to prompt-injection concerns. Tool results from `search_web`/`fetch_web_page` remain untrusted external text.

### 2. Model-driven replies from structured tool results

Tool results are enriched with receipt-ready structured data: `calories`, `description`, `date`, `nutritionSource`, `nutritionConfidence`, `derivation`, `undoDeadline`, `sourceUrl`, `sourceName`. The normal deterministic reply templates (`_canonical_reply`, `_meal_receipt`, `_media_lines`, `_VERBS`) are removed from `journal_agent.py`. The model writes the full reply from the structured tool result. Server-rendered fallback acknowledgements are retained for provider failure after any durable tool result, including journal mutations and pending nutrition choices, so the user is never told to retry an action that already committed.

The system prompt instructs the model: "After a successful `apply_journal_actions`, write a short receipt: what was logged, calories, source/confidence, derivation if available, and the undo deadline."

### 3. Model decides language

The `romanian: bool` field on `AgentContext` and the `is_romanian()` call in the agent path are removed. The system prompt has one line: "Reply in the language the user used. If mixed, use the dominant one." `is_romanian()` is kept only for slash-command dispatch (`/today`, `/help`), which bypasses the model and uses the stored `preferred_language`.

## Relationship to ADR 0003

ADR 0003 ("AI is an interpreter, not an authority") remains in force. The AI boundary is unchanged: the model is still an interpretation engine, mutations still go through typed application-controlled tools, and validation remains in application code. This ADR changes only:
- **Prompt organization**: monolithic → core + capability docs (progressive disclosure).
- **Reply rendering**: deterministic templates → model-written replies from structured tool results.
- **Language selection**: `is_romanian()` regex → model decision.

The security properties of ADR 0003 (no direct model authority over state, server-side validation, untrusted tool/web output) are preserved.

## Consequences

- **+1 tool call** for unfamiliar scenarios: the model calls `load_instructions(topic)` before acting on nutrition, portions, combos, editing, daily totals, or onboarding requests. This is a deliberate trade-off for a smaller core prompt.
- **Receipts may vary in tone**: the model writes replies, so exact wording is no longer deterministic. The eval suite (issue #109) asserts structured behavior (correct tool called, correct calories, undo available) rather than exact strings.
- **Requires eval suite**: model-driven replies need a comprehensive eval suite to maintain quality. Issue #109 adds fraction, mixed-language, combo, receipt-quality, prompt-injection, and tool-failure eval fixtures.
- **Tool modules**: `journal_tool_executor.py` is split into focused modules (`app/tools/journal_actions.py`, `nutrition.py`, `portion.py`, `settings.py`, `planning.py`, `instructions.py`, `registry.py`, `shared.py`) so new capabilities can be added without touching unrelated code.
- **New capabilities**: `get_weekly_summary`, `search_food_history`, and custom food aliases (`save_alias`/`resolve_alias`) are added in Phase 4.

## Tool grouping

Tools are organized into named groups (all tools remain available to the model; no dynamic routing in v2.0):

- **Always-available**: `get_today_summary`, `get_weekly_summary`, `search_entries`, `search_food_history`, `get_entry`, `apply_journal_actions`, `undo_last_change`, `load_instructions`
- **Nutrition**: `resolve_nutrition`, `lookup_food`, `get_private_food`, `search_packaged_food`, `get_pending_nutrition_quotes`, `select_packaged_food`, `search_web`, `fetch_web_page`, `estimate_food`, `save_private_food`
- **Aliases**: `save_alias`, `resolve_alias`
- **Settings**: `get_settings`, `update_settings`
- **Planning**: `plan_todos`, `complete_todo`

Future optimization (post-v2.0): send only always-available + loaded-capability tools. Requires a routing layer. Deferred.


## Supervised hardening: mutation receipts and bounded ordinary-food logging

- After a journal mutation attempt, final receipts are rendered from server-owned action rows, including failures, estimate labels and a fresh todaySummary read after flush. Model prose cannot substitute a different mutation result. Provider outages use the same receipt. A turn cannot replay a batch after any success; an all-failed batch gets at most one retry. Tool-budget exhaustion states incomplete work rather than inventing a missing user detail.
- Important residual: a no-tool free-text answer still has no typed journal-claim field and can falsely assert a save. The adversarial terminal-contract test is deliberately xfailed; this is an unmet gate, not an enforced guarantee. Closing it requires a structured terminal reply separating conversational text from journal outcome/receipt references, with server-validated references and server-only mutation claims; no success-word regex is used.
- Ordinary foods use direct transparent estimates, with targeted lookup for products/restaurants and explicit verification. Supplied calories and printed values at their real basis remain authoritative. Six estimates plus instruction loading, one batch and readback use nine tool calls under the unchanged ten-call cap.
- EDIT quantity/unit replace a single persisted food item's quantity; same-unit quantity-only edits rescale its stored total. A changed basis needs replacement calories. Numeric corrections invalidate stale nutrition evidence/macros, retaining originals in the Undo snapshot. Owned search/get results expose structured quantities. Direct ml/portion AI totals retain ai_estimate/estimate without inventing grams or verified provenance; their free-text basis is included in the receipt, not a new durable evidence schema.


### Round-two receipt corrections

Mutation calls require the model to select a validated en/ro replyLanguage for copy only; outcome data, ownership and validation are unchanged. Missing language retains the legacy English fallback, not a language classifier. The prompt instructs normal calls to supply the dominant message language; actual language selection remains unmeasured without live-model evaluation.

Every action result has a server-assigned one-based actionIndex and bounded requestedDescription. Owned expired quotes can supply identity but never authorize consumption; foreign choices reveal no product name. Earlier failed attempts are omitted only when a later successful action has the same server-labelled actionKey. The post-success stop remains terminal: it is not selective failed-item retry support.

Replacement quantities are rendered as the authoritative new quantity/unit; stale names are explicitly entry labels, not corrected amounts. Direct estimate receipts show a concise assumption basis. Submitted packaged selections are accounted for by mutation outcomes and cannot also say Not logged; genuinely unsubmitted selections can. No-tool false-save remains an unmet gate: an envelope with unrestricted conversational prose would not close it. A full guarantee would need constrained renderable response types and current-turn/current-user validated receipt references, rejecting forged/stale/foreign references with no raw-prose fallback, trading away free conversational flexibility. That redesign is outside this batch.
