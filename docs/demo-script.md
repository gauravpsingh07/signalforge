# Demo Script

Phase 1 demo:

1. Start the FastAPI service.
2. Run `GET /health` or open the generated OpenAPI docs at `/docs`.
3. Start the SvelteKit frontend.
4. Register a new user from `/login`.
5. Create a project from `/dashboard` or `/projects`.
6. Open the project settings page.
7. Create a demo API key and verify the raw key is shown once.
8. Refresh or list keys and verify only the masked prefix is visible.
9. Revoke the key and verify its status changes to revoked.
10. Create a second demo key and send events:
    `python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40`
11. Confirm the script prints accepted job IDs.
12. Run the worker from `services/worker` with `python -m app.worker --once` once per queued event.
13. Open `/projects/{projectId}` and verify total events, error rate, p95 latency, charts, and top services appear.
14. Open `/projects/{projectId}/events` and verify processed events appear with service, level, latency, metadata, and fingerprint details.

Future demo phases will add spike generation, metric rollups, anomaly detection, incidents, AI summaries, alerts, and pipeline observability.
