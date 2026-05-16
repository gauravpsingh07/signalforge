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
    get_settings().local_anomalies_path = str(tmp_path / "anomalies.json")
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


def write_anomaly(project_id: str, severity: str = "high") -> None:
    path = Path(get_settings().local_anomalies_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "id": "anom_1",
                    "project_id": project_id,
                    "service": "payment-api",
                    "environment": "production",
                    "anomaly_type": "error_rate_spike",
                    "severity": severity,
                    "score": 4.5,
                    "baseline_value": 0.02,
                    "observed_value": 0.4,
                    "window_start": "2026-05-15T16:00:00+00:00",
                    "window_end": "2026-05-15T16:05:00+00:00",
                    "status": "open",
                    "fingerprint_hash": None,
                    "metadata": {},
                    "created_at": "2026-05-15T16:01:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_anomalies_endpoint_returns_project_anomalies(client: TestClient) -> None:
    token = register(client, "anomalies@example.com")
    project = create_project(client, token)
    write_anomaly(project["id"])

    response = client.get(
        f"/projects/{project['id']}/anomalies?severity=high",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["anomalies"][0]["anomaly_type"] == "error_rate_spike"


def test_anomalies_endpoint_enforces_ownership(client: TestClient) -> None:
    first_token = register(client, "anomaly-owner@example.com")
    second_token = register(client, "anomaly-other@example.com")
    project = create_project(client, first_token)
    write_anomaly(project["id"])

    response = client.get(
        f"/projects/{project['id']}/anomalies",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404
