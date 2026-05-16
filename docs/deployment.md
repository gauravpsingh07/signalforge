# Deployment

This guide prepares SignalForge for a free-tier portfolio deployment. It does not include real secrets, deployed URLs, screenshots, or resume copy.

## Targets

| Service | Suggested free-tier target | Notes |
| --- | --- | --- |
| Frontend | Vercel or Cloudflare Pages | SvelteKit app in `apps/web`. |
| API | Render free web service | FastAPI app in `services/api`. |
| Worker | Render background worker, or local worker for demo | Worker polls the configured queue with `python -m app.worker`. |
| PostgreSQL | Neon free tier | Run `infra/database/migrations/001_initial_schema.sql`. |
| Queue | Upstash Redis REST, with local JSONL fallback | API pushes jobs and worker pops jobs when Upstash env vars are configured. |
| Event analytics | Current local/PostgreSQL fallback; ClickHouse/Tinybird schema documented | `infra/clickhouse/events_schema.sql` is the target analytics schema. |
| AI | Gemini API, with deterministic fallback | Missing `GEMINI_API_KEY` does not break the worker. |
| Alerts | Discord Webhook | Missing webhook records skipped alerts. |

Free services may sleep. Treat this as portfolio-scale infrastructure, not a production SLA.

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

4. Set the same `DATABASE_URL` in the API and worker environments.

Local equivalent:

```bash
docker compose up -d postgres
psql "postgresql://signalforge:signalforge@localhost:5432/signalforge" -f infra/database/migrations/001_initial_schema.sql
```

If `DATABASE_URL` is blank, SignalForge still runs locally with in-memory or file fallbacks, but deployed API and worker instances should share Neon so state persists across restarts.

## 3. Create Upstash Redis

1. Create an Upstash Redis database.
2. Copy the REST URL and REST token.
3. Set these on both API and worker:

```text
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
```

The local JSONL queue fallback is useful for local demos only. A deployed API and worker need a shared queue provider such as Upstash.

`QSTASH_TOKEN` is reserved for future QStash-style delivery. The current queue implementation uses Upstash Redis REST when the Redis URL and token are present.

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

## 6. Deploy Worker To Render

This repo includes a Render background worker definition named `signalforge-worker`.

Manual Render settings:

```text
Root Directory: services/worker
Build Command: python -m pip install -r requirements.txt
Start Command: python -m app.worker
```

Required worker env vars for a deployed demo:

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

If a free background worker is unavailable, keep the API deployed and run the worker locally during demos:

```bash
cd services/worker
python -m app.worker
```

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
PUBLIC_API_BASE_URL=<api-origin>
```

Use the actual API host from your provider dashboard. Do not commit it unless it is intentionally public and stable.

### Cloudflare Pages

Use the same app root:

```text
Root Directory: apps/web
Build Command: npm run build
Environment Variable: PUBLIC_API_BASE_URL=<api-origin>
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

1. Open the API `/health` endpoint.
2. Open the frontend login page.
3. Register a user, create a project, and create a demo API key.
4. Send traffic:

```bash
python scripts/send_demo_events.py --api-url <api-origin> --project-key sf_demo_your_key --count 20
```

5. Confirm the worker processes jobs and `/pipeline-health` shows recent job counts.
6. Generate an error spike and verify anomalies, incidents, summary fallback or Gemini output, and alert logging.

## Caveats

- Free web services may sleep, so the first request can be slow.
- Free databases and queues have storage, throughput, and connection limits.
- Local file fallbacks are not shared across deployed instances.
- This deployment is portfolio-scale only and makes no production uptime claim.
- Rotate any leaked API key, webhook, or provider token immediately.
