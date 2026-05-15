from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_metadata_store, get_rate_limiter
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore
from app.services.rate_limit_service import InMemoryRateLimiter


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    store = InMemoryMetadataStore()
    limiter = InMemoryRateLimiter()
    settings = get_settings()
    settings.local_queue_path = str(tmp_path / "queue.jsonl")
    settings.ingest_rate_limit_per_minute = 60
    settings.ingest_rate_limit_per_ip_minute = 120
    app.dependency_overrides[get_metadata_store] = lambda: store
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient) -> str:
    response = client.post(
        "/auth/register",
        json={"email": "ingest@example.com", "password": "correct-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def ingestion_headers(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def create_project_key(client: TestClient) -> tuple[str, str]:
    token = register(client)
    project = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Checkout Service Demo"},
    ).json()
    key = client.post(
        f"/projects/{project['id']}/api-keys",
        headers=auth_headers(token),
        json={"name": "Local demo key"},
    ).json()
    return token, key["raw_key"]


def event_payload(**overrides) -> dict:
    payload = {
        "eventId": "evt_123",
        "service": "payment-api",
        "environment": "production",
        "level": "info",
        "message": "Checkout completed",
        "statusCode": 200,
        "latencyMs": 120,
        "traceId": "trace_abc",
        "requestId": "req_123",
        "metadata": {"route": "/checkout"},
    }
    payload.update(overrides)
    return payload


def test_valid_event_returns_202(client: TestClient) -> None:
    _, raw_key = create_project_key(client)

    response = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["eventId"] == "evt_123"
    assert data["jobId"]
    assert data["status"] == "accepted"


def test_missing_api_key_returns_401(client: TestClient) -> None:
    response = client.post("/v1/events", json=event_payload())

    assert response.status_code == 401


def test_invalid_api_key_returns_401(client: TestClient) -> None:
    response = client.post(
        "/v1/events",
        headers=ingestion_headers("sf_demo_invalid"),
        json=event_payload(),
    )

    assert response.status_code == 401


def test_revoked_api_key_returns_401(client: TestClient) -> None:
    token, raw_key = create_project_key(client)
    key = client.get("/projects", headers=auth_headers(token)).json()
    project_id = key[0]["id"]
    listed = client.get(
        f"/projects/{project_id}/api-keys",
        headers=auth_headers(token),
    ).json()
    client.delete(f"/api-keys/{listed[0]['id']}", headers=auth_headers(token))

    response = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(),
    )

    assert response.status_code == 401


def test_invalid_level_returns_422(client: TestClient) -> None:
    _, raw_key = create_project_key(client)

    response = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(level="notice"),
    )

    assert response.status_code == 422


def test_invalid_status_code_returns_422(client: TestClient) -> None:
    _, raw_key = create_project_key(client)

    response = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(statusCode=99),
    )

    assert response.status_code == 422


def test_oversized_message_returns_422(client: TestClient) -> None:
    _, raw_key = create_project_key(client)

    response = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(message="x" * 2001),
    )

    assert response.status_code == 422


def test_oversized_metadata_returns_422(client: TestClient) -> None:
    _, raw_key = create_project_key(client)

    response = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(metadata={"blob": "x" * 9000}),
    )

    assert response.status_code == 422


def test_rate_limit_returns_429(client: TestClient) -> None:
    get_settings().ingest_rate_limit_per_minute = 1
    _, raw_key = create_project_key(client)

    first = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(eventId="evt_1"),
    )
    second = client.post(
        "/v1/events",
        headers=ingestion_headers(raw_key),
        json=event_payload(eventId="evt_2"),
    )

    assert first.status_code == 202
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_batch_ingestion_enqueues_multiple_jobs(client: TestClient) -> None:
    _, raw_key = create_project_key(client)

    response = client.post(
        "/v1/events/batch",
        headers=ingestion_headers(raw_key),
        json={
            "events": [
                event_payload(eventId="evt_batch_1", level="info"),
                event_payload(eventId="evt_batch_2", level="warn", statusCode=202),
            ]
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["acceptedCount"] == 2
    assert len(data["jobIds"]) == 2
