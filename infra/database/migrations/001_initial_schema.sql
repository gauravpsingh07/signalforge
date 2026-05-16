-- SignalForge Phase 1 metadata foundation.
-- PostgreSQL/Neon-compatible schema for auth, projects, and hashed API keys.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  description TEXT,
  environment_default TEXT NOT NULL DEFAULT 'production',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, slug)
);

CREATE TABLE IF NOT EXISTS api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  key_prefix TEXT NOT NULL,
  last_used_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS worker_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type TEXT NOT NULL,
  entity_id UUID,
  status TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  error_message TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS event_fingerprints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  service TEXT NOT NULL,
  environment TEXT NOT NULL,
  level TEXT NOT NULL,
  status_code INTEGER,
  fingerprint_hash TEXT NOT NULL,
  normalized_message TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  occurrence_count INTEGER NOT NULL DEFAULT 1,
  UNIQUE(project_id, fingerprint_hash)
);

CREATE TABLE IF NOT EXISTS events_metadata (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_id TEXT NOT NULL,
  api_key_prefix TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  service TEXT NOT NULL,
  environment TEXT NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  normalized_message TEXT NOT NULL,
  fingerprint_hash TEXT NOT NULL,
  status_code INTEGER,
  latency_ms INTEGER,
  trace_id TEXT,
  request_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(project_id, event_id)
);

CREATE TABLE IF NOT EXISTS metric_rollups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  service TEXT NOT NULL,
  environment TEXT NOT NULL,
  bucket_start TIMESTAMPTZ NOT NULL,
  bucket_size_seconds INTEGER NOT NULL DEFAULT 60,
  total_events INTEGER NOT NULL DEFAULT 0,
  error_events INTEGER NOT NULL DEFAULT 0,
  warning_events INTEGER NOT NULL DEFAULT 0,
  fatal_events INTEGER NOT NULL DEFAULT 0,
  latency_avg_ms NUMERIC,
  latency_p95_ms NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(project_id, service, environment, bucket_start, bucket_size_seconds)
);

CREATE TABLE IF NOT EXISTS anomalies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  service TEXT NOT NULL,
  environment TEXT NOT NULL,
  anomaly_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  score NUMERIC NOT NULL,
  baseline_value NUMERIC,
  observed_value NUMERIC,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  fingerprint_hash TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_project_id ON api_keys(project_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_worker_jobs_status ON worker_jobs(status);
CREATE INDEX IF NOT EXISTS idx_worker_jobs_job_type ON worker_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_event_fingerprints_project_id ON event_fingerprints(project_id);
CREATE INDEX IF NOT EXISTS idx_events_metadata_project_timestamp ON events_metadata(project_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_metadata_filters ON events_metadata(project_id, service, environment, level);
CREATE INDEX IF NOT EXISTS idx_metric_rollups_project_bucket ON metric_rollups(project_id, bucket_start DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_project_status ON anomalies(project_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomalies_open_dedupe
  ON anomalies(project_id, service, environment, anomaly_type, window_start, COALESCE(fingerprint_hash, ''))
  WHERE status = 'open';

-- Later phases add:
-- incidents, incident_events, and alerts.
