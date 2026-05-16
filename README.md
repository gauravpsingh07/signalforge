# SignalForge | Distributed AI Observability Platform

SignalForge is a portfolio-scale observability platform for application events. The full system is designed to ingest logs and events, process them asynchronously, detect anomalies, group incidents, generate AI incident summaries, send alerts, and expose pipeline health.

Phase 6 implements incident lifecycle and grouping. It includes registration/login, project management, hashed ingestion API keys, event ingestion, worker processing, deterministic fingerprinting, idempotent event storage, 60-second service rollups, metrics APIs, project overview charts, anomaly detection, anomaly views, incident grouping, incident list/detail pages, manual resolution, and an event explorer.

## Why This Is Not a Simple Log Viewer

The project is planned around a distributed event pipeline rather than a raw log table. The intended architecture separates request-time ingestion from background processing, analytics storage, incident grouping, AI summary generation, alert delivery, and internal pipeline observability.

Phase 6 detects anomalies from rollups and fingerprints using Python logic, then groups related anomalies into incidents. It does not build Gemini AI summaries, Discord alerts, or pipeline observability yet.

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
| Frontend | SvelteKit, TypeScript, Tailwind CSS, Chart.js | Dashboard cards, project charts, anomaly table, incident pages, event explorer |
| Backend API | FastAPI, Pydantic settings | Health, auth, project, API key, ingestion, event search, metrics, anomalies, incidents |
| Worker | Python | Queue consumer, normalization, fingerprinting, event storage, metric rollups, anomaly detection, incident grouping |
| Metadata DB | PostgreSQL/Neon | Users, projects, api_keys, worker_jobs, events_metadata, event_fingerprints, metric_rollups, anomalies, incidents, incident_events |
| Queue | Redis/QStash-compatible | Queue abstraction with local JSONL fallback |
| Event Store | ClickHouse/Tinybird-compatible | Schema placeholder |
| AI | Gemini API | Planned integration |
| Alerts | Discord Webhooks | Planned integration |
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

## Roadmap Phases

1. Phase 0: Monorepo foundation. Implemented.
2. Phase 1: Auth, projects, and hashed API keys. Implemented.
3. Phase 2: Event ingestion, validation, rate limits, and queue abstraction. Implemented.
4. Phase 3: Worker processing, normalization, fingerprints, and event storage. Implemented.
5. Phase 4: Metrics dashboard and event explorer. Implemented.
6. Phase 5: Deterministic anomaly detection. Implemented.
7. Phase 6: Incident grouping and lifecycle. Implemented.
8. Phase 7: Gemini incident summaries.
9. Phase 8: Discord alerts.
10. Phase 9: Pipeline observability.
11. Phase 10: Demo scripts, tests, and hardening.
12. Phase 11: Free-tier deployment docs.
13. Phase 12: Portfolio polish and screenshots.

## Free-Tier Strategy

SignalForge is designed for local and portfolio-scale demos. External providers are configured through environment variables, and later phases should include local fallbacks for services such as queueing and event storage whenever provider credentials are missing.

## Security Notes

- Do not commit secrets, provider tokens, API keys, or `.env` files.
- Ingestion API keys are hashed before storage and raw keys are shown only once at creation.
- Project and API key routes enforce user ownership.
- Later phases must keep AI calls and analytics work out of the request path.
- CORS origins are environment-driven in the API service.

## Testing

Current Phase 1 validation:

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

## Demo Ingestion

After starting the API and creating a project API key, send demo events:

```bash
python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40
```

The API validates the request, applies rate limits, records a queued `worker_jobs` row, writes the job to the configured queue fallback, and returns `202 Accepted` with a job ID. Analytics, AI, and alerting are intentionally outside this request path.

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

The Phase 6 UI includes `/projects/{projectId}/incidents` and `/projects/{projectId}/incidents/{incidentId}`. The detail page shows lifecycle status, timeline, related anomalies, fingerprints, event samples, and an explicit Phase 7 placeholder for Gemini summaries.

## Screenshots

After later polish, capture screenshots for:

- Dashboard project cards.
- Project overview charts.
- Anomaly table/timeline.
- Incident list and incident detail.
- Event explorer with selected event details.
- Project settings with ingestion instructions.

## Deployment Plan Placeholder

Planned deployment targets are Vercel or Cloudflare Pages for the frontend, Render for the API and worker, Neon for PostgreSQL, Upstash for Redis/QStash-compatible queueing, ClickHouse Cloud or Tinybird for event analytics, Gemini for summaries, and Discord Webhooks for alerts.

Free services may sleep and are suitable only for portfolio-scale demos.

## Screenshots Placeholder

Screenshots will be added after the dashboard and event pipeline features exist. See `docs/screenshots/README.md`.
