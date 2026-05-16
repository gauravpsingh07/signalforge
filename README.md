# SignalForge | Distributed AI Observability Platform

SignalForge is a portfolio-scale observability platform for application events. It ingests application events through an API-key protected endpoint, processes them asynchronously with a worker, builds service-level rollups, detects deterministic anomalies, groups related anomalies into incidents, generates Gemini or fallback incident summaries, records Discord alert attempts, and exposes dashboard views for events, incidents, and pipeline health.

The project is designed to be runnable locally without paid services. External providers such as Neon, Upstash, Gemini, Discord, Vercel, Render, ClickHouse, and Tinybird are configured through environment variables and documented as optional or deployment-time integrations.

## Problem

Raw logs are noisy. A developer can receive thousands of application events without a clear answer to the questions that matter during an incident:

- Which service is unhealthy?
- Is this a normal error rate or a spike?
- Are repeated failures related by fingerprint?
- Has the incident already been summarized and alerted?
- Is the event pipeline itself processing jobs successfully?

SignalForge turns event streams into a small set of service metrics, anomalies, incidents, summaries, alerts, and worker-health signals.

## Why This Is Not A CRUD Or Log Viewer Project

SignalForge is built around an asynchronous event pipeline, not a raw log table:

- The ingestion API validates, rate-limits, enqueues, and returns quickly.
- A separate worker performs normalization, fingerprinting, storage, rollups, anomaly detection, incident grouping, AI summary generation, and alert logging.
- Deterministic anomaly detection runs before Gemini. Gemini is used only to summarize grouped incidents.
- Incidents track lifecycle state and related anomalies instead of showing isolated log rows.
- Pipeline health is observable through job counts, queue depth, processing latency, failed jobs, and retry actions.

## Architecture

```text
Client app or demo script
  -> FastAPI ingestion API
      -> validates payload, API key, rate limits, request size
      -> writes worker job metadata
      -> enqueues event job
  -> Queue abstraction
      -> Upstash Redis REST when configured
      -> local JSONL fallback for local demos
  -> Python worker
      -> consumes job
      -> normalizes event
      -> fingerprints repeated errors
      -> stores processed event
      -> updates metric rollups
      -> detects anomalies
      -> groups incidents
      -> creates AI/fallback summaries
      -> records Discord alert attempts
  -> PostgreSQL/Neon-compatible metadata
  -> local/PostgreSQL event fallback
  -> ClickHouse/Tinybird target schema documented for analytics
  -> SvelteKit dashboard
      -> projects, metrics, events, anomalies, incidents, alerts, pipeline health
```

## Tech Stack

| Layer | Technology | Why It Is Used |
| --- | --- | --- |
| Frontend | SvelteKit, TypeScript, Tailwind CSS, Chart.js | Fast dashboard UI, typed API client, responsive styling, local chart rendering. |
| API | FastAPI, Pydantic settings, PyJWT | Typed request validation, consistent JSON errors, JWT dashboard auth, API-key ingestion. |
| Worker | Python | Clear background processing boundary for queue consumption and deterministic analysis. |
| Metadata Store | PostgreSQL/Neon-compatible schema | Durable users, projects, API keys, jobs, rollups, anomalies, incidents, and alerts. |
| Queue | Upstash Redis REST with local JSONL fallback | Shared deployed queue when configured, provider-free local development otherwise. |
| Event Store | Local JSONL/PostgreSQL-compatible fallback; ClickHouse/Tinybird schema documented | Keeps the demo runnable now while documenting the intended columnar analytics path. |
| AI | Gemini API with deterministic fallback | Summarizes incidents after deterministic detection and grouping; missing keys do not break demos. |
| Alerts | Discord Webhooks | Records high/critical incident and recovery notifications with deduplication and skipped/failed states. |
| CI | GitHub Actions | Runs frontend, API, and worker validation jobs. |

## Features

### Backend

- User registration, login, and JWT-protected dashboard routes.
- Project creation and ownership checks.
- Hashed ingestion API keys with raw keys shown only once.
- `POST /v1/events` and `POST /v1/events/batch` ingestion.
- Pydantic payload validation, request-size guard, metadata/message caps, rate limits, and consistent JSON errors.
- Project-scoped event, metric, anomaly, incident, alert, and pipeline APIs.
- Bounded pagination for collection routes.

### Worker

- Queue consumer with local JSONL fallback and Upstash Redis REST support.
- Event normalization for service, environment, level, timestamps, and metadata.
- Deterministic message normalization and fingerprint hashing.
- Idempotent processed-event storage by project and event ID.
- Metric rollups for volume, warning/error/fatal counts, error rate, average latency, and p95 latency.
- Failed-job retries and dead-letter status tracking.
- Worker job timestamps for processing latency.

### AI/ML

- Deterministic anomaly detection for error-rate spikes, latency spikes, repeated new fingerprints, and fatal bursts.
- Incident grouping by project, service, environment, fingerprint, anomaly type, and time window.
- Gemini incident summaries only after deterministic anomaly detection and incident grouping.
- Deterministic fallback summaries when Gemini is not configured or returns invalid output.
- Sanitization before summary generation to redact API keys, bearer tokens, JWT-shaped values, cookies, passwords, and secrets.

### Dashboard

- Login/register flow.
- Project list and project overview pages.
- Event explorer with service, environment, level, and message filters.
- Metric charts with empty-state fallback.
- Anomaly table.
- Incident list and incident detail pages with timeline, related anomalies, fingerprints, AI/fallback summary, and alert history.
- Pipeline health page with queue provider, queue depth, job counts, latency, failures, recent jobs, and retry actions.
- Loading, error, retry, and empty states for dashboard workflows.

### Alerts

- Discord alert attempts for high/critical incident open, high-to-critical escalation, and incident resolution.
- Alert deduplication by incident, channel, and lifecycle event.
- `sent`, `skipped`, and `failed` alert statuses.
- Missing `DISCORD_WEBHOOK_URL` records skipped alerts instead of breaking the worker.

### Security

- Raw ingestion keys are never stored and are returned only once.
- API key hashes use an environment-driven pepper.
- Dashboard routes enforce user/project ownership.
- Ingestion keys are compared using constant-time hash comparison.
- CORS origins are environment-driven.
- Provider secrets live in runtime env vars, not committed files.

### Testing

- API tests cover auth, projects, API keys, ingestion validation, rate limits, metrics, anomalies, incidents, alerts, pipeline health, request-size hardening, pagination validation, and demo script dry-runs.
- Worker tests cover queue behavior, event processing, fingerprinting, rollups, anomaly detection, incident grouping, AI fallback, Discord skipped/failure paths, dead-letter behavior, job timestamps, and requeue behavior.
- Frontend validation uses SvelteKit sync, `svelte-check`, and production build.

## End-To-End Flow

1. Create a project in the dashboard.
2. Generate a demo or live ingestion API key.
3. Send events through `POST /v1/events`.
4. The API validates the event and API key, enforces rate limits, creates a queued worker job, and returns `202 Accepted`.
5. The worker consumes queued jobs outside the request path.
6. The worker normalizes the event, calculates a fingerprint, stores the processed event, and updates rollups.
7. Deterministic anomaly detection evaluates the current service window against thresholds and baselines.
8. New anomalies are grouped into incidents.
9. High or critical incidents receive a Gemini summary or deterministic fallback summary.
10. Discord alert attempts are recorded for significant incident lifecycle events.
11. The dashboard shows metrics, events, anomalies, incidents, summaries, alert history, and pipeline health.

## Anomaly Detection

Gemini is not used to decide whether an anomaly exists. Detection is deterministic Python logic.

Error-rate spike:

```text
current_error_rate = (error_events + fatal_events) / total_events
z_score = (current_error_rate - baseline_mean) / baseline_stddev

high severity:
  total_events >= min_sample_count
  current_error_rate > 0.20
  z_score >= 3.0

critical severity:
  total_events >= min_sample_count
  current_error_rate > 0.50
```

Latency spike:

```text
current_p95 > baseline_p95 * 3
current_p95 > 1000ms
total_events >= min_sample_count
```

Repeated new error:

```text
fingerprint first_seen is inside the current window
occurrence_count >= repeated_fingerprint_threshold
```

Fatal burst:

```text
fatal_events in current 5-minute window >= fatal_burst_threshold
```

Open anomalies are deduplicated by project, service, environment, anomaly type, window, and fingerprint.

## API Summary

Sample ingestion request:

```bash
curl -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer sf_demo_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "evt_123",
    "timestamp": "2026-05-15T15:45:00Z",
    "service": "payment-api",
    "environment": "production",
    "level": "error",
    "message": "Stripe checkout timeout while creating session",
    "statusCode": 504,
    "latencyMs": 2380,
    "traceId": "trace_abc123",
    "requestId": "req_789",
    "metadata": {
      "route": "/checkout",
      "region": "local"
    }
  }'
```

Implemented API areas:

- `/health` and `/`
- `/auth/register`, `/auth/login`, `/auth/me`
- `/projects`
- `/projects/{project_id}/api-keys`
- `/api-keys/{key_id}`
- `/v1/events` and `/v1/events/batch`
- `/projects/{project_id}/events`
- `/projects/{project_id}/metrics`
- `/projects/{project_id}/services`
- `/projects/{project_id}/anomalies`
- `/projects/{project_id}/incidents`
- `/incidents/{incident_id}`
- `/incidents/{incident_id}/resolve`
- `/projects/{project_id}/alerts`
- `/pipeline-health`, `/worker-health`, `/pipeline/jobs`, `/pipeline/jobs/{job_id}/retry`

See [docs/api-reference.md](docs/api-reference.md) for details.

## Local Setup

Install frontend dependencies:

```bash
cd apps/web
npm install
npm run check
npm run build
npm run dev
```

Install and run the API:

```bash
cd services/api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
uvicorn app.main:app --reload --port 8000
```

Install and run the worker:

```bash
cd services/worker
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest
python -m app.worker --once
```

Optional local Postgres and Redis:

```bash
docker compose up -d postgres redis
psql "postgresql://signalforge:signalforge@localhost:5432/signalforge" -f infra/database/migrations/001_initial_schema.sql
```

If `DATABASE_URL` is not set, the API and worker use local in-memory/file fallbacks suitable for single-machine demos.

## Demo Flow

1. Start the API, frontend, and worker environment.
2. Register or log in at `http://localhost:5173/login`.
3. Create a project.
4. Open project settings and create a demo API key.
5. Send normal traffic:

```bash
python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40
```

6. Drain queued jobs by running the worker once per queued event:

```bash
cd services/worker
python -m app.worker --once
```

7. Generate spike and recovery scenarios:

```bash
python scripts/generate_error_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_latency_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_recovery_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key
```

8. Review project metrics, event explorer, anomaly table, incident detail, AI/fallback summary, alert history, and pipeline health.
9. Reset local fallback files when needed:

```bash
python scripts/reset_demo_project.py --api-url http://localhost:8000 --project-key sf_demo_your_key --yes
```

All demo scripts support `--dry-run`.

## Deployment

Live demo placeholder: not deployed in this repository.

- Deployment guide: [docs/deployment.md](docs/deployment.md)
- Free-tier strategy: [docs/free-tier-strategy.md](docs/free-tier-strategy.md)
- Render blueprint: [render.yaml](render.yaml)
- Vercel app config: [apps/web/vercel.json](apps/web/vercel.json)

## Free-Tier Limitations

- The project is intended for local and portfolio-scale demos, not production traffic.
- Free services may sleep, so first requests can be slow.
- Provider quotas can change; rate limits and payload caps are configurable through environment variables.
- Local JSONL fallbacks are not shared storage and should not be used for multi-instance deployments.
- ClickHouse/Tinybird event analytics are documented as a target schema; the current runnable implementation uses local/PostgreSQL-compatible event paths.
- Missing Gemini or Discord credentials do not break the demo; fallback summaries and skipped alert logs are used instead.
- No production SLA or enterprise scale is claimed.

## Security Considerations

- Do not commit `.env` files, provider tokens, Discord webhooks, Gemini keys, raw SignalForge API keys, local database dumps, or logs.
- Runtime secrets are documented in `.env.example` files only by variable name.
- Rotate any key or webhook that appears in a terminal recording, screenshot, or shared logs.
- Keep ingestion API keys server-side; do not ship them in public frontend code.
- AI summary inputs are sanitized before Gemini calls.
- Dashboard users can access only their own projects and project-scoped resources.

## Testing Commands

```bash
cd services/api
python -m pytest

cd ../worker
python -m pytest

cd ../../apps/web
npm run check
npm run build
```

The GitHub Actions workflow runs equivalent API, worker, and frontend validation. The frontend CI install step uses `npm install` to avoid the known platform optional-dependency lockfile issue on Linux runners.

## Screenshots And GIFs

Screenshots are not committed yet. Place real screenshots in `docs/screenshots/` after running the local demo. Do not add fake screenshots.

Planned captures:

- Login and dashboard.
- Project overview charts.
- Event explorer.
- Anomaly table.
- Incident detail with Gemini or fallback summary.
- Pipeline health dashboard.
- Discord alert history or a clearly labeled skipped-alert state when no webhook is configured.

See [docs/screenshots/README.md](docs/screenshots/README.md).

## Future Improvements

- Implement a provider-backed ClickHouse or Tinybird event store path behind the existing event-store abstraction.
- Add retention cleanup jobs for long-running demos.
- Add service-silence anomaly detection.
- Add per-project Discord webhook storage with masking and rotation flows.
- Add browser-level end-to-end tests for the dashboard demo path.
- Add real screenshots or GIFs after running the final local demo.
