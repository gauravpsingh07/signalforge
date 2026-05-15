from app.services.event_normalizer import NormalizedEvent
from app.services.metric_rollup_service import MetricRollupService, bucket_start_for, percentile


def event(level: str = "info", latency_ms: int | None = 100) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=f"evt_{level}_{latency_ms}",
        project_id="project_123",
        api_key_prefix="sf_demo_test",
        timestamp="2026-05-15T15:45:23+00:00",
        received_at="2026-05-15T15:45:24+00:00",
        service="payment-api",
        environment="production",
        level=level,
        message="Checkout completed",
        normalized_message="checkout completed",
        fingerprint_hash="abc123",
        status_code=200,
        latency_ms=latency_ms,
        trace_id=None,
        request_id=None,
        metadata={},
    )


def test_rollup_bucket_calculation() -> None:
    assert bucket_start_for("2026-05-15T15:45:23+00:00") == "2026-05-15T15:45:00+00:00"


def test_latency_percentile() -> None:
    assert percentile([100, 200, 300, 400], 0.95) == 400


def test_rollup_counts_and_latency(tmp_path) -> None:
    service = MetricRollupService(str(tmp_path / "rollups.json"))

    service.update_for_event(event("info", 100))
    service.update_for_event(event("warn", 200))
    rollup = service.update_for_event(event("error", 300))

    assert rollup["total_events"] == 3
    assert rollup["warning_events"] == 1
    assert rollup["error_events"] == 1
    assert rollup["latency_avg_ms"] == 200
    assert rollup["latency_p95_ms"] == 300
