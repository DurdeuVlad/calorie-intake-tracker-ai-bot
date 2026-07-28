CREATE TABLE nutrition_source_cache (
  id BIGSERIAL PRIMARY KEY,
  barcode VARCHAR(64) NOT NULL UNIQUE,
  product_name VARCHAR(255) NOT NULL,
  calories_per_100g INTEGER,
  protein_per_100g NUMERIC(10,2),
  carbs_per_100g NUMERIC(10,2),
  fat_per_100g NUMERIC(10,2),
  source_url TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE private_foods (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES food_users(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  calories_per_100g INTEGER,
  protein_per_100g NUMERIC(10,2),
  carbs_per_100g NUMERIC(10,2),
  fat_per_100g NUMERIC(10,2),
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(user_id, name)
);
