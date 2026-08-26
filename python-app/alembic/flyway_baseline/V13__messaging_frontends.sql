ALTER TABLE food_users ALTER COLUMN telegram_user_id DROP NOT NULL;
CREATE TABLE messaging_identities (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
 provider VARCHAR(32) NOT NULL, external_user_id TEXT NOT NULL,
 UNIQUE(provider, external_user_id)
);
INSERT INTO messaging_identities (user_id, provider, external_user_id)
 SELECT id, 'telegram', telegram_user_id::text FROM food_users WHERE telegram_user_id IS NOT NULL
 ON CONFLICT (provider, external_user_id) DO NOTHING;
CREATE TABLE messaging_routes (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
 provider VARCHAR(32) NOT NULL, conversation_id TEXT NOT NULL,
 UNIQUE(user_id, provider, conversation_id)
);
INSERT INTO messaging_routes (user_id, provider, conversation_id)
 SELECT id, 'telegram', telegram_user_id::text FROM food_users WHERE telegram_user_id IS NOT NULL
 ON CONFLICT (user_id, provider, conversation_id) DO NOTHING;
CREATE TABLE frontend_link_codes (
 code VARCHAR(32) PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
 expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ
);
