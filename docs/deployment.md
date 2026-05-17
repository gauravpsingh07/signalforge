# Deployment

This guide documents the current free-tier portfolio deployment. It does not include real secrets, screenshots, or resume copy.

Current deployed endpoints:

- Frontend: https://signalforge-orcin.vercel.app
- API: https://signalforge-api-28ht.onrender.com
- API health: https://signalforge-api-28ht.onrender.com/health

The free-tier hosted setup uses Vercel for the frontend, Render Free Web Service for the API, Neon PostgreSQL, and Upstash Redis. Render did not offer a free Background Worker option during setup, so full async processing requires running the worker locally during demos/testing with the same Neon and Upstash environment variables.

## Targets

| Service | Suggested free-tier target | Notes |
| --- | --- | --- |
| Frontend | Vercel or Cloudflare Pages | SvelteKit app in `apps/web`. |
| API | Render free web service | FastAPI app in `services/api`. |
| Worker | Local worker during free demo/testing | Render Background Worker was not used because no free option was available. |
| PostgreSQL | Neon free tier | Run `infra/database/migrations/001_initial_schema.sql`. |
| Queue | Upstash Redis REST, with local JSONL fallback | API pushes jobs and worker pops jobs when Upstash env vars are configured. |
| Event analytics | Current local/PostgreSQL fallback; ClickHouse/Tinybird schema documented | `infra/clickhouse/events_schema.sql` is the target analytics schema. |
| AI | Gemini API, with deterministic fallback | Missing `GEMINI_API_KEY` does not break the worker. |
| Alerts | Discord Webhook | Missing webhook records skipped alerts. |

Free services may sleep. Treat this as portfolio-scale infrastructure, not a production SLA. The hosted API can enqueue jobs while the local worker is offline, but metrics, anomalies, incidents, summaries, and alerts update only when the worker is running.

## 1. Prepare The Repository

1. Confirm local validation passes:

```bash
cd apps/web && npm run check && npm run build
cd ../../services/api && python -m pytest
cd ../worker && python -m pytest
```

2. Keep all secrets out of Git. Use provider dashboards for secret values.

3. Copy env names from:

- `apps/web/.env.example`
- `services/api/.env.example`
- `services/worker/.env.example`
- `infra/env/.env.example`

## 2. Create Neon Postgres

1. Create a Neon project and database.
2. Copy the pooled connection string.
3. Run the migration from a trusted local shell:

```bash
psql "postgresql://USER:PASSWORD@HOST/signalforge?sslmode=require" -f infra/database/migrations/001_initial_schema.sql
```

4. Set the same `DATABASE_URL` in the API and local worker environment.

Local equivalent:

```bash
docker compose up -d postgres
psql "postgresql://signalforge:signalforge@localhost:5432/signalforge" -f infra/database/migrations/001_initial_schema.sql
```

If `DATABASE_URL` is blank, SignalForge still runs locally with in-memory or file fallbacks, but the deployed API and local demo worker should share Neon so state persists across API restarts and worker sessions. The Neon default database name may be `neondb`; SignalForge does not require the database itself to be named `signalforge`.

## 3. Create Upstash Redis

1. Create an Upstash Redis database.
2. Copy the REST URL and REST token.
3. Set these on both the Render API and the local worker:

```text
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
```

The local JSONL queue fallback is useful for single-machine local demos only. The deployed API and local demo worker need a shared queue provider such as Upstash Redis REST.

`QSTASH_TOKEN` is reserved for future QStash-style delivery. The current queue implementation uses Upstash Redis REST when the Redis URL and token are present, so `QSTASH_TOKEN` can remain unset.

## 4. Configure Gemini And Discord

Optional integrations:

```text
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
DISCORD_WEBHOOK_URL=...
DASHBOARD_BASE_URL=<frontend-origin>
```

If Gemini is not configured, high and critical incidents receive deterministic fallback summaries. If Discord is not configured, alert attempts are logged with `skipped` status.

## 5. Deploy API To Render

This repo includes `render.yaml` with a web service named `signalforge-api`.

Manual Render settings:

```text
Root Directory: services/api
Build Command: python -m pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required API env vars for a deployed demo:

```text
DATABASE_URL
JWT_SECRET
API_KEY_PEPPER
ALLOWED_ORIGINS
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
```

Optional API env vars:

```text
GEMINI_API_KEY
GEMINI_MODEL
DISCORD_WEBHOOK_URL
DASHBOARD_BASE_URL
CLICKHOUSE_HOST
CLICKHOUSE_USER
CLICKHOUSE_PASSWORD
CLICKHOUSE_DATABASE
QSTASH_TOKEN
```

Set `ALLOWED_ORIGINS` to the final frontend origin once it exists. Do not use fake deployed URLs in committed docs.

## 6. Run The Worker Locally For The Free Demo

Render Background Worker was not used for the current free-tier demo because no free worker option was available. Do not collapse worker processing into the API just to avoid this hosting limitation; the separate API + queue + worker architecture is part of SignalForge's design.

Run the worker locally during demos/testing from `services/worker`:

```powershell
$env:DATABASE_URL="YOUR_NEON_DATABASE_URL"
$env:UPSTASH_REDIS_REST_URL="YOUR_UPSTASH_REDIS_REST_URL"
$env:UPSTASH_REDIS_REST_TOKEN="YOUR_UPSTASH_REDIS_REST_TOKEN"
$env:WORKER_CONCURRENCY="2"
$env:MAX_JOB_ATTEMPTS="3"
# Optional:
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
$env:DISCORD_WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL"
python -m app.worker
```

Required local worker env vars for the deployed demo:

```text
DATABASE_URL
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
```

Optional worker env vars:

```text
GEMINI_API_KEY
GEMINI_MODEL
DISCORD_WEBHOOK_URL
DASHBOARD_BASE_URL
WORKER_CONCURRENCY
MAX_JOB_ATTEMPTS
CLICKHOUSE_HOST
CLICKHOUSE_USER
CLICKHOUSE_PASSWORD
CLICKHOUSE_DATABASE
QSTASH_TOKEN
```

Keep this terminal open while sending demo traffic and using the dashboard. Queued jobs remain in Upstash until the worker processes them.

## 7. Deploy Frontend

### Vercel

Create a Vercel project with:

```text
Root Directory: apps/web
Install Command: npm install
Build Command: npm run build
```

`apps/web/vercel.json` records the same commands. Set:

```text
PUBLIC_API_BASE_URL=https://signalforge-api-28ht.onrender.com
```

Do not include `/health` in `PUBLIC_API_BASE_URL`.

### Cloudflare Pages

Use the same app root:

```text
Root Directory: apps/web
Build Command: npm run build
Environment Variable: PUBLIC_API_BASE_URL=https://signalforge-api-28ht.onrender.com
```

The current app uses SvelteKit `adapter-auto`. Verify the Pages build output in the provider dashboard before sharing a demo.

## 8. ClickHouse Or Tinybird Notes

The repository includes `infra/clickhouse/events_schema.sql` as the intended event analytics schema. The current implementation remains honest and demo-friendly by using local JSONL and PostgreSQL-compatible event metadata paths.

To enable a future ClickHouse/Tinybird path:

1. Create the events table or equivalent data source from `infra/clickhouse/events_schema.sql`.
2. Set:

```text
CLICKHOUSE_HOST
CLICKHOUSE_USER
CLICKHOUSE_PASSWORD
CLICKHOUSE_DATABASE
```

3. Wire the event store service to write raw analytics events to the provider. Until that provider path is implemented, keep using the local/PostgreSQL fallback and document the tradeoff in demos.

## 9. Smoke Test The Deployment

1. Open https://signalforge-api-28ht.onrender.com/health.
2. Open https://signalforge-orcin.vercel.app.
3. Register a user, create a project, and create a demo API key.
4. Start the local worker with the Neon and Upstash env vars above.
5. Send traffic:

```bash
python scripts/send_demo_events.py --api-url https://signalforge-api-28ht.onrender.com --project-key sf_demo_your_key --count 20
python scripts/generate_error_spike.py --api-url https://signalforge-api-28ht.onrender.com --project-key sf_demo_your_key
python scripts/generate_latency_spike.py --api-url https://signalforge-api-28ht.onrender.com --project-key sf_demo_your_key
```

6. Confirm the worker processes jobs and `/pipeline-health` shows recent job counts.
7. Verify dashboard metrics, event explorer, anomalies, incidents, incident detail, summary fallback or Gemini output, alert history, and pipeline health.

## Caveats

- Free web services may sleep, so the first request can be slow.
- Free databases and queues have storage, throughput, and connection limits.
- The free hosted setup does not include always-on worker processing. Run the worker locally during demos/testing.
- Local file fallbacks are not shared across deployed instances.
- This deployment is portfolio-scale only and makes no production uptime claim.
- Rotate any leaked API key, webhook, or provider token immediately.
