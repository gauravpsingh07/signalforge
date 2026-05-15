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

## Phase 0 Scope

Phase 0 creates the foundation needed for that flow:

- Monorepo structure.
- SvelteKit frontend shell.
- FastAPI health endpoint and placeholder route modules.
- Python worker skeleton.
- PostgreSQL and ClickHouse/Tinybird schema placeholders.
- Docker Compose for local Postgres and Redis.
- GitHub Actions skeleton.

No production event processing or auth is implemented in Phase 0.
