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
10. Start the worker with `python -m app.worker --once` to verify the worker package imports and reports status.

Future demo phases will add normal event traffic, spike generation, anomaly detection, incidents, AI summaries, alerts, and pipeline observability.
