import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_metadata_store
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    store = InMemoryMetadataStore()
    get_settings().local_event_store_path = str(tmp_path / "events.jsonl")
    app.dependency_overrides[get_metadata_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_project(client: TestClient, token: str) -> dict:
    response = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Checkout Service Demo"},
    )
    assert response.status_code == 201
    return response.json()


def write_event(project_id: str, **overrides) -> None:
    event = {
        "event_id": "evt_1",
        "project_id": project_id,
        "api_key_prefix": "sf_demo_test",
        "timestamp": "2026-05-15T15:45:00+00:00",
        "received_at": "2026-05-15T15:45:01+00:00",
        "service": "payment-api",
        "environment": "production",
        "level": "error",
        "message": "Checkout timeout",
        "normalized_message": "checkout timeout",
        "fingerprint_hash": "abc123",
        "status_code": 504,
        "latency_ms": 2380,
        "trace_id": "trace_123",
        "request_id": "req_123",
        "metadata": {"route": "/checkout"},
    }
    event.update(overrides)
    path = Path(get_settings().local_event_store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as events_file:
        events_file.write(json.dumps(event) + "\n")


def test_project_events_returns_processed_events(client: TestClient) -> None:
    token = register(client, "events@example.com")
    project = create_project(client, token)
    write_event(project["id"])

    response = client.get(
        f"/projects/{project['id']}/events",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["fingerprint_hash"] == "abc123"


def test_project_events_supports_filters(client: TestClient) -> None:
    token = register(client, "filters@example.com")
    project = create_project(client, token)
    write_event(project["id"], event_id="evt_error", level="error", message="Checkout timeout")
    write_event(project["id"], event_id="evt_info", level="info", message="Checkout completed")

    response = client.get(
        f"/projects/{project['id']}/events?level=error&search=timeout",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    assert events[0]["event_id"] == "evt_error"


def test_user_cannot_read_another_users_events(client: TestClient) -> None:
    first_token = register(client, "first-events@example.com")
    second_token = register(client, "second-events@example.com")
    project = create_project(client, first_token)
    write_event(project["id"])

    response = client.get(
        f"/projects/{project['id']}/events",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404
