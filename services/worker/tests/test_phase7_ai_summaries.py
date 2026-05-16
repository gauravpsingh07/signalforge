import json
from pathlib import Path

from app.config import get_settings
from app.services.ai_summary_service import AiSummaryService, sanitize_for_ai, validate_summary_json
from app.services.incident_grouping_service import IncidentGroupingService


def configure(tmp_path: Path) -> tuple[Path, Path]:
    settings = get_settings()
    settings.database_url = ""
    settings.gemini_api_key = ""
    settings.local_incidents_path = str(tmp_path / "incidents.json")
    settings.local_anomalies_path = str(tmp_path / "anomalies.json")
    settings.local_event_store_path = str(tmp_path / "events.jsonl")
    settings.incident_grouping_window_minutes = 30
    settings.incident_auto_resolve_cooldown_minutes = 30
    return Path(settings.local_incidents_path), Path(settings.local_anomalies_path)


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
        "metadata": {"apiKey": "sf_demo_secret"},
        "created_at": "2026-05-15T16:01:00+00:00",
    }


def write_anomalies(path: Path, anomalies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(anomalies), encoding="utf-8")


def read_incidents(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_sanitization_removes_secrets_and_api_keys() -> None:
    sanitized = sanitize_for_ai(
        {
            "message": "failed with key sf_live_supersecret and Authorization: Bearer abc.def",
            "metadata": {"api_key": "sf_demo_hidden", "route": "/checkout"},
        }
    )

    assert "sf_live_supersecret" not in sanitized["message"]
    assert "Bearer abc.def" not in sanitized["message"]
    assert sanitized["metadata"]["api_key"] == "[REDACTED]"


def test_missing_gemini_key_uses_fallback_summary(tmp_path: Path) -> None:
    incidents_path, anomalies_path = configure(tmp_path)
    write_anomalies(anomalies_path, [anomaly()])

    incident = IncidentGroupingService().group_anomaly(anomaly())
    stored = read_incidents(incidents_path)["incidents"][0]
    payload = json.loads(stored["ai_summary"])

    assert incident["id"] == stored["id"]
    assert payload["source"] == "fallback"
    assert payload["affectedService"] == "payment-api"
    assert stored["likely_cause"]
    assert len(stored["recommended_actions"]) >= 1


def test_valid_json_response_is_parsed_and_stored(tmp_path: Path) -> None:
    incidents_path, anomalies_path = configure(tmp_path)
    get_settings().gemini_api_key = "test-key"
    write_anomalies(anomalies_path, [anomaly()])

    def fake_gemini(_: dict) -> str:
        return json.dumps(
            {
                "summary": "Checkout errors are elevated.",
                "affectedService": "payment-api",
                "impact": "Some checkout requests fail.",
                "likelyCause": "Payment provider timeouts.",
                "timeline": [{"time": "16:00", "event": "Error rate exceeded baseline"}],
                "recommendedActions": ["Check payment provider status"],
                "confidence": "medium",
            }
        )

    IncidentGroupingService(ai_summary_service=AiSummaryService(gemini_client=fake_gemini)).group_anomaly(anomaly())
    payload = json.loads(read_incidents(incidents_path)["incidents"][0]["ai_summary"])

    assert payload["source"] == "gemini"
    assert payload["summary"] == "Checkout errors are elevated."
    assert payload["likelyCause"] == "Payment provider timeouts."


def test_invalid_json_response_falls_back_without_crashing(tmp_path: Path) -> None:
    incidents_path, anomalies_path = configure(tmp_path)
    get_settings().gemini_api_key = "test-key"
    write_anomalies(anomalies_path, [anomaly()])

    IncidentGroupingService(
        ai_summary_service=AiSummaryService(gemini_client=lambda _: "not json")
    ).group_anomaly(anomaly())
    payload = json.loads(read_incidents(incidents_path)["incidents"][0]["ai_summary"])

    assert payload["source"] == "fallback"
    assert "error" in payload


def test_summary_is_not_regenerated_unnecessarily(tmp_path: Path) -> None:
    incidents_path, anomalies_path = configure(tmp_path)
    write_anomalies(anomalies_path, [anomaly("anom_1"), anomaly("anom_2")])
    calls = 0

    def fake_gemini(_: dict) -> str:
        nonlocal calls
        calls += 1
        return json.dumps(
            {
                "summary": "Incident summary.",
                "affectedService": "payment-api",
                "impact": "Elevated failures.",
                "likelyCause": "Timeouts.",
                "timeline": [{"time": "16:00", "event": "Error rate spike"}],
                "recommendedActions": ["Inspect checkout"],
                "confidence": "medium",
            }
        )

    get_settings().gemini_api_key = "test-key"
    service = IncidentGroupingService(ai_summary_service=AiSummaryService(gemini_client=fake_gemini))
    service.group_anomaly(anomaly("anom_1"))
    service.group_anomaly(anomaly("anom_2"))

    assert calls == 1
    assert len(read_incidents(incidents_path)["incident_events"]) == 2


def test_validate_summary_json_accepts_strict_contract() -> None:
    payload = validate_summary_json(
        json.dumps(
            {
                "summary": "Summary",
                "affectedService": "payment-api",
                "impact": "Impact",
                "likelyCause": "Cause",
                "timeline": [],
                "recommendedActions": [],
                "confidence": "medium",
            }
        ),
        {"service": "payment-api"},
    )

    assert payload["confidence"] == "medium"
