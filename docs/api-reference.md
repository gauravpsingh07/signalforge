# API Reference

Phase 5 includes service health, user auth, project management, hashed API key management, async event ingestion, processed event search, metrics, and anomaly reads.

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
    "activeIncidents": 0
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

## Placeholders

- `/v1/events/status`
- `/metrics/status`
- `/incidents/status`

Future phases will replace remaining placeholders with incident endpoints.
