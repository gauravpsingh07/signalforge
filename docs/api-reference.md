# API Reference

Phase 1 includes service health, user auth, project management, and hashed API key management.

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

## Placeholders

- `/v1/events/status`
- `/metrics/status`
- `/incidents/status`

Future phases will replace placeholders with implemented ingestion, metrics, anomaly, and incident endpoints.
