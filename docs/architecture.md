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

Phase 0 implements the shell for the frontend, API, worker, local infrastructure, and documentation. Event ingestion, queueing, anomaly detection, incident grouping, AI summaries, alerts, and pipeline health are added in later phases.
