CREATE TABLE pending_agent_actions (
  user_id BIGINT PRIMARY KEY REFERENCES food_users(id) ON DELETE CASCADE,
  action_type VARCHAR(16) NOT NULL,
  entry_id BIGINT NOT NULL REFERENCES food_entries(id) ON DELETE CASCADE,
  description TEXT,
  calories INTEGER,
  summary TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_pending_agent_actions_expiry ON pending_agent_actions(expires_at);
