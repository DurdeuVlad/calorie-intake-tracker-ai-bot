# ADR 0002: Webhook verification and idempotency

**Status:** Accepted

Accept Telegram updates only at an HTTPS webhook endpoint protected by Telegram's secret-token header. Persist and uniquely constrain `update_id` before processing. Duplicate claims return success without repeating business actions. Edited Telegram messages follow an explicit update path and must not silently create a new eating event.
