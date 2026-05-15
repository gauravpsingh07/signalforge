# SignalForge | Distributed AI Observability Platform

SignalForge is a portfolio-scale observability platform for application events. The full system is designed to ingest logs and events, process them asynchronously, detect anomalies, group incidents, generate AI incident summaries, send alerts, and expose pipeline health.

Phase 1 implements the secure metadata foundation. It includes registration/login, JWT-authenticated project management, hashed ingestion API keys that reveal the raw key only once, an importable Python worker skeleton, local infrastructure configuration, documentation, and CI.

## Why This Is Not a Simple Log Viewer

The project is planned around a distributed event pipeline rather than a raw log table. The intended architecture separates request-time ingestion from background processing, analytics storage, incident grouping, AI summary generation, alert delivery, and internal pipeline observability.

Phase 1 does not implement event ingestion, queue processing, anomaly detection, AI summaries, alerts, or pipeline observability yet. The repository structure and docs are prepared so each phase can add them without turning the project into a dashboard-only app.

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

| Layer | Technology | Phase 0 Status |
| --- | --- | --- |
| Frontend | SvelteKit, TypeScript, Tailwind CSS | Auth, project, and API key screens |
| Backend API | FastAPI, Pydantic settings | Health, auth, project, and API key routes |
| Worker | Python | Importable local polling placeholder |
| Metadata DB | PostgreSQL/Neon | Users, projects, and api_keys migration |
| Queue | Redis/QStash-compatible | Planned abstraction |
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
3. Phase 2: Event ingestion, validation, rate limits, and queue abstraction. Planned.
4. Phase 3: Worker processing, normalization, fingerprints, and event storage.
5. Phase 4: Metrics dashboard and event explorer.
6. Phase 5: Deterministic anomaly detection.
7. Phase 6: Incident grouping and lifecycle.
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

## Deployment Plan Placeholder

Planned deployment targets are Vercel or Cloudflare Pages for the frontend, Render for the API and worker, Neon for PostgreSQL, Upstash for Redis/QStash-compatible queueing, ClickHouse Cloud or Tinybird for event analytics, Gemini for summaries, and Discord Webhooks for alerts.

Free services may sleep and are suitable only for portfolio-scale demos.

## Screenshots Placeholder

Screenshots will be added after the dashboard and event pipeline features exist. See `docs/screenshots/README.md`.
