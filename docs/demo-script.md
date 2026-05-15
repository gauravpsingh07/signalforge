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
    `python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key`
11. Confirm the script prints accepted job IDs.
12. Open `/projects/{projectId}/events` and note that event explorer rows arrive after later worker processing phases.
13. Start the worker with `python -m app.worker --once` to verify the worker package imports and reports status.

Future demo phases will add spike generation, event storage, anomaly detection, incidents, AI summaries, alerts, and pipeline observability.
