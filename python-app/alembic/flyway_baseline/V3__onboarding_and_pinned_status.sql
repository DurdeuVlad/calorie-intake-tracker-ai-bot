ALTER TABLE user_settings ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_settings ADD COLUMN onboarding_stage VARCHAR(32) NOT NULL DEFAULT 'TIMEZONE';
CREATE TABLE pinned_daily_status (
 id BIGSERIAL PRIMARY KEY,
 user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
 chat_id BIGINT NOT NULL,
 local_date DATE NOT NULL,
 desired_text TEXT NOT NULL,
 desired_version BIGINT NOT NULL,
 delivered_version BIGINT NOT NULL,
 telegram_message_id BIGINT,
 updated_at TIMESTAMPTZ NOT NULL,
 UNIQUE(user_id, chat_id)
);
CREATE INDEX idx_pinned_daily_status_pending ON pinned_daily_status(id) WHERE desired_version > delivered_version;
