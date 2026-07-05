import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.services.anomaly_service import AnomalyService
from app.services.event_normalizer import NormalizedEvent

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)
PROJECT_ID = "project-1"


def make_event(service: str = "payment-api") -> NormalizedEvent:
    return NormalizedEvent(
        event_id="evt-1",
        project_id=PROJECT_ID,
        api_key_prefix="sf_demo_test0000",
        timestamp=NOW.isoformat(),
        received_at=NOW.isoformat(),
        service=service,
        environment="production",
        level="info",
        message="ok",
        normalized_message="ok",
        fingerprint_hash="hash-1",
        status_code=200,
        latency_ms=100,
        trace_id=None,
        request_id=None,
        metadata={},
    )


def write_rollups(path: Path, last_checkout_bucket_minutes_ago: int) -> None:
    buckets = {}
    for offset, minutes_ago in enumerate(range(last_checkout_bucket_minutes_ago + 10, last_checkout_bucket_minutes_ago - 1, -1)):
        bucket_start = NOW - timedelta(minutes=minutes_ago)
        buckets[f"checkout-{offset}"] = {
            "project_id": PROJECT_ID,
            "service": "checkout-api",
            "environment": "production",
            "bucket_start": bucket_start.isoformat(),
            "bucket_size_seconds": 60,
            "total_events": 5,
            "error_events": 0,
            "warning_events": 0,
            "fatal_events": 0,
            "latency_avg_ms": 100,
            "latency_p95_ms": 200,
        }
    buckets["payment-now"] = {
        "project_id": PROJECT_ID,
        "service": "payment-api",
        "environment": "production",
        "bucket_start": NOW.isoformat(),
        "bucket_size_seconds": 60,
        "total_events": 3,
        "error_events": 0,
        "warning_events": 0,
        "fatal_events": 0,
        "latency_avg_ms": 100,
        "latency_p95_ms": 200,
    }
    path.write_text(json.dumps(buckets), encoding="utf-8")


def make_service(tmp_path: Path) -> AnomalyService:
    settings = get_settings()
    settings.database_url = ""
    settings.upstash_redis_rest_url = ""
    settings.upstash_redis_rest_token = ""
    return AnomalyService(
        rollups_path=str(tmp_path / "rollups.json"),
        fingerprints_path=str(tmp_path / "fingerprints.json"),
        anomalies_path=str(tmp_path / "anomalies.json"),
    )


def test_detects_recently_silent_sibling_service(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    write_rollups(service.rollups_path, last_checkout_bucket_minutes_ago=30)

    created = service.detect_service_silence(make_event())

    assert len(created) == 1
    anomaly = created[0]
    assert anomaly["anomaly_type"] == "service_silence"
    assert anomaly["service"] == "checkout-api"
    assert anomaly["severity"] == "high"
    assert anomaly["observed_value"] >= get_settings().anomaly_service_silence_minutes


def test_silence_anomaly_deduplicates_while_open(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    write_rollups(service.rollups_path, last_checkout_bucket_minutes_ago=30)

    first = service.detect_service_silence(make_event())
    second = service.detect_service_silence(make_event())

    assert len(first) == 1
    assert second == []


def test_ignores_services_active_within_threshold(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    write_rollups(service.rollups_path, last_checkout_bucket_minutes_ago=5)

    assert service.detect_service_silence(make_event()) == []


def test_ignores_services_silent_beyond_lookback(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    write_rollups(
        service.rollups_path,
        last_checkout_bucket_minutes_ago=get_settings().anomaly_service_silence_lookback_minutes + 30,
    )

    assert service.detect_service_silence(make_event()) == []


def test_never_flags_the_reporting_service_itself(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    write_rollups(service.rollups_path, last_checkout_bucket_minutes_ago=30)

    created = service.detect_service_silence(make_event(service="checkout-api"))

    assert created == []
