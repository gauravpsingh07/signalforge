import json
import math
from pathlib import Path

from app.config import get_settings
from app.services.anomaly_service import AnomalyService, z_score
from app.services.event_normalizer import NormalizedEvent


def event(
    *,
    level: str = "error",
    timestamp: str = "2026-05-15T16:00:15+00:00",
    latency_ms: int | None = 1200,
    fingerprint_hash: str = "fp_123",
) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=f"evt_{level}_{timestamp}",
        project_id="project_123",
        api_key_prefix="sf_demo_test",
        timestamp=timestamp,
        received_at=timestamp,
        service="payment-api",
        environment="production",
        level=level,
        message="Checkout timeout",
        normalized_message="checkout timeout",
        fingerprint_hash=fingerprint_hash,
        status_code=500 if level == "error" else 503,
        latency_ms=latency_ms,
        trace_id=None,
        request_id=None,
        metadata={},
    )


def write_rollups(path: Path, buckets: list[dict]) -> None:
    path.write_text(
        json.dumps({str(index): bucket for index, bucket in enumerate(buckets)}),
        encoding="utf-8",
    )


def bucket(
    start: str,
    *,
    total: int,
    errors: int = 0,
    fatal: int = 0,
    p95: int | None = 100,
) -> dict:
    return {
        "project_id": "project_123",
        "service": "payment-api",
        "environment": "production",
        "bucket_start": start,
        "bucket_size_seconds": 60,
        "total_events": total,
        "error_events": errors,
        "warning_events": 0,
        "fatal_events": fatal,
        "latency_avg_ms": p95,
        "latency_p95_ms": p95,
    }


def configure(tmp_path: Path) -> tuple[Path, Path]:
    settings = get_settings()
    settings.local_metric_rollups_path = str(tmp_path / "rollups.json")
    settings.local_anomalies_path = str(tmp_path / "anomalies.json")
    settings.anomaly_min_sample_count = 5
    settings.anomaly_repeated_fingerprint_threshold = 5
    settings.anomaly_fatal_burst_threshold = 3
    return Path(settings.local_metric_rollups_path), Path(settings.local_anomalies_path)


def baseline_buckets() -> list[dict]:
    return [
        bucket("2026-05-15T15:00:00+00:00", total=20, errors=0, p95=100),
        bucket("2026-05-15T15:10:00+00:00", total=20, errors=1, p95=110),
        bucket("2026-05-15T15:20:00+00:00", total=20, errors=0, p95=120),
        bucket("2026-05-15T15:30:00+00:00", total=20, errors=1, p95=100),
        bucket("2026-05-15T15:40:00+00:00", total=20, errors=0, p95=110),
    ]


def test_z_score_calculation() -> None:
    assert z_score(0.5, 0.1, 0.1) == 4
    assert math.isinf(z_score(0.5, 0.0, 0.0))


def test_error_spike_anomaly_created(tmp_path: Path) -> None:
    rollups_path, _ = configure(tmp_path)
    write_rollups(
        rollups_path,
        baseline_buckets()
        + [
            bucket("2026-05-15T16:00:00+00:00", total=10, errors=4, p95=120),
        ],
    )

    anomalies = AnomalyService().detect_for_event(event())

    assert any(item["anomaly_type"] == "error_rate_spike" for item in anomalies)


def test_no_anomaly_when_sample_count_too_low(tmp_path: Path) -> None:
    rollups_path, _ = configure(tmp_path)
    write_rollups(
        rollups_path,
        baseline_buckets()
        + [
            bucket("2026-05-15T16:00:00+00:00", total=4, errors=4, p95=120),
        ],
    )

    anomalies = AnomalyService().detect_for_event(event())

    assert anomalies == []


def test_latency_spike_anomaly_created(tmp_path: Path) -> None:
    rollups_path, _ = configure(tmp_path)
    write_rollups(
        rollups_path,
        baseline_buckets()
        + [
            bucket("2026-05-15T16:00:00+00:00", total=10, errors=0, p95=1500),
        ],
    )

    anomalies = AnomalyService().detect_for_event(event(level="info", latency_ms=1500))

    assert any(item["anomaly_type"] == "latency_spike" for item in anomalies)


def test_new_repeated_fingerprint_anomaly_created(tmp_path: Path) -> None:
    rollups_path, _ = configure(tmp_path)
    write_rollups(rollups_path, [bucket("2026-05-15T16:00:00+00:00", total=5, errors=5)])

    anomalies = AnomalyService().detect_for_event(
        event(),
        {
            "fingerprint_hash": "fp_123",
            "occurrence_count": 5,
            "first_seen_at": "2026-05-15T16:00:01+00:00",
        },
    )

    assert any(item["anomaly_type"] == "new_repeated_error" for item in anomalies)


def test_fatal_burst_creates_critical_anomaly(tmp_path: Path) -> None:
    rollups_path, _ = configure(tmp_path)
    write_rollups(
        rollups_path,
        baseline_buckets()
        + [
            bucket("2026-05-15T16:00:00+00:00", total=6, fatal=3, p95=120),
        ],
    )

    anomalies = AnomalyService().detect_for_event(event(level="fatal"))

    assert any(item["anomaly_type"] == "fatal_event_burst" and item["severity"] == "critical" for item in anomalies)


def test_duplicate_anomaly_not_created_repeatedly(tmp_path: Path) -> None:
    rollups_path, anomalies_path = configure(tmp_path)
    write_rollups(
        rollups_path,
        baseline_buckets()
        + [
            bucket("2026-05-15T16:00:00+00:00", total=10, errors=6, p95=120),
        ],
    )
    service = AnomalyService()

    first = service.detect_for_event(event())
    second = service.detect_for_event(event())

    assert len(first) >= 1
    assert second == []
    stored = json.loads(anomalies_path.read_text(encoding="utf-8"))
    assert len(stored) == len(first)
