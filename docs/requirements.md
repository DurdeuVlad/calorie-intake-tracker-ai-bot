# Functional Requirements & Acceptance Criteria

---

## Core Business Rules

1. **Idempotency & Deduplication**:
   - Each inbound update (Telegram `update_id` or Mattermost `post_id`) is claimed atomically in PostgreSQL (`processed_updates`).
   - Network retries or replayed webhooks produce zero duplicate food entries or outbox messages.

2. **Strict User Ownership & Access Control**:
   - Every database query and mutation is strictly filtered by the caller's verified `user_id`.
   - Messages from users not explicitly listed in `ALLOWED_TELEGRAM_USER_IDS` or `ALLOWED_MATTERMOST_USER_IDS` are rejected immediately without disclosing system state.

3. **Transaction Safety & Atomicity**:
   - Inbound messages may trigger multiple food entry mutations. Each requested action is validated independently.
   - Successful actions are committed and reported explicitly. An unexpected error during processing rolls back the transaction, preventing partial corrupt writes.

4. **10-Minute Reversible Undo**:
   - Every journal modification generates a message-level snapshot (`JournalChangeSet` / `JournalMutation`).
   - Users can execute `/undo` or request an undo in natural language within 10 minutes to restore previous state.

5. **Structured Quantities & Units**:
   - Calories may be declared directly or derived from structured quantities.
   - Supported quantity units: grams (`g`), millilitres (`ml`), portions (`portion`), or `unspecified`.

6. **Transient Media Lifecycle (Zero Retention)**:
   - Voice notes, images, and documents are downloaded transiently to memory/tmpfs.
   - Original media files are deleted immediately following transcription or vision extraction. No binary media is saved to PostgreSQL or persistent disk volumes.

7. **Nutrition Provenance**:
   - Every logged food item tracks its provenance source: `OFFICIAL_SOURCE` (Open Food Facts), `PRIVATE_RECORD`, `MANUAL`, or `AI_ESTIMATE`.

8. **AI Execution Boundaries**:
   - AI models act strictly as interpretation engines calling typed tools (`JournalToolExecutor`).
   - Ambiguous or incomplete model outputs require clarification instead of guessing user intent.

9. **Multi-Frontend Linking**:
   - Accounts across Telegram and Mattermost can be linked using `/link`. Codes expire after 10 minutes and can be redeemed once.

10. **Timezone-Aware Reporting & Pinned Status**:
    - Users configure their IANA timezone during onboarding (`/start` or `/settings`).
    - Scheduled morning (08:00 default) and evening (22:00 default) reports deliver once per local calendar day.
    - Pinned daily status updates dynamically reflect total calories and macro intake for the current local day.

---

## Acceptance Criteria Matrix

| Domain | Acceptance Criteria | Verification Method |
| --- | --- | --- |
| **Authentication** | Senders not on allowlist are rejected cleanly without side effects. | Integration test & manual check. |
| **Idempotency** | Sending the same update twice creates exactly one food entry and one reply message. | `processed_updates` ledger assertions. |
| **Natural Language** | Text, voice, photos, and document inputs extract food items, quantities, and calories. | Automated eval suite & integration tests. |
| **10-Minute Undo** | `/undo` within 10 minutes reverts the exact previous message mutations; `/undo` after 10 minutes fails gracefully. | ChangeSet expiration integration tests. |
| **Nutrition Lookup** | Open Food Facts and SearxNG return valid nutrition data; failure falls back to AI estimation with `AI_ESTIMATE` provenance. | Mocked tool boundary tests. |
| **Web Fetching & SSRF** | `fetch_web_page` rejects internal IP ranges (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, cloud metadata endpoints). | Unit tests for `BrowserlessClient`. |
| **Scheduled Reports** | Morning and evening reports fire once per day per user timezone; retries across restarts do not send duplicate reports. | `report_deliveries` unique index verification. |

