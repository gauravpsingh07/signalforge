# System Design

## Intended Flow

1. A client application sends events to `POST /v1/events` with a project API key.
2. FastAPI validates the request, checks rate limits, enqueues the event, and returns quickly.
3. A Python worker consumes queued jobs outside the request path.
4. The worker normalizes events, computes fingerprints, writes raw events to an event store, and updates rollups.
5. Deterministic anomaly detection compares current windows against baselines.
6. Related anomalies and fingerprints are grouped into incidents.
7. Gemini generates structured summaries for significant incidents.
8. Discord alerts are sent for critical incidents and recoveries.
9. The SvelteKit dashboard shows service health, events, incidents, and pipeline health.

## Current Implemented Scope

SignalForge currently includes the completed ingestion, incident, summary, alerting, pipeline observability, demo-hardening, deployment-documentation, and final presentation scope:

- Monorepo structure.
- SvelteKit login, dashboard, project list, and project API key settings screens.
- FastAPI health, auth, project, and API key routes.
- JWT access tokens for dashboard authentication.
- Password hashes using PBKDF2-HMAC-SHA256.
- API key generation with `sf_demo_` or `sf_live_` prefixes.
- API key hashing with an environment-driven pepper.
- Ownership checks on project and API key operations.
- `POST /v1/events` and `POST /v1/events/batch` with ingestion API-key auth.
- Event payload validation and payload-size guards.
- In-memory rate limiting fallback for local development.
- Queue abstraction that writes to Upstash Redis REST when configured or local JSONL otherwise.
- `worker_jobs` records for queued ingestion jobs.
- Python worker queue consumer.
- Event normalization for service, environment, level, timestamp, received_at, and metadata.
- Message normalization and deterministic fingerprint hashing.
- Idempotent event storage with local JSONL fallback and PostgreSQL `events_metadata`.
- Fingerprint updates with local JSON fallback and PostgreSQL `event_fingerprints`.
- Event search API and frontend event explorer.
- Worker-updated 60-second rollup buckets.
- Metrics API for dashboard time series, service list, error rate, p95 latency, and active incident count.
- Project overview charts and service health table.
- Dashboard project cards with recent event volume and error rate.
- Error-rate spike detection using rolling baselines and z-scores.
- Latency spike detection using p95 baseline comparisons.
- New repeated error detection from fingerprint counts.
- Fatal event burst detection.
- Anomaly API and frontend anomaly table/timeline.
- Incident grouping from related anomalies and fingerprints.
- Manual incident resolution.
- Simple auto-resolution after a configurable cooldown with no related anomaly updates.
- Incident list and incident detail APIs.
- Frontend incident list and detail pages with timeline, related anomalies, related fingerprints, event samples, and structured AI summary rendering.
- Gemini incident summary service with deterministic local fallback when `GEMINI_API_KEY` is not configured.
- AI input sanitization that redacts API keys, bearer tokens, JWTs, passwords, cookies, secrets, and authorization strings.
- Summary caching in incident records so incidents are not regenerated for every event.
- Discord alert delivery for high/critical incident open, high-to-critical escalation, and resolved recovery states.
- Alert deduplication by incident, channel, and alert type.
- Alert logging with `sent`, `skipped`, and `failed` statuses.
- Alert history in incident detail and project settings.
- Authenticated `/pipeline-health` and `/worker-health` APIs.
- Recent worker job listing with status, type, and time filters.
- Failed and dead-letter job counts.
- Worker processing timestamps and latency calculations.
- Queue provider and local queue depth reporting.
- Alert delivery failure count.
- Safe retry endpoint for failed or dead-letter jobs with available payload references.
- Frontend `/pipeline-health` dashboard with job counters, latency, failures, queue mode, and recent worker jobs.
- Demo scripts for normal traffic, error spikes, latency spikes, recovery traffic, and local fallback reset.
- Request-size guard that rejects oversized API requests with a consistent JSON error.
- Bounded pagination limits on project collection routes and pipeline job listing.
- Constant-time API key hash comparison.
- Dashboard retry buttons, accessible filter labels, chart empty states, and sanitized event-message rendering.
- Tests for script dry-runs, request-size errors, pagination validation, local queue behavior, and requeue append behavior.
- Render blueprint for the FastAPI API and Python worker.
- Vercel SvelteKit app config for the frontend.
- Deployment documentation for Neon migrations, Upstash Redis REST queue setup, frontend/API/worker provider commands, and smoke testing.
- Free-tier strategy documentation covering provider caveats, rate limits, batching, fallbacks, and portfolio-scale assumptions.
- Final README and screenshot placeholder documentation with no fake deployed URLs, fake screenshots, production SLA claims, or resume bullet sections.
- PostgreSQL metadata schema for users, projects, api_keys, worker_jobs, events_metadata, event_fingerprints, metric_rollups, anomalies, incidents, incident_events, and alerts.
- Docker Compose for local Postgres and Redis.
- GitHub Actions skeleton.

## API Key Hashing and Ownership Model

Raw ingestion API keys are generated by the API and returned only in the create response. The database stores only a key prefix for display and a hash produced from the raw key plus `API_KEY_PEPPER`. Listing keys returns masked prefixes and never returns raw keys or hashes.

Every project belongs to a user. Project reads, updates, and API key management require a valid JWT and check that the authenticated user owns the project before returning data or mutating state.

## Async Ingestion Boundary

The ingestion API authenticates the raw project key, validates the event, applies rate limits, creates a queued `worker_jobs` record, writes a queue payload, updates `last_used_at`, and returns `202 Accepted`. It does not call Gemini, ClickHouse/Tinybird, anomaly detection, or Discord. This keeps request latency bounded and preserves the distributed-system boundary between API ingestion and background processing.

## Worker Processing

The worker reads queued jobs from the same local JSONL or Redis/Upstash-style queue abstraction used by the API. Each event is normalized, fingerprinted, stored idempotently, and marked complete. Failed jobs increment attempts and move to `dead_letter` after the configured maximum attempts.

Client-provided `eventId` values are used for idempotency per project. Repeated timeout messages with different request IDs, UUIDs, timestamps, or variable numbers normalize to the same fingerprint input.

## Metric Rollups

After a worker stores a new event, it updates the matching `project_id + service + environment + bucket_start + bucket_size_seconds` rollup. The local fallback stores latency samples so avg and p95 can be computed exactly for portfolio-scale demos. The PostgreSQL path recomputes the current bucket from `events_metadata` after each event, which is simple and reliable at demo scale and keeps the logic modular for a future ClickHouse/Tinybird query implementation.

## Anomaly Detection

Gemini is not used for detection. The worker runs deterministic checks after rollup and fingerprint updates:

```text
current_error_rate = (error_events + fatal_events) / total_events
z_score = (current_error_rate - baseline_mean) / baseline_stddev

high error-rate anomaly:
  total_events >= min_sample_count
  current_error_rate > 0.20
  z_score >= 3.0

critical error-rate anomaly:
  total_events >= min_sample_count
  current_error_rate > 0.50

latency anomaly:
  total_events >= min_sample_count
  current_p95 > baseline_p95 * 3
  current_p95 > 1000ms

new repeated error:
  fingerprint first_seen is inside current 5-minute window
  occurrence_count >= repeated_fingerprint_threshold

fatal burst:
  fatal_events in current 5-minute window >= fatal_burst_threshold
```

Open anomalies are deduplicated by project, service, environment, anomaly type, 5-minute window, and fingerprint hash.

## Incident Grouping and Lifecycle

When the anomaly service creates one or more new anomaly records, the worker sends those records to the incident grouping service. The grouping rules are deterministic:

```text
candidate incident:
  status == open
  same project_id
  same service
  same environment
  incident.updated_at is inside grouping window
  same fingerprint_hash if available OR same anomaly_type

if candidate exists:
  attach anomaly through incident_events
  update incident.updated_at
  severity = max(existing severity, anomaly severity)
else:
  create incident
  attach anomaly through incident_events
```

Incident titles are generated from anomaly type, such as `High error rate in payment-api`, `Latency spike in checkout-service`, `Repeated errors in payment-api`, or `Fatal event burst in payment-api`.

Resolved incidents are not reused. A later matching anomaly creates a new incident, which preserves lifecycle history. Operators can resolve incidents manually through `POST /incidents/{incident_id}/resolve`. The worker also auto-resolves stale open incidents after `INCIDENT_AUTO_RESOLVE_COOLDOWN_MINUTES` when no related anomaly has updated them.

The `incidents` table stores current lifecycle state. The `incident_events` table links incidents to anomalies and, when available, event fingerprints or event IDs. This keeps noisy anomaly records grouped into investigation units before Gemini or alerting runs.

## AI Incident Summaries

Gemini is post-detection summarization only. The sequence is:

```text
event -> rollup/fingerprint -> deterministic anomaly -> grouped incident -> AI summary
```

The worker calls the AI summary service only for high or critical incidents when:

- a new high or critical incident is created;
- an existing incident materially escalates to a higher severity;
- the incident has no cached summary yet.

The worker does not call Gemini for low-level events or to classify anomalies.

The summary input is a sanitized context object:

```text
incident:
  service, environment, severity, started_at, updated_at
anomaly_metrics:
  type, severity, score, baseline_value, observed_value, window
top_fingerprints:
  fingerprint hashes only
sample_messages:
  redacted event messages
timeline:
  anomaly detection timestamps
```

Sensitive keys such as `api_key`, `token`, `secret`, `password`, `authorization`, `cookie`, and `jwt` are replaced with `[REDACTED]`. Raw SignalForge ingestion keys, bearer tokens, and JWT-shaped values are redacted from text before any Gemini call.

Gemini is asked for strict JSON with this contract:

```json
{
  "summary": "Short incident summary in 2-3 sentences.",
  "affectedService": "payment-api",
  "impact": "Checkout requests are timing out for some users.",
  "likelyCause": "Payment provider timeout or insufficient retry handling.",
  "timeline": [{"time": "16:00", "event": "Error rate exceeded baseline"}],
  "recommendedActions": ["Check payment provider status"],
  "confidence": "medium"
}
```

If `GEMINI_API_KEY` is not configured, or Gemini returns invalid JSON, SignalForge stores a deterministic fallback summary. The API parses the cached summary and exposes it as `ai_summary_payload` for the incident detail UI.

## Discord Alerting and Deduplication

Discord alerting happens after incident grouping and, when available, after the AI summary is cached:

```text
deterministic anomaly -> incident grouping -> AI summary/fallback -> Discord alert
```

The alert service sends only incident lifecycle notifications:

```text
opened:
  incident severity is high or critical
  no previous opened alert exists for incident/channel

escalated:
  previous severity was high
  new severity is critical
  no previous escalated alert exists for incident/channel

resolved:
  incident status changes to resolved
  no previous resolved alert exists for incident/channel
```

The MVP uses a global `DISCORD_WEBHOOK_URL`. Per-project webhook storage is intentionally deferred to avoid introducing secret storage and masking flows in this phase. `DASHBOARD_BASE_URL` can be configured to include a dashboard link in the Discord embed.

Every attempted alert is recorded in the `alerts` table or local fallback file:

- `sent` when Discord accepts the webhook request;
- `skipped` when `DISCORD_WEBHOOK_URL` is missing;
- `failed` when the webhook call raises or returns an error.

Skipped and failed alerts do not crash event processing, incident grouping, manual resolution, or auto-resolution. This keeps alerting as a side effect of the incident lifecycle, not a dependency of ingestion or detection.

## Pipeline Observability

Pipeline observability is scoped to the authenticated user's projects. The API derives the user's project IDs, filters worker jobs and alert failures to those projects, and returns operational state without exposing raw queue payloads.

The health API reports:

```text
api status and timestamp
queue provider: local, redis, or qstash
local queue depth when available
worker_jobs counts by queued, processing, completed, failed, dead_letter
failed + dead_letter total
completed jobs in the last hour
average processing latency from started_at/completed_at
last processed job timestamp
accepted process_event jobs in the last hour
failed alert delivery count
```

The worker marks jobs with `started_at` when processing begins and `completed_at` when a job completes, fails, or moves to dead letter. The local fallback keeps the original safe payload reference on the worker job record so failed local jobs can be requeued through `POST /pipeline/jobs/{job_id}/retry`.

Retry is intentionally narrow: only failed and dead-letter jobs with an existing payload reference can be retried, and ownership is checked before the job is requeued. The retry endpoint updates the job back to `queued`, clears the error message, clears processing timestamps, and appends the payload to the configured local queue.
