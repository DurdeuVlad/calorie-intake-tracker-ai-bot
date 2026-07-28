CREATE TABLE outbound_telegram_messages (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  text TEXT NOT NULL,
  status VARCHAR(16) NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  sent_at TIMESTAMPTZ
);
CREATE INDEX idx_outbound_telegram_messages_ready ON outbound_telegram_messages(status, next_attempt_at, id);
