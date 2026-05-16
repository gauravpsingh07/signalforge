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
    settings.discord_webhook_url = ""
    settings.local_incidents_path = str(tmp_path / "incidents.json")
    settings.local_anomalies_path = str(tmp_path / "anomalies.json")
    settings.local_alerts_path = str(tmp_path / "alerts.json")
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


def write_incident_and_alert(project_id: str) -> None:
    Path(get_settings().local_anomalies_path).write_text("[]", encoding="utf-8")
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
                        "ai_summary": None,
                        "likely_cause": None,
                        "recommended_actions": None,
                        "started_at": "2026-05-15T16:00:00+00:00",
                        "resolved_at": None,
                        "created_at": "2026-05-15T16:01:00+00:00",
                        "updated_at": "2026-05-15T16:01:00+00:00",
                    }
                ],
                "incident_events": [],
            }
        ),
        encoding="utf-8",
    )
    Path(get_settings().local_alerts_path).write_text(
        json.dumps(
            [
                {
                    "id": "alert_1",
                    "project_id": project_id,
                    "incident_id": "incident_1",
                    "channel": "discord",
                    "status": "skipped",
                    "payload": {"alert_type": "opened"},
                    "sent_at": None,
                    "error_message": "DISCORD_WEBHOOK_URL is not configured",
                    "created_at": "2026-05-15T16:02:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_project_alerts_endpoint_returns_history_and_config_flag(client: TestClient) -> None:
    token = register(client, "alerts@example.com")
    project = create_project(client, token)
    write_incident_and_alert(project["id"])

    response = client.get(f"/projects/{project['id']}/alerts", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["discordConfigured"] is False
    assert response.json()["alerts"][0]["payload"]["alert_type"] == "opened"


def test_incident_detail_includes_alert_history(client: TestClient) -> None:
    token = register(client, "alert-detail@example.com")
    project = create_project(client, token)
    write_incident_and_alert(project["id"])

    response = client.get("/incidents/incident_1", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["alert_history"][0]["status"] == "skipped"


def test_manual_resolve_records_recovery_alert_when_webhook_missing(client: TestClient) -> None:
    token = register(client, "alert-resolve@example.com")
    project = create_project(client, token)
    write_incident_and_alert(project["id"])

    response = client.post("/incidents/incident_1/resolve", headers=auth_headers(token))

    assert response.status_code == 200
    alerts = json.loads(Path(get_settings().local_alerts_path).read_text(encoding="utf-8"))
    assert [alert["payload"]["alert_type"] for alert in alerts] == ["opened", "resolved"]
    assert alerts[1]["status"] == "skipped"
