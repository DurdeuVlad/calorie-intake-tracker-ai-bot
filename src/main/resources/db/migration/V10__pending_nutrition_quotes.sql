CREATE TABLE pending_nutrition_quotes (
  quote_id UUID PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
  quote_type VARCHAR(32) NOT NULL,
  product_name VARCHAR(255) NOT NULL,
  brand VARCHAR(255),
  grams NUMERIC(10,2) NOT NULL,
  calories_per_100g INTEGER NOT NULL,
  barcode VARCHAR(64),
  source_url TEXT,
  estimate_basis VARCHAR(512),
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  CHECK (quote_type IN ('PACKAGED_MATCH', 'AI_ESTIMATE'))
);
CREATE INDEX idx_pending_nutrition_quotes_owner_expiry
  ON pending_nutrition_quotes(user_id, expires_at, created_at);
CREATE INDEX idx_pending_nutrition_quotes_expiry ON pending_nutrition_quotes(expires_at);
