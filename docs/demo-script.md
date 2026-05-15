# Demo Script

Phase 0 demo:

1. Start the FastAPI service.
2. Run `GET /health` or open the generated OpenAPI docs at `/docs`.
3. Start the SvelteKit frontend.
4. Open the dashboard shell and pipeline-health route.
5. Start the worker with `python -m app.worker --once` to verify the worker package imports and reports status.

Future demo phases will add project creation, API key generation, normal event traffic, spike generation, anomaly detection, incidents, AI summaries, alerts, and pipeline observability.
