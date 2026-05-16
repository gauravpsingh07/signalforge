# API Reference

Phase 8 includes service health, user auth, project management, hashed API key management, async event ingestion, processed event search, metrics, anomaly reads, incident lifecycle APIs, cached AI incident summaries, and Discord alert history.

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

## Auth

### `POST /auth/register`

Creates a user and returns a JWT access token.

```json
{
  "email": "dev@example.com",
  "password": "correct-password"
}
```

### `POST /auth/login`

Authenticates an existing user and returns a JWT access token.

### `GET /auth/me`

Returns the current user. Requires `Authorization: Bearer <token>`.

## Projects

### `GET /projects`

Lists projects owned by the current user.

### `POST /projects`

Creates a project owned by the current user.

```json
{
  "name": "Checkout Service Demo",
  "description": "Demo checkout observability project",
  "environment_default": "production"
}
```

### `GET /projects/{project_id}`

Returns one owned project or `404` if it does not belong to the current user.

### `PATCH /projects/{project_id}`

Updates an owned project.

## API Keys

### `POST /projects/{project_id}/api-keys`

Creates an ingestion API key for an owned project. The raw key is returned only once.

```json
{
  "name": "Local demo key",
  "mode": "demo"
}
```

### `GET /projects/{project_id}/api-keys`

Lists masked API keys. Raw keys and hashes are never returned.

### `DELETE /api-keys/{key_id}`

Revokes a key by setting `revoked_at`.

## Event Ingestion

Public ingestion uses project API keys, not dashboard JWTs.

### `POST /v1/events`

Requires `Authorization: Bearer <raw_project_api_key>`.

```json
{
  "eventId": "evt_123_optional_client_id",
  "timestamp": "2026-05-15T15:45:00Z",
  "service": "payment-api",
  "environment": "production",
  "level": "error",
  "message": "Stripe checkout timeout while creating session",
  "statusCode": 504,
  "latencyMs": 2380,
  "traceId": "trace_abc123",
  "requestId": "req_789",
  "metadata": {
    "route": "/checkout",
    "region": "us-east-1"
  }
}
```

Response:

```json
{
  "eventId": "evt_123_optional_client_id",
  "jobId": "97b3f0d5-7f7c-4a1f-b7de-7f91f4f30172",
  "status": "accepted"
}
```

### `POST /v1/events/batch`

Requires `Authorization: Bearer <raw_project_api_key>`.

```json
{
  "events": [
    {
      "service": "payment-api",
      "level": "info",
      "message": "Checkout completed"
    },
    {
      "service": "payment-api",
      "level": "warn",
      "message": "Payment provider latency elevated",
      "latencyMs": 840
    }
  ]
}
```

Response:

```json
{
  "acceptedCount": 2,
  "jobIds": ["job_1", "job_2"],
  "status": "accepted"
}
```

Invalid API keys return `401`, validation failures return `422`, and rate limits return `429` with `Retry-After`.

## Event Search

### `GET /projects/{project_id}/events`

Requires dashboard JWT auth. Returns processed events for an owned project.

Supported query filters:

- `service`
- `environment`
- `level`
- `start`
- `end`
- `search`
- `limit`

Response:

```json
{
  "events": [
    {
      "event_id": "evt_123",
      "project_id": "project_uuid",
      "timestamp": "2026-05-15T15:45:00+00:00",
      "service": "payment-api",
      "environment": "production",
      "level": "error",
      "message": "Checkout timeout",
      "fingerprint_hash": "abc123",
      "status_code": 504,
      "latency_ms": 2380,
      "metadata": {"route": "/checkout"}
    }
  ]
}
```

## Metrics

### `GET /projects/{project_id}/metrics`

Requires dashboard JWT auth. Returns dashboard-friendly rollups for an owned project.

Query params:

- `range`: `1h`, `6h`, or `24h`
- `service`
- `environment`
- `bucketSize`: default `60`

Response:

```json
{
  "range": "1h",
  "bucketSize": 60,
  "summary": {
    "totalEvents": 42,
    "errorEvents": 3,
    "warningEvents": 5,
    "fatalEvents": 0,
    "latencyP95Ms": 900,
    "errorRate": 0.071,
    "activeIncidents": 1
  },
  "series": [],
  "services": ["payment-api"],
  "topServices": []
}
```

### `GET /projects/{project_id}/services`

Returns services with rollup data for filter controls.

## Anomalies

### `GET /projects/{project_id}/anomalies`

Requires dashboard JWT auth. Returns deterministic anomalies for an owned project.

Supported filters:

- `service`
- `environment`
- `severity`
- `status`
- `anomaly_type`
- `start`
- `end`
- `limit`

Response:

```json
{
  "anomalies": [
    {
      "id": "anomaly_uuid",
      "service": "payment-api",
      "environment": "production",
      "anomaly_type": "error_rate_spike",
      "severity": "high",
      "score": 4.2,
      "baseline_value": 0.03,
      "observed_value": 0.42,
      "window_start": "2026-05-15T16:00:00+00:00",
      "window_end": "2026-05-15T16:05:00+00:00",
      "status": "open"
    }
  ]
}
```

## Incidents

### `GET /projects/{project_id}/incidents`

Requires dashboard JWT auth. Returns incidents for an owned project.

Supported filters:

- `service`
- `environment`
- `severity`
- `status`
- `limit`

Response:

```json
{
  "incidents": [
    {
      "id": "incident_uuid",
      "project_id": "project_uuid",
      "title": "High error rate in payment-api",
      "service": "payment-api",
      "environment": "production",
      "severity": "high",
      "status": "open",
      "ai_summary": "{\"summary\":\"Checkout errors are elevated.\"}",
      "ai_summary_payload": {
        "summary": "Checkout errors are elevated.",
        "affectedService": "payment-api",
        "impact": "Some checkout requests fail.",
        "likelyCause": "Payment provider timeouts.",
        "timeline": [{"time": "16:00", "event": "Error rate exceeded baseline"}],
        "recommendedActions": ["Check payment provider status"],
        "confidence": "medium",
        "source": "fallback"
      },
      "likely_cause": "Payment provider timeouts.",
      "recommended_actions": ["Check payment provider status"],
      "started_at": "2026-05-15T16:00:00+00:00",
      "resolved_at": null,
      "created_at": "2026-05-15T16:01:00+00:00",
      "updated_at": "2026-05-15T16:03:00+00:00",
      "related_anomaly_count": 2
    }
  ]
}
```

### `GET /incidents/{incident_id}`

Requires dashboard JWT auth and enforces project ownership. Returns incident detail for investigation.

Response:

```json
{
  "incident": {
    "id": "incident_uuid",
    "title": "High error rate in payment-api",
    "service": "payment-api",
    "environment": "production",
    "severity": "high",
    "status": "open",
    "ai_summary_payload": {
      "summary": "Checkout errors are elevated.",
      "affectedService": "payment-api",
      "impact": "Some checkout requests fail.",
      "likelyCause": "Payment provider timeouts.",
      "timeline": [{"time": "16:00", "event": "Error rate exceeded baseline"}],
      "recommendedActions": ["Check payment provider status"],
      "confidence": "medium",
      "source": "fallback"
    },
    "related_anomaly_count": 2
  },
  "related_anomalies": [],
  "related_fingerprints": ["fingerprint_hash"],
  "event_samples": [],
  "alert_history": [
    {
      "id": "alert_uuid",
      "channel": "discord",
      "status": "skipped",
      "payload": {"alert_type": "opened"},
      "sent_at": null,
      "error_message": "DISCORD_WEBHOOK_URL is not configured",
      "created_at": "2026-05-15T16:02:00+00:00"
    }
  ],
  "timeline": [
    {
      "time": "2026-05-15T16:00:00+00:00",
      "label": "Incident opened",
      "description": "High error rate in payment-api"
    }
  ]
}
```

## Alerts

### `GET /projects/{project_id}/alerts`

Requires dashboard JWT auth. Returns alert history for an owned project and whether a global Discord webhook is configured.

Supported filters:

- `incident_id`
- `status`
- `channel`
- `limit`

Response:

```json
{
  "discordConfigured": false,
  "alerts": [
    {
      "id": "alert_uuid",
      "project_id": "project_uuid",
      "incident_id": "incident_uuid",
      "channel": "discord",
      "status": "skipped",
      "payload": {
        "alert_type": "opened",
        "content": "Incident opened: High error rate in payment-api"
      },
      "sent_at": null,
      "error_message": "DISCORD_WEBHOOK_URL is not configured",
      "created_at": "2026-05-15T16:02:00+00:00"
    }
  ]
}
```

Alert statuses:

- `sent`: webhook request succeeded.
- `skipped`: `DISCORD_WEBHOOK_URL` is not configured.
- `failed`: webhook request failed but did not crash the pipeline.

## Incident Actions

### `POST /incidents/{incident_id}/resolve`

Requires dashboard JWT auth and enforces project ownership. Marks the incident resolved.

Response:

```json
{
  "incident": {
    "id": "incident_uuid",
    "status": "resolved",
    "resolved_at": "2026-05-15T16:30:00+00:00"
  }
}
```

## Placeholders

- `/v1/events/status`
- `/metrics/status`

Future phases will add pipeline-health APIs.
