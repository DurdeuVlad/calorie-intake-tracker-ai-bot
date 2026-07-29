CREATE TABLE pending_food_drafts (
  user_id BIGINT PRIMARY KEY REFERENCES food_users(id) ON DELETE CASCADE,
  raw_message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_pending_food_drafts_expires_at ON pending_food_drafts(expires_at);
