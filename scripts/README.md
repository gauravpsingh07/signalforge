# Demo Scripts

These scripts generate local SignalForge demo traffic through the ingestion API. They require a project API key created from the dashboard.

```bash
python scripts/send_demo_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key --count 40
python scripts/generate_error_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_latency_spike.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/generate_recovery_events.py --api-url http://localhost:8000 --project-key sf_demo_your_key
python scripts/reset_demo_project.py --api-url http://localhost:8000 --project-key sf_demo_your_key --yes
```

Use `--dry-run` on any script to verify generated payloads without contacting the API. After sending events, run the worker repeatedly from `services/worker` with:

```bash
python -m app.worker --once
```
