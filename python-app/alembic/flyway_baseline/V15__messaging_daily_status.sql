CREATE TABLE messaging_daily_status (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
 provider VARCHAR(32) NOT NULL, conversation_id TEXT NOT NULL, text TEXT NOT NULL,
 remote_message_id TEXT, dirty BOOLEAN NOT NULL DEFAULT TRUE, UNIQUE(user_id,provider,conversation_id)
);
