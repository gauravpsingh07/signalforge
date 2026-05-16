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
    settings = get_settings()
    settings.database_url = ""
    settings.local_incidents_path = str(tmp_path / "incidents.json")
    settings.local_anomalies_path = str(tmp_path / "anomalies.json")
    settings.local_event_store_path = str(tmp_path / "events.jsonl")
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


def write_summarized_incident(project_id: str) -> None:
    summary = {
        "summary": "Checkout errors are elevated after deterministic grouping.",
        "affectedService": "payment-api",
        "impact": "Some checkout requests fail.",
        "likelyCause": "Payment provider timeouts.",
        "timeline": [{"time": "16:00", "event": "Error rate exceeded baseline"}],
        "recommendedActions": ["Check payment provider status"],
        "confidence": "medium",
        "source": "fallback",
    }
    Path(get_settings().local_anomalies_path).write_text(
        json.dumps(
            [
                {
                    "id": "anom_1",
                    "project_id": project_id,
                    "service": "payment-api",
                    "environment": "production",
                    "anomaly_type": "error_rate_spike",
                    "severity": "high",
                    "score": 4.5,
                    "baseline_value": 0.02,
                    "observed_value": 0.4,
                    "window_start": "2026-05-15T16:00:00+00:00",
                    "window_end": "2026-05-15T16:05:00+00:00",
                    "status": "open",
                    "fingerprint_hash": "fp_timeout",
                    "metadata": {},
                    "created_at": "2026-05-15T16:01:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    Path(get_settings().local_incidents_path).write_text(
        json.dumps(
            {
                "incidents": [
                    {
                        "id": "incident_1",
                        "project_id": project_id,
                        "title": "High error rate in payment-api",
                        "service": "payment-api",
                        "environment": "production",
                        "severity": "high",
                        "status": "open",
                        "ai_summary": json.dumps(summary),
                        "likely_cause": summary["likelyCause"],
                        "recommended_actions": summary["recommendedActions"],
                        "started_at": "2026-05-15T16:00:00+00:00",
                        "resolved_at": None,
                        "created_at": "2026-05-15T16:01:00+00:00",
                        "updated_at": "2026-05-15T16:01:00+00:00",
                    }
                ],
                "incident_events": [
                    {
                        "id": "link_1",
                        "incident_id": "incident_1",
                        "anomaly_id": "anom_1",
                        "fingerprint_id": None,
                        "fingerprint_hash": "fp_timeout",
                        "anomaly_type": "error_rate_spike",
                        "event_external_id": None,
                        "created_at": "2026-05-15T16:01:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_incident_detail_includes_structured_ai_summary(client: TestClient) -> None:
    token = register(client, "summary@example.com")
    project = create_project(client, token)
    write_summarized_incident(project["id"])

    response = client.get("/incidents/incident_1", headers=auth_headers(token))

    assert response.status_code == 200
    summary = response.json()["incident"]["ai_summary_payload"]
    assert summary["affectedService"] == "payment-api"
    assert summary["recommendedActions"] == ["Check payment provider status"]
    assert summary["source"] == "fallback"
