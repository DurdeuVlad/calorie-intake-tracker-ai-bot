CREATE TABLE telegram_update_inbox (
  update_id BIGINT PRIMARY KEY,
  telegram_user_id BIGINT NOT NULL,
  chat_id BIGINT NOT NULL,
  payload TEXT NOT NULL,
  status VARCHAR(16) NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL,
  lease_expires_at TIMESTAMPTZ,
  lease_token UUID,
  correlation_id UUID NOT NULL,
  last_error_category VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_telegram_update_inbox_ready ON telegram_update_inbox(status, next_attempt_at, update_id);
CREATE INDEX idx_telegram_update_inbox_user_order ON telegram_update_inbox(telegram_user_id, update_id, status);

ALTER TABLE outbound_telegram_messages ADD COLUMN source_update_id BIGINT;
CREATE INDEX idx_outbound_telegram_messages_source_update ON outbound_telegram_messages(source_update_id);
