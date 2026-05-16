import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.services.incident_grouping_service import IncidentGroupingService


def configure(tmp_path: Path) -> Path:
    settings = get_settings()
    settings.database_url = ""
    settings.local_incidents_path = str(tmp_path / "incidents.json")
    settings.incident_grouping_window_minutes = 30
    settings.incident_auto_resolve_cooldown_minutes = 30
    return Path(settings.local_incidents_path)


def anomaly(
    anomaly_id: str,
    *,
    service: str = "payment-api",
    anomaly_type: str = "error_rate_spike",
    severity: str = "high",
    fingerprint_hash: str | None = "fp_timeout",
    created_at: str = "2026-05-15T16:01:00+00:00",
) -> dict:
    return {
        "id": anomaly_id,
        "project_id": "project_123",
        "service": service,
        "environment": "production",
        "anomaly_type": anomaly_type,
        "severity": severity,
        "score": 4.5,
        "baseline_value": 0.02,
        "observed_value": 0.4,
        "window_start": "2026-05-15T16:00:00+00:00",
        "window_end": "2026-05-15T16:05:00+00:00",
        "status": "open",
        "fingerprint_hash": fingerprint_hash,
        "metadata": {},
        "created_at": created_at,
    }


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_related_anomalies_attach_to_existing_incident(tmp_path: Path) -> None:
    path = configure(tmp_path)
    service = IncidentGroupingService()

    first = service.group_anomaly(anomaly("anom_1"))
    second = service.group_anomaly(anomaly("anom_2", created_at="2026-05-15T16:03:00+00:00"))

    data = read(path)
    assert first["id"] == second["id"]
    assert len(data["incidents"]) == 1
    assert len(data["incident_events"]) == 2


def test_different_services_create_different_incidents(tmp_path: Path) -> None:
    path = configure(tmp_path)
    service = IncidentGroupingService()

    service.group_anomaly(anomaly("anom_1", service="payment-api"))
    service.group_anomaly(anomaly("anom_2", service="checkout-service"))

    assert len(read(path)["incidents"]) == 2


def test_severity_escalates_when_critical_anomaly_attaches(tmp_path: Path) -> None:
    configure(tmp_path)
    service = IncidentGroupingService()

    incident = service.group_anomaly(anomaly("anom_1", severity="high"))
    escalated = service.group_anomaly(anomaly("anom_2", severity="critical"))

    assert incident["id"] == escalated["id"]
    assert escalated["severity"] == "critical"


def test_resolved_incident_is_not_reused(tmp_path: Path) -> None:
    path = configure(tmp_path)
    service = IncidentGroupingService()
    first = service.group_anomaly(anomaly("anom_1"))
    data = read(path)
    data["incidents"][0]["status"] = "resolved"
    data["incidents"][0]["resolved_at"] = "2026-05-15T16:04:00+00:00"
    path.write_text(json.dumps(data), encoding="utf-8")

    second = service.group_anomaly(anomaly("anom_2", created_at="2026-05-15T16:06:00+00:00"))

    assert first["id"] != second["id"]
    assert len(read(path)["incidents"]) == 2


def test_auto_resolution_marks_stale_incident_resolved(tmp_path: Path) -> None:
    configure(tmp_path)
    service = IncidentGroupingService()
    service.group_anomaly(anomaly("anom_1"))

    resolved = service.auto_resolve(datetime(2026, 5, 15, 16, 45, tzinfo=UTC))

    assert resolved[0]["status"] == "resolved"
    assert resolved[0]["resolved_at"] is not None
