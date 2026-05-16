# SignalForge | Distributed AI Observability Platform

SignalForge is a portfolio-scale observability platform for application events. The full system is designed to ingest logs and events, process them asynchronously, detect anomalies, group incidents, generate AI incident summaries, send alerts, and expose pipeline health.

Phase 11 adds provider-ready free-tier deployment configuration and documentation. It includes registration/login, project management, hashed ingestion API keys, event ingestion, worker processing, deterministic fingerprinting, idempotent event storage, 60-second service rollups, metrics APIs, project overview charts, anomaly detection, incident grouping, structured incident summaries, Discord alert logging, incident list/detail pages, manual resolution, an event explorer, pipeline health APIs, worker job visibility, a pipeline-health dashboard, reproducible demo scripts, stronger tests, request-size limits, UI loading/error/empty-state hardening, Render/Vercel configuration, and deployment/free-tier guides.

## Why This Is Not a Simple Log Viewer

The project is planned around a distributed event pipeline rather than a raw log table. The intended architecture separates request-time ingestion from background processing, analytics storage, incident grouping, AI summary generation, alert delivery, and internal pipeline observability.

Phase 11 keeps anomaly detection, incident grouping, AI summaries, and Discord alerts downstream of worker processing, then documents how to deploy the same system on free-tier services without requiring paid infrastructure.

## Architecture Placeholder

```text
Client app
  -> FastAPI ingestion API
  -> Redis/QStash-compatible queue
  -> Python worker
  -> PostgreSQL metadata + ClickHouse/Tinybird event analytics
  -> anomaly detection + incident grouping
  -> Gemini summaries + Discord alerts
  -> SvelteKit dashboard
```

## Tech Stack

| Layer | Technology | Current Status |
| --- | --- | --- |
| Frontend | SvelteKit, TypeScript, Tailwind CSS, Chart.js | Dashboard cards, project charts, anomaly table, incident pages with AI summaries and alert history, event explorer, pipeline-health view |
| Backend API | FastAPI, Pydantic settings | Health, auth, project, API key, ingestion, event search, metrics, anomalies, incidents, alerts, pipeline health |
| Worker | Python | Queue consumer, normalization, fingerprinting, event storage, metric rollups, anomaly detection, incident grouping, AI summary generation, Discord alerts, job timestamps |
| Metadata DB | PostgreSQL/Neon | Users, projects, api_keys, worker_jobs, events_metadata, event_fingerprints, metric_rollups, anomalies, incidents, incident_events, alerts |
| Queue | Redis/QStash-compatible | Queue abstraction with local JSONL fallback |
| Event Store | ClickHouse/Tinybird-compatible | Schema placeholder |
| AI | Gemini API with fallback | Post-detection incident summaries only |
| Alerts | Discord Webhooks | High/critical incident and recovery notifications with dedupe |
| CI | GitHub Actions | Frontend, API, worker jobs |

## Local Setup

### Frontend

```bash
cd apps/web
npm install
npm run check
npm run build
npm run dev
```

### API

```bash
cd services/api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
uvicorn app.main:app --reload --port 8000
```

Run the Phase 1 metadata migration against local Postgres:

```bash
docker compose up -d postgres redis
psql "postgresql://signalforge:signalforge@localhost:5432/signalforge" -f ../../infra/database/migrations/001_initial_schema.sql
```

If `DATABASE_URL` is not configured, the API uses an in-memory local fallback so the Phase 1 UI can still be explored without external services. Persistent local development should use PostgreSQL.

### Worker

```bash
cd services/worker
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
python -m app.worker --once
```

`--once` processes one queued job if available. Run it repeatedly after `scripts/send_demo_events.py` to drain the local queue.

### Local Infrastructure

```bash
docker compose up -d postgres redis
```

## Environment Variables

Example files are provided in:

- `infra/env/.env.example`
- `services/api/.env.example`
- `services/worker/.env.example`
- `apps/web/.env.example`

Do not commit real secrets or local `.env` files.

### Frontend

Required:

- `PUBLIC_API_BASE_URL`: public API origin used by the SvelteKit frontend.

### API

Required for deployed demos:

- `DATABASE_URL`: Neon/PostgreSQL connection string. Secret.
- `JWT_SECRET`: dashboard JWT signing secret. Secret.
- `API_KEY_PEPPER`: API-key hashing pepper. Secret.
- `ALLOWED_ORIGINS`: comma-separated frontend origins for CORS.
- `UPSTASH_REDIS_REST_URL`: shared queue provider URL.
- `UPSTASH_REDIS_REST_TOKEN`: shared queue provider token. Secret.

Optional integrations and limits:

- `QSTASH_TOKEN`
- `CLICKHOUSE_HOST`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`: secret.
- `CLICKHOUSE_DATABASE`
- `GEMINI_API_KEY`: secret.
- `GEMINI_MODEL`
- `DISCORD_WEBHOOK_URL`: secret.
- `DASHBOARD_BASE_URL`
- `INGEST_RATE_LIMIT_PER_MINUTE`
- `INGEST_RATE_LIMIT_PER_IP_MINUTE`
- `INGEST_MAX_BATCH_SIZE`
- `INGEST_MAX_MESSAGE_LENGTH`
- `INGEST_MAX_METADATA_BYTES`
- `MAX_REQUEST_BODY_BYTES`
- `LOCAL_QUEUE_PATH`
- `LOCAL_EVENT_STORE_PATH`
- `LOCAL_WORKER_JOBS_PATH`
- `LOCAL_METRIC_ROLLUPS_PATH`
- `LOCAL_ANOMALIES_PATH`
- `LOCAL_INCIDENTS_PATH`
- `LOCAL_ALERTS_PATH`
- `ANOMALY_MIN_SAMPLE_COUNT`
- `ANOMALY_REPEATED_FINGERPRINT_THRESHOLD`
- `ANOMALY_FATAL_BURST_THRESHOLD`
- `INCIDENT_GROUPING_WINDOW_MINUTES`
- `INCIDENT_AUTO_RESOLVE_COOLDOWN_MINUTES`

### Worker

Required for deployed demos:

- `DATABASE_URL`: same Neon/PostgreSQL connection string used by the API. Secret.
- `UPSTASH_REDIS_REST_URL`: shared queue provider URL.
- `UPSTASH_REDIS_REST_TOKEN`: shared queue provider token. Secret.

Optional integrations and limits:

- `QSTASH_TOKEN`
- `CLICKHOUSE_HOST`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`: secret.
- `CLICKHOUSE_DATABASE`
- `GEMINI_API_KEY`: secret.
- `GEMINI_MODEL`
- `DISCORD_WEBHOOK_URL`: secret.
- `DASHBOARD_BASE_URL`
- `WORKER_CONCURRENCY`
- `MAX_JOB_ATTEMPTS`
- `LOCAL_QUEUE_PATH`
- `LOCAL_EVENT_STORE_PATH`
- `LOCAL_WORKER_JOBS_PATH`
- `LOCAL_FINGERPRINTS_PATH`
- `LOCAL_METRIC_ROLLUPS_PATH`
- `LOCAL_ANOMALIES_PATH`
- `LOCAL_INCIDENTS_PATH`
- `LOCAL_ALERTS_PATH`
- `INGEST_MAX_METADATA_BYTES`
- `ANOMALY_MIN_SAMPLE_COUNT`
- `ANOMALY_REPEATED_FINGERPRINT_THRESHOLD`
- `ANOMALY_FATAL_BURST_THRESHOLD`
- `INCIDENT_GROUPING_WINDOW_MINUTES`
- `INCIDENT_AUTO_RESOLVE_COOLDOWN_MINUTES`

For local MVP usage, leave external provider variables blank and use the documented local fallbacks. For deployed API and worker processes, configure Neon and Upstash so both services share persistent state and queue data.

## Deployment

Live demo placeholder: not deployed in this repository.

- Deployment guide: [docs/deployment.md](docs/deployment.md)
- Free-tier strategy: [docs/free-tier-strategy.md](docs/free-tier-strategy.md)
- Render blueprint: [render.yaml](render.yaml)
- Vercel app config: [apps/web/vercel.json](apps/web/vercel.json)

## Roadmap Phases

1. Phase 0: Monorepo foundation. Implemented.
2. Phase 1: Auth, projects, and hashed API keys. Implemented.
3. Phase 2: Event ingestion, validation, rate limits, and queue abstraction. Implemented.
4. Phase 3: Worker processing, normalization, fingerprints, and event storage. Implemented.
5. Phase 4: Metrics dashboard and event explorer. Implemented.
6. Phase 5: Deterministic anomaly detection. Implemented.
7. Phase 6: Incident grouping and lifecycle. Implemented.
8. Phase 7: Gemini incident summaries. Implemented.
9. Phase 8: Discord alerts. Implemented.
10. Phase 9: Pipeline observability. Implemented.
11. Phase 10: Demo scripts, tests, and hardening. Implemented.
12. Phase 11: Free-tier deployment docs. Implemented.
13. Phase 12: Portfolio polish and screenshots.

## Free-Tier Strategy

SignalForge is designed for local and portfolio-scale demos. External providers are configured through environment variables, and local fallbacks keep development runnable when provider credentials are missing. See [docs/free-tier-strategy.md](docs/free-tier-strategy.md) for limits, fallbacks, and caveats.

## Security Notes

- Do not commit secrets, provider tokens, API keys, or `.env` files.
- Ingestion API keys are hashed before storage and raw keys are shown only once at creation.
- Project and API key routes enforce user ownership.
- Later phases must keep AI calls and analytics work out of the request path.
- AI summary prompts are built from sanitized incident context and redact API keys, tokens, secrets, cookies, and authorization strings before any Gemini call.
- Discord webhooks are configured through environment variables. Webhook URLs are not exposed in the frontend, and missing webhooks are logged as skipped alerts instead of failing processing.
- CORS origins are environment-driven in the API service.
- Oversized API requests are rejected with a consistent JSON `413` response before route handling.
- Collection endpoints apply bounded pagination limits for portfolio-scale local use.

## Testing

Current validation:

```bash
cd apps/web && npm run check && npm run build
cd services/api && python -m pytest
cd services/worker && python -m pytest
```

Phase 1 API tests cover registration, duplicate email rejection, login, invalid login, project creation, cross-user project isolation, one-time raw API key creation, masked key listing, and revocation.

Phase 2 API tests cover valid ingestion, missing/invalid/revoked API keys, invalid event fields, oversized payload fields, rate limiting, and batch ingestion.

Phase 3 worker tests cover message normalization, stable fingerprints, successful processing, failed/dead-letter jobs, and duplicate `eventId` idempotency. API tests cover processed event search and ownership.

Phase 4 tests cover rollup bucket calculation, error rate calculation, latency avg/p95 calculation, and metrics endpoint ownership.

Phase 5 tests cover z-score calculation, error-rate spikes, latency spikes, repeated new fingerprints, fatal bursts, anomaly deduplication, and anomaly endpoint ownership.

Phase 6 tests cover incident grouping, service separation, severity escalation, auto-resolution, resolved incident dedupe behavior, incident endpoint ownership, detail payloads, and manual resolution.

Phase 7 tests cover AI input sanitization, missing-key fallback summaries, valid Gemini JSON parsing and storage, invalid Gemini output fallback, summary regeneration suppression, and incident detail summary payloads.

Phase 8 tests cover missing webhook skip logging, sent alert recording, open alert deduplication, severity escalation alerts, recovery alerts, failed webhook recording, alert history APIs, and manual-resolution recovery alert logging.

Phase 9 tests cover pipeline-health counts, queue depth, failed/dead-letter totals, average processing latency, alert failure counts, worker job filtering, retry requeue behavior, endpoint authentication, and local worker job timestamp persistence.

Phase 10 tests cover request-size hardening, bounded pagination validation, demo script dry runs, local queue FIFO behavior, and retry requeue appends.

## Local Demo Flow

1. Start optional local infrastructure:

```bash
docker compose up -d postgres redis
```

2. Run the PostgreSQL migration if using `DATABASE_URL`:

```bash
psql "postgresql://signalforge:signalforge@localhost:5432/signalforge" -f infra/database/migrations/001_initial_schema.sql
```

3. Start the API:

```bash
cd services/api
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

4. Start the frontend:

```bash
cd apps/web
npm install
npm run dev
```

5. Register or log in at `http://localhost:5173/login`, create a project, open project settings, and create a demo API key.

6. Send normal traffic:

```bash
python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40
```

7. Drain queued jobs from another terminal:

```bash
cd services/worker
python -m pip install -r requirements.txt
python -m app.worker --once
```

Run the worker command once per queued event, or keep repeating it while demo traffic is being generated.

8. Generate a spike and recovery scenario:

```bash
python scripts/generate_error_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_latency_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_recovery_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key
```

9. View `/projects/{projectId}` for rollups, `/projects/{projectId}/anomalies` for deterministic detections, `/projects/{projectId}/incidents` for grouped incidents, incident detail for AI fallback or Gemini summaries and alert history, and `/pipeline-health` for worker/job health.

10. Reset local fallback files when needed:

```bash
python scripts/reset_demo_project.py --api-url http://localhost:8000 --project-key sf_demo_your_key --yes
```

## Demo Ingestion

After starting the API and creating a project API key, send demo events:

```bash
python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40
```

Additional Phase 10 scripts generate deterministic demo scenarios:

```bash
python scripts/generate_error_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_latency_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_recovery_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key
```

All demo scripts support `--dry-run` for payload validation without contacting the API.

The API validates the request, applies rate limits, records a queued `worker_jobs` row, writes the job to the configured queue fallback, and returns `202 Accepted` with a job ID. Analytics, AI summaries, and alerting are intentionally outside this request path.

Process queued local events:

```bash
cd services/worker
python -m app.worker --once
```

Processed events are written to the configured local event store fallback or PostgreSQL when `DATABASE_URL` is set, then shown in `/projects/{projectId}/events`.

Metric rollups are updated by the worker in 60-second buckets and shown in `/projects/{projectId}`.

## Deterministic Anomaly Detection

SignalForge does not use Gemini or any LLM to decide whether an anomaly exists. Detection is deterministic Python logic:

- Error-rate spike: current 5-minute error rate is compared to the prior 30-60 minute baseline. High severity requires `current_error_rate > 0.20` and `z_score >= 3.0`; critical severity is created when `current_error_rate > 0.50`.
- Latency spike: current p95 latency must exceed `baseline_p95 * 3` and be greater than `1000ms`.
- New repeated error: a new error fingerprint crossing the configured repeat threshold creates an anomaly.
- Fatal burst: fatal events crossing the configured 5-minute threshold create a critical anomaly.

Open anomalies are deduplicated by project, service, environment, type, window, and fingerprint.

## Incident Lifecycle

When the worker creates an anomaly, it passes the anomaly to the incident grouping service. The service attaches it to an existing open incident when the project, service, environment, and recent related fingerprint or anomaly type match. Otherwise, it creates a new incident with status `open`.

Incident severity escalates to the highest related anomaly severity. Incidents can be resolved manually from the detail page, and stale open incidents are auto-resolved after the configured cooldown window when no related anomaly updates them.

The UI includes `/projects/{projectId}/incidents` and `/projects/{projectId}/incidents/{incidentId}`. The detail page shows lifecycle status, timeline, related anomalies, fingerprints, event samples, and structured AI summary fields when available.

## AI Incident Summaries

Gemini is used after deterministic anomaly detection and incident grouping. The worker summarizes a high or critical incident when it is created or when its severity escalates. It does not regenerate for every event.

The summary contract is structured JSON:

```json
{
  "summary": "Short incident summary.",
  "affectedService": "payment-api",
  "impact": "Checkout requests are failing for some users.",
  "likelyCause": "Payment provider timeout or service regression.",
  "timeline": [{"time": "16:00", "event": "Error rate exceeded baseline"}],
  "recommendedActions": ["Check payment provider status"],
  "confidence": "medium"
}
```

If `GEMINI_API_KEY` is missing or Gemini returns invalid JSON, the worker stores a deterministic local fallback summary so the demo remains usable without external AI access. Summary results are cached on the incident record in `ai_summary`, `likely_cause`, and `recommended_actions`.

## Discord Alerts

SignalForge uses a global `DISCORD_WEBHOOK_URL` for free demo alerting. The worker records a Discord alert when a high or critical incident opens, when an incident escalates from high to critical, and when an incident resolves.

Alerts are deduplicated by incident, channel, and alert type:

- one `opened` alert per high/critical incident;
- one `escalated` alert when severity increases to critical;
- one `resolved` alert when the incident recovers or is manually resolved.

If `DISCORD_WEBHOOK_URL` is missing, the alert is recorded with status `skipped`. If Discord returns an error, the alert is recorded with status `failed`. Both paths keep the worker and API pipeline running. Alert history is visible on the incident detail page and project settings page.

## Pipeline Observability

SignalForge exposes authenticated pipeline-health APIs for the jobs owned by the current user's projects:

- `GET /pipeline-health` and `GET /worker-health` return API status, queue provider, local queue depth when available, worker job counts by status, failed/dead-letter count, completed jobs in the last hour, average processing latency, last processed timestamp, recent ingestion count, and alert delivery failures.
- `GET /pipeline/jobs` returns recent worker jobs with optional status, type, and time filters. The response intentionally omits raw queue payloads while showing safe error and timing fields.
- `POST /pipeline/jobs/{job_id}/retry` requeues failed or dead-letter local jobs when a safe payload reference is available.

The `/pipeline-health` frontend page shows queue mode, job counters, worker latency, failed alert delivery count, recent errors, worker job history, and retry actions for failed jobs.

## Screenshots

After later polish, capture screenshots for:

- Dashboard project cards.
- Project overview charts.
- Anomaly table/timeline.
- Incident list and incident detail.
- Discord alert history.
- Pipeline-health dashboard.
- Event explorer with selected event details.
- Project settings with ingestion instructions.

## Deployment Notes

Phase 11 documents a free-tier deployment path using Vercel or Cloudflare Pages for the frontend, Render for the API and worker, Neon for PostgreSQL, Upstash Redis REST for queueing, optional ClickHouse/Tinybird analytics, optional Gemini summaries, and optional Discord alerts. See [docs/deployment.md](docs/deployment.md).

Free services may sleep and are suitable only for portfolio-scale demos. No production SLA is claimed.

## Screenshots Placeholder

Screenshots will be added after the dashboard and event pipeline features exist. See `docs/screenshots/README.md`.
