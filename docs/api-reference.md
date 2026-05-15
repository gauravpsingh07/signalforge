# API Reference

Phase 0 includes only service status endpoints and placeholder route modules.

## Implemented

### `GET /health`

Returns API service health.

```json
{
  "service": "signalforge-api",
  "status": "healthy",
  "version": "0.0.1",
  "timestamp": "2026-05-15T00:00:00+00:00"
}
```

### `GET /`

Returns a root API status payload.

## Placeholders

- `/auth/status`
- `/projects/status`
- `/api-keys/status`
- `/v1/events/status`
- `/metrics/status`
- `/incidents/status`

Future phases will replace placeholders with implemented auth, project, API key, ingestion, metrics, anomaly, and incident endpoints.
