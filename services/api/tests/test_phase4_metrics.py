import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_metadata_store
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore
from app.services.metrics_service import calculate_error_rate


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    store = InMemoryMetadataStore()
    get_settings().local_metric_rollups_path = str(tmp_path / "rollups.json")
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


def write_rollup(project_id: str) -> None:
    path = Path(get_settings().local_metric_rollups_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "key": {
                    "project_id": project_id,
                    "service": "payment-api",
                    "environment": "production",
                    "bucket_start": datetime.now(UTC).replace(second=0, microsecond=0).isoformat(),
                    "bucket_size_seconds": 60,
                    "total_events": 10,
                    "error_events": 2,
                    "warning_events": 1,
                    "fatal_events": 0,
                    "latency_avg_ms": 150,
                    "latency_p95_ms": 300,
                    "latency_samples": [100, 150, 300],
                }
            }
        ),
        encoding="utf-8",
    )


def test_error_rate_calculation() -> None:
    assert calculate_error_rate(10, 2) == 0.2
    assert calculate_error_rate(0, 2) == 0.0


def test_metrics_endpoint_returns_rollups(client: TestClient) -> None:
    token = register(client, "metrics@example.com")
    project = create_project(client, token)
    write_rollup(project["id"])

    response = client.get(
        f"/projects/{project['id']}/metrics?range=24h",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["totalEvents"] == 10
    assert data["summary"]["errorRate"] == 0.2
    assert data["series"][0]["latencyP95Ms"] == 300
    assert data["services"] == ["payment-api"]


def test_metrics_endpoint_enforces_ownership(client: TestClient) -> None:
    first_token = register(client, "metrics-owner@example.com")
    second_token = register(client, "metrics-other@example.com")
    project = create_project(client, first_token)
    write_rollup(project["id"])

    response = client.get(
        f"/projects/{project['id']}/metrics",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404
