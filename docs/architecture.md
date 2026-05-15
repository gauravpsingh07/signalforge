# Architecture

SignalForge is designed as a distributed observability pipeline.

```text
+--------------------+       +----------------------+       +-------------------+
| SvelteKit Frontend | <---> | FastAPI Backend API  | ----> | Neon PostgreSQL   |
| Dashboard + Auth   |       | Projects/API/Events  |       | Metadata/Rollups  |
+--------------------+       +----------+-----------+       +-------------------+
                                      |
                                      v
                             +-------------------+
                             | Upstash Queue     |
                             | QStash/Redis      |
                             +---------+---------+
                                       |
                                       v
                             +-------------------+
                             | Python Worker     |
                             | Normalize/Detect  |
                             +----+--------+-----+
                                  |        |
                                  v        v
                       +----------------+  +---------------------+
                       | ClickHouse /   |  | Gemini API          |
                       | Tinybird       |  | Incident Summary    |
                       +----------------+  +----------+----------+
                                                  |
                                                  v
                                           +--------------+
                                           | Discord Alert|
                                           +--------------+
```

Phase 3 implements the API ingestion path, local queue fallback, worker event processing, deterministic fingerprinting, idempotent event storage, and event explorer. Metric rollups, anomaly detection, incident grouping, AI summaries, alerts, and pipeline health are added in later phases.
