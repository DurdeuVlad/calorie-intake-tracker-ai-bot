CREATE TABLE agent_runs (
  correlation_id UUID PRIMARY KEY,
  telegram_update_id BIGINT,
  actor_user_id BIGINT REFERENCES food_users(id) ON DELETE SET NULL,
  input_type VARCHAR(32) NOT NULL,
  model_alias VARCHAR(128),
  outcome VARCHAR(32) NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  tool_call_count INTEGER NOT NULL DEFAULT 0,
  final_reply_summary TEXT,
  error_category VARCHAR(64)
);
CREATE INDEX idx_agent_runs_started_at ON agent_runs(started_at DESC);
CREATE INDEX idx_agent_runs_actor_started_at ON agent_runs(actor_user_id, started_at DESC);
CREATE INDEX idx_agent_runs_outcome_started_at ON agent_runs(outcome, started_at DESC);

CREATE TABLE agent_tool_events (
  id BIGSERIAL PRIMARY KEY,
  agent_run_id UUID NOT NULL REFERENCES agent_runs(correlation_id) ON DELETE CASCADE,
  sequence_number INTEGER NOT NULL,
  tool_name VARCHAR(128) NOT NULL,
  arguments_summary TEXT,
  result_code VARCHAR(64) NOT NULL,
  result_summary TEXT,
  latency_ms BIGINT,
  failure_category VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(agent_run_id, sequence_number)
);
CREATE INDEX idx_agent_tool_events_run_sequence ON agent_tool_events(agent_run_id, sequence_number);
CREATE INDEX idx_agent_tool_events_name_created_at ON agent_tool_events(tool_name, created_at DESC);

CREATE TABLE integration_events (
  id BIGSERIAL PRIMARY KEY,
  agent_run_id UUID REFERENCES agent_runs(correlation_id) ON DELETE CASCADE,
  provider VARCHAR(64) NOT NULL,
  operation VARCHAR(128) NOT NULL,
  model_alias VARCHAR(128),
  outcome VARCHAR(32) NOT NULL,
  latency_ms BIGINT,
  error_category VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_integration_events_created_at ON integration_events(created_at DESC);
CREATE INDEX idx_integration_events_provider_created_at ON integration_events(provider, created_at DESC);

CREATE TABLE agent_trace_payloads (
  id BIGSERIAL PRIMARY KEY,
  agent_run_id UUID NOT NULL REFERENCES agent_runs(correlation_id) ON DELETE CASCADE,
  payload_type VARCHAR(32) NOT NULL,
  encrypted_payload TEXT NOT NULL,
  redacted_preview VARCHAR(512) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(agent_run_id, payload_type)
);

CREATE TABLE audit_events (
  id BIGSERIAL PRIMARY KEY,
  actor_type VARCHAR(32) NOT NULL,
  actor_identifier VARCHAR(255) NOT NULL,
  action VARCHAR(128) NOT NULL,
  target_type VARCHAR(64),
  target_identifier VARCHAR(255),
  reason VARCHAR(512),
  metadata_summary TEXT,
  occurred_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_audit_events_occurred_at ON audit_events(occurred_at DESC);
CREATE INDEX idx_audit_events_actor_occurred_at ON audit_events(actor_identifier, occurred_at DESC);
CREATE FUNCTION prevent_audit_event_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events are immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_events_immutable
  BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();

ALTER TABLE outbound_telegram_messages
  ADD COLUMN agent_run_id UUID REFERENCES agent_runs(correlation_id) ON DELETE SET NULL;
CREATE INDEX idx_outbound_telegram_messages_agent_run_id ON outbound_telegram_messages(agent_run_id);
