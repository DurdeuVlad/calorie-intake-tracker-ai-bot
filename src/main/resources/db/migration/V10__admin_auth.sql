CREATE TABLE admin_users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(320) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMPTZ
);

CREATE TABLE admin_api_keys (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  key_prefix VARCHAR(32) NOT NULL,
  key_hash CHAR(64) NOT NULL UNIQUE,
  scopes TEXT NOT NULL,
  expires_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at TIMESTAMPTZ
);
CREATE INDEX idx_admin_api_keys_active ON admin_api_keys(revoked_at, expires_at);

CREATE TABLE admin_audit_events (
  id BIGSERIAL PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actor_type VARCHAR(32) NOT NULL,
  actor_id VARCHAR(255),
  action VARCHAR(96) NOT NULL,
  target_type VARCHAR(64),
  target_id VARCHAR(255),
  correlation_id UUID,
  metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_admin_audit_events_occurred_at ON admin_audit_events(occurred_at DESC);
CREATE FUNCTION prevent_admin_audit_event_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'admin_audit_events are immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER admin_audit_events_immutable
  BEFORE UPDATE OR DELETE ON admin_audit_events
  FOR EACH ROW EXECUTE FUNCTION prevent_admin_audit_event_mutation();
