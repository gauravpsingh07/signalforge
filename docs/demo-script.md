# Demo Script

Phase 10 local presenter flow:

1. Start optional local services with `docker compose up -d postgres redis`.
2. If using Postgres, run `psql "postgresql://signalforge:signalforge@localhost:5432/signalforge" -f infra/database/migrations/001_initial_schema.sql`.
3. Start the API from `services/api` with `uvicorn app.main:app --reload --port 8000`.
4. Start the frontend from `apps/web` with `npm run dev`.
5. Register a new user from `/login`.
6. Create a project named `Checkout Service Demo` from `/dashboard` or `/projects`.
7. Open project settings.
8. Create a demo API key and verify the raw key is shown once.
9. Refresh or list keys and verify only the masked prefix is visible.
10. Send normal traffic:
    `python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40`
11. Confirm the script prints accepted job IDs.
12. Run the worker from `services/worker` with `python -m app.worker --once` once per queued event.
13. Open `/projects/{projectId}` and verify total events, error rate, p95 latency, charts, and top services appear.
14. Open `/projects/{projectId}/events` and verify processed events appear with service, level, latency, metadata, and fingerprint details.
15. Run `python scripts/generate_error_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key`.
16. Run the worker once per queued spike event.
17. Open `/projects/{projectId}/anomalies` and verify deterministic anomalies appear.
18. Open `/projects/{projectId}/incidents` and verify related anomalies are grouped into an open incident.
19. Open the incident detail page and verify timeline, related anomalies, fingerprints, and the AI summary card appear. If `GEMINI_API_KEY` is not configured, verify the deterministic fallback summary is shown.
20. Verify the incident detail page shows alert history. If `DISCORD_WEBHOOK_URL` is not configured, verify a skipped Discord alert is logged.
21. Run `python scripts/generate_latency_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key` and repeat the worker drain to show a latency anomaly.
22. Run `python scripts/generate_recovery_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key` and drain worker jobs to show healthy follow-up traffic.
23. Open project settings and verify the Discord alerts card shows whether the global webhook is configured.
24. Click Resolve on an incident and verify the incident status changes to resolved and a resolved alert is logged.
25. Open `/pipeline-health` and verify queue provider, queue depth, worker job counts, average latency, completed jobs, failed/dead-letter totals, and alert delivery failures are visible.
26. Filter the worker job table by failed or dead-letter jobs.
27. Retry a failed local job with an available payload and verify it returns to queued.
28. Use `python scripts/reset_demo_project.py --api-url http://localhost:8000 --project-key sf_demo_your_key --dry-run` to preview local fallback cleanup, then add `--yes` when you want to reset the demo files.

Use `--dry-run` on traffic scripts before a live demo to verify payload generation without contacting the API.

Future demo phases will add deployment documentation and final portfolio polish.
