# Free-Tier Strategy

SignalForge is designed to run as a local and portfolio-scale demo without paid infrastructure. External providers are optional for local development and configured only through runtime environment variables.

## Principles

- Keep local development provider-free by default.
- Use shared managed services only when deploying multiple processes.
- Keep ingestion quick: validate, rate-limit, enqueue, and return.
- Run heavy work in the worker: normalization, storage, rollups, anomaly detection, incident grouping, summaries, and alerts.
- Do not commit secrets, tokens, API keys, webhooks, or generated `.env` files.

## Local Fallbacks

| Capability | Local fallback | Free-tier provider |
| --- | --- | --- |
| Metadata/auth | In-memory API fallback or local Postgres | Neon Postgres |
| Queue | Local JSONL queue file | Upstash Redis REST |
| Processed events | Local JSONL event store or PostgreSQL metadata | ClickHouse/Tinybird target schema |
| Fingerprints/rollups/anomalies/incidents/alerts | Local JSON files or PostgreSQL paths | Neon Postgres |
| AI summaries | Deterministic fallback summary | Gemini API |
| Discord alerts | `skipped` alert log when webhook missing | Discord Webhook |

Local JSON files are useful for single-machine demos. They should not be treated as durable shared storage for deployed API/worker processes.

## Rate Limits And Payload Limits

The API protects free-tier resources with configurable limits:

```text
INGEST_RATE_LIMIT_PER_MINUTE=60
INGEST_RATE_LIMIT_PER_IP_MINUTE=120
INGEST_MAX_BATCH_SIZE=25
INGEST_MAX_MESSAGE_LENGTH=2000
INGEST_MAX_METADATA_BYTES=8192
MAX_REQUEST_BODY_BYTES=1048576
```

Collection endpoints also bound pagination so event, anomaly, incident, alert, and worker-job reads stay small during demos.

## Queue Usage

The API enqueues event jobs and returns `202 Accepted` without running analytics, AI, or alert delivery in the request path. This protects the API from slow provider calls and makes worker processing independently retryable.

For local demos, the JSONL queue is enough. For deployed demos, use Upstash Redis REST so the Render API and worker share the same queue.

## Storage And Retention

The MVP keeps local fallback files in `tmp/` and can reset them with:

```bash
python scripts/reset_demo_project.py --api-url http://localhost:8000 --project-key sf_demo_your_key --yes
```

For Neon, keep demo traffic small and periodically reset test projects or database rows if storage grows. A future cleanup job can enforce retention windows; Phase 11 documents the strategy without adding scheduled deletion behavior.

## Event Analytics

`infra/clickhouse/events_schema.sql` documents the intended columnar event analytics shape. The current application remains runnable without ClickHouse or Tinybird by using local/PostgreSQL-compatible storage paths.

When enabling ClickHouse or Tinybird later, preserve the current boundary: the worker should write/query analytics data, while the API ingestion path should only enqueue.

## AI And Alerts

Gemini and Discord are optional:

- Missing `GEMINI_API_KEY` stores a deterministic fallback incident summary.
- Missing `DISCORD_WEBHOOK_URL` records a skipped alert.
- Failed Discord calls are logged and do not crash worker processing.

This keeps demos usable even when provider accounts are not configured or a free-tier provider is unavailable.

## Free-Tier Caveats

- Free services may sleep after inactivity.
- First request latency may be slow.
- Provider quotas can change, so keep limits configurable instead of hardcoding assumptions into code.
- This project is suitable for portfolio demos, not production traffic or uptime claims.
- If a secret is exposed, rotate it in the provider dashboard and revoke any affected SignalForge API keys.
