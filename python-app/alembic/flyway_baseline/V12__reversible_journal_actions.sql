ALTER TABLE food_entries ADD COLUMN deleted_at TIMESTAMPTZ;
CREATE INDEX idx_food_entries_active_user_eaten_at ON food_entries(user_id, eaten_at) WHERE deleted_at IS NULL;

CREATE TABLE journal_undo_actions (
  user_id BIGINT PRIMARY KEY REFERENCES food_users(id) ON DELETE CASCADE,
  entry_id BIGINT NOT NULL REFERENCES food_entries(id) ON DELETE CASCADE,
  action_type VARCHAR(16) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_journal_undo_actions_expiry ON journal_undo_actions(expires_at);
