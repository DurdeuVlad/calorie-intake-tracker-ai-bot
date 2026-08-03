ALTER TABLE food_items ADD COLUMN quantity NUMERIC(10,2);
ALTER TABLE food_items ADD COLUMN quantity_unit VARCHAR(16) NOT NULL DEFAULT 'unspecified';

UPDATE food_items
SET quantity = quantity_grams,
    quantity_unit = CASE WHEN quantity_grams IS NULL THEN 'unspecified' ELSE 'g' END;

ALTER TABLE food_items ADD CONSTRAINT chk_food_items_quantity_positive CHECK (quantity IS NULL OR quantity > 0);
ALTER TABLE food_items ADD CONSTRAINT chk_food_items_quantity_unit CHECK (quantity_unit IN ('g','ml','portion','unspecified'));

CREATE TABLE journal_change_sets (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  undone_at TIMESTAMPTZ,
  CONSTRAINT chk_journal_change_set_expiry CHECK (expires_at > created_at)
);

CREATE INDEX idx_journal_change_sets_latest_undoable
  ON journal_change_sets(user_id, created_at DESC, id DESC)
  WHERE undone_at IS NULL;
CREATE INDEX idx_journal_change_sets_expiry ON journal_change_sets(expires_at);

CREATE TABLE journal_change_mutations (
  id BIGSERIAL PRIMARY KEY,
  change_set_id BIGINT NOT NULL REFERENCES journal_change_sets(id) ON DELETE CASCADE,
  sequence_number INTEGER NOT NULL,
  action_type VARCHAR(16) NOT NULL CHECK (action_type IN ('CREATE','EDIT','MOVE','DELETE')),
  before_state JSONB,
  after_state JSONB,
  UNIQUE(change_set_id, sequence_number),
  CONSTRAINT chk_journal_mutation_snapshots CHECK (
    (action_type = 'CREATE' AND after_state IS NOT NULL)
    OR (action_type <> 'CREATE' AND before_state IS NOT NULL)
  )
);
