# Demo Script

Phase 9 demo:

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
15. Run `python scripts/generate_error_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key`.
16. Run the worker once per queued spike event.
17. Open `/projects/{projectId}/anomalies` and verify deterministic anomalies appear.
18. Open `/projects/{projectId}/incidents` and verify related anomalies are grouped into an open incident.
19. Open the incident detail page and verify the timeline, related anomalies, fingerprints, and AI summary card appear. If `GEMINI_API_KEY` is not configured, verify the deterministic fallback summary is shown.
20. Verify the incident detail page shows alert history. If `DISCORD_WEBHOOK_URL` is not configured, verify a skipped Discord alert is logged.
21. Open project settings and verify the Discord alerts card shows whether the global webhook is configured.
22. Click Resolve and verify the incident status changes to resolved and a resolved alert is logged.
23. Open `/pipeline-health` and verify queue provider, queue depth, worker job counts, average latency, completed jobs, and alert delivery failures are visible.
24. Filter the worker job table by failed or dead-letter jobs.
25. Retry a failed local job with an available payload and verify it returns to queued.

Future demo phases will add hardening, deployment documentation, and final portfolio polish.
