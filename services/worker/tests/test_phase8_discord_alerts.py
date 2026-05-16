import json
from pathlib import Path

from app.config import get_settings
from app.services.discord_service import DiscordAlertService
from app.services.incident_grouping_service import IncidentGroupingService


def configure(tmp_path: Path) -> tuple[Path, Path, Path]:
    settings = get_settings()
    settings.database_url = ""
    settings.gemini_api_key = ""
    settings.discord_webhook_url = ""
    settings.dashboard_base_url = "http://localhost:5173"
    settings.local_incidents_path = str(tmp_path / "incidents.json")
    settings.local_anomalies_path = str(tmp_path / "anomalies.json")
    settings.local_alerts_path = str(tmp_path / "alerts.json")
    settings.local_event_store_path = str(tmp_path / "events.jsonl")
    settings.incident_grouping_window_minutes = 30
    settings.incident_auto_resolve_cooldown_minutes = 30
    return (
        Path(settings.local_incidents_path),
        Path(settings.local_anomalies_path),
        Path(settings.local_alerts_path),
    )


def anomaly(anomaly_id: str = "anom_1", severity: str = "high") -> dict:
    return {
        "id": anomaly_id,
        "project_id": "project_123",
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
        "fingerprint_hash": "fp_timeout",
        "metadata": {},
        "created_at": "2026-05-15T16:01:00+00:00",
    }


def write_anomalies(path: Path, anomalies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(anomalies), encoding="utf-8")


def read_alerts(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_webhook_marks_alert_skipped(tmp_path: Path) -> None:
    _, anomalies_path, alerts_path = configure(tmp_path)
    write_anomalies(anomalies_path, [anomaly()])

    IncidentGroupingService().group_anomaly(anomaly())

    alerts = read_alerts(alerts_path)
    assert alerts[0]["status"] == "skipped"
    assert alerts[0]["payload"]["alert_type"] == "opened"
    assert alerts[0]["error_message"] == "DISCORD_WEBHOOK_URL is not configured"


def test_open_incident_sends_one_alert(tmp_path: Path) -> None:
    _, anomalies_path, alerts_path = configure(tmp_path)
    get_settings().discord_webhook_url = "https://discord.example/webhook"
    sent_payloads: list[dict] = []
    write_anomalies(anomalies_path, [anomaly("anom_1"), anomaly("anom_2")])
    service = IncidentGroupingService(
        discord_service=DiscordAlertService(sender=lambda _url, payload: sent_payloads.append(payload))
    )

    service.group_anomaly(anomaly("anom_1"))
    service.group_anomaly(anomaly("anom_2"))

    alerts = read_alerts(alerts_path)
    assert len(alerts) == 1
    assert alerts[0]["status"] == "sent"
    assert alerts[0]["payload"]["alert_type"] == "opened"
    assert len(sent_payloads) == 1


def test_severity_escalation_sends_escalation_alert(tmp_path: Path) -> None:
    _, anomalies_path, alerts_path = configure(tmp_path)
    get_settings().discord_webhook_url = "https://discord.example/webhook"
    write_anomalies(anomalies_path, [anomaly("anom_1", "high"), anomaly("anom_2", "critical")])
    service = IncidentGroupingService(discord_service=DiscordAlertService(sender=lambda _url, _payload: None))

    service.group_anomaly(anomaly("anom_1", "high"))
    service.group_anomaly(anomaly("anom_2", "critical"))

    alert_types = [alert["payload"]["alert_type"] for alert in read_alerts(alerts_path)]
    assert alert_types == ["opened", "escalated"]


def test_resolve_sends_one_recovery_alert(tmp_path: Path) -> None:
    _, anomalies_path, alerts_path = configure(tmp_path)
    get_settings().discord_webhook_url = "https://discord.example/webhook"
    write_anomalies(anomalies_path, [anomaly()])
    service = IncidentGroupingService(discord_service=DiscordAlertService(sender=lambda _url, _payload: None))
    incident = service.group_anomaly(anomaly())
    incident["status"] = "resolved"

    service.discord_service.handle_incident_resolved(incident)
    service.discord_service.handle_incident_resolved(incident)

    alert_types = [alert["payload"]["alert_type"] for alert in read_alerts(alerts_path)]
    assert alert_types == ["opened", "resolved"]


def test_failed_webhook_call_is_recorded(tmp_path: Path) -> None:
    _, anomalies_path, alerts_path = configure(tmp_path)
    get_settings().discord_webhook_url = "https://discord.example/webhook"
    write_anomalies(anomalies_path, [anomaly()])

    def fail(_url: str, _payload: dict) -> None:
        raise RuntimeError("webhook failed")

    IncidentGroupingService(discord_service=DiscordAlertService(sender=fail)).group_anomaly(anomaly())

    alerts = read_alerts(alerts_path)
    assert alerts[0]["status"] == "failed"
    assert alerts[0]["error_message"] == "webhook failed"
