CREATE TABLE messaging_inbox (
 id BIGSERIAL PRIMARY KEY, provider VARCHAR(32) NOT NULL, event_id TEXT NOT NULL, payload TEXT NOT NULL,
 status VARCHAR(16) NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
 lease_expires_at TIMESTAMPTZ, lease_token UUID, UNIQUE(provider,event_id)
);
CREATE INDEX idx_messaging_inbox_ready ON messaging_inbox(status,next_attempt_at,id);
CREATE TABLE messaging_outbox (
 id BIGSERIAL PRIMARY KEY, provider VARCHAR(32) NOT NULL, conversation_id TEXT NOT NULL, text TEXT NOT NULL,
 status VARCHAR(16) NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
 lease_expires_at TIMESTAMPTZ, lease_token UUID
);
CREATE INDEX idx_messaging_outbox_ready ON messaging_outbox(status,next_attempt_at,id);
