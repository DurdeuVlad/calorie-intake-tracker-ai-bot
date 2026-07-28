ALTER TABLE pinned_daily_status ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'PENDING';
ALTER TABLE pinned_daily_status ADD COLUMN lease_expires_at TIMESTAMPTZ;
ALTER TABLE pinned_daily_status ADD COLUMN lease_token UUID;
