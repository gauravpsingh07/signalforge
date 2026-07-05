import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.services.anomaly_service import AnomalyService, five_minute_window
from app.services.event_normalizer import NormalizedEvent

PROJECT_ID = "project-1"
NOW = datetime(2026, 7, 5, 12, 2, 0, tzinfo=UTC)


def make_event() -> NormalizedEvent:
    return NormalizedEvent(
        event_id="evt-1",
        project_id=PROJECT_ID,
        api_key_prefix="sf_demo_test0000",
        timestamp=NOW.isoformat(),
        received_at=NOW.isoformat(),
        service="checkout-api",
        environment="production",
        level="error",
        message="boom",
        normalized_message="boom",
        fingerprint_hash="hash-1",
        status_code=500,
        latency_ms=100,
        trace_id=None,
        request_id=None,
        metadata={},
    )


def write_current_window_rollup(path: Path, total: int, errors: int) -> None:
    window_start, _ = five_minute_window(NOW.isoformat())
    path.write_text(
        json.dumps(
            {
                "bucket": {
                    "project_id": PROJECT_ID,
                    "service": "checkout-api",
                    "environment": "production",
                    "bucket_start": window_start.isoformat(),
                    "bucket_size_seconds": 60,
                    "total_events": total,
                    "error_events": errors,
                    "warning_events": 0,
                    "fatal_events": 0,
                    "latency_avg_ms": 100,
                    "latency_p95_ms": 200,
                }
            }
        ),
        encoding="utf-8",
    )


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


def test_fast_budget_burn_creates_slo_anomaly(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    write_current_window_rollup(service.rollups_path, total=10, errors=8)

    candidates = service.build_candidates(make_event())
    slo_candidates = [c for c in candidates if c.anomaly_type == "slo_fast_burn"]

    assert len(slo_candidates) == 1
    candidate = slo_candidates[0]
    assert candidate.severity == "high"
    assert candidate.score == 160.0
    assert candidate.baseline_value == 0.005
    assert candidate.metadata["slo_target"] == get_settings().slo_target


def test_no_slo_anomaly_below_fast_burn_threshold(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    # 2% error rate = 4x burn on a 0.5% budget: at risk, but not page-worthy.
    write_current_window_rollup(service.rollups_path, total=100, errors=2)

    candidates = service.build_candidates(make_event())

    assert [c for c in candidates if c.anomaly_type == "slo_fast_burn"] == []
