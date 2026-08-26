# Release Acceptance & Verification Plan

This document defines the automated CI release gate and manual pre-production verification matrix required for public release versions.

---

## 1. Automated Verification Gate (CI Pipeline)

The `master` build must pass all automated verification checks prior to release:

- **Python Test Suite**: Unit, PostgreSQL/Alembic integration, and Webhook-to-Outbox tests pass cleanly (`python -m pytest tests` from `python-app`).
- **Container Build Safety**: Python multi-stage Docker build completes successfully (`docker build .` from `python-app`).
- **Secret & Governance Scan**: Zero committed `.env` files, API tokens, Telegram secrets, raw media, or live database dumps.
- **SSRF Validation Test**: `test_ssrf_guard.py` proves internal IP blocking (`127.0.0.1`, private ranges, and cloud metadata IPs).
- **Idempotency Assertions**: Duplicate webhook `update_id` submissions produce exactly one database entry and one outbox reply.
- **Undo ChangeSet Expiration**: Reversible undo change sets expire after 10 minutes and prevent stale state rollbacks.

---

## 2. Pre-Production Acceptance Matrix

Run this matrix prior to updating a live production instance:

| Scenario | Input Type | Pass Criteria | Status |
| --- | --- | --- | --- |
| **Onboarding (`/start`)** | Text Command | User timezone and daily calorie goal are saved in `user_settings`. | NOT VERIFIED |
| **Natural Language Text Log** | Text Message | Meal extracted, logged in `food_entries`/`food_items`, confirmation reply sent, `/today` updated. | NOT VERIFIED |
| **Voice Note Logging** | Audio Note | Transcribed via OpenAI Audio, extracted into structured meal items, audio discarded immediately. | NOT VERIFIED |
| **Photo / Document Logging** | Image / Document | Extracted via OpenAI Vision, nutrition verified, raw bytes discarded from memory/tmpfs. | NOT VERIFIED |
| **Search & History (`/today`)** | Text Command | Returns user-scoped food items for current local day; blocks unauthorized user reads. | NOT VERIFIED |
| **Reversible Undo (`/undo`)** | Text / Command | Executing `/undo` within 10 minutes restores state and updates pinned daily summary. | NOT VERIFIED |
| **Nutrition Provenance** | Tool Call | Items show `OFFICIAL_SOURCE` (Open Food Facts), `PRIVATE_RECORD`, `MANUAL`, or `AI_ESTIMATE`. | NOT VERIFIED |
| **Idempotent Webhook Retry** | HTTP POST | Replaying identical Telegram update ID yields HTTP 200 and zero duplicate entries. | NOT VERIFIED |
| **Scheduled Report Delivery** | Scheduled Job | Morning (08:00) and Evening (22:00) reports deliver once per local calendar day across restarts. | NOT VERIFIED |
| **Mattermost Frontend Link** | `/link` Code | Sending link code in Mattermost DM connects account to Telegram identity within 10 minutes. | NOT VERIFIED |

---

## 3. Production Release Status

**STATUS: NOT CURRENTLY VERIFIED**

Do not mark this repository production-ready from this document alone. Run the current Python CI gate and the manual matrix against the canonical `python-app/` deployment, then record the evidence and date here.

## 4. Latest Local Verification

Verified 2026-08-26 against the canonical Python path:

- `python -m pytest tests` from `python-app`: **115 passed** against an isolated PostgreSQL 17 instance bootstrapped from the relocated V1–V17 baseline and current Alembic revisions.
- `python -m ruff check app tests` from `python-app`: **passed**.
- `docker build --tag food-journal-python-qc:local python-app`: **passed**.
- `docker compose -f python-app/compose.yaml config --quiet`: **passed**.
- Markdown link audit and `git diff --check HEAD`: **passed**.
- Real-model prompt evaluation and the production acceptance matrix: **not run**; they require configured external services and deliberate manual verification.

