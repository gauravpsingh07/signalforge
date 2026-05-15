import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.services.event_normalizer import NormalizedEvent


def bucket_start_for(timestamp: str, bucket_size_seconds: int = 60) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)
    epoch = int(parsed.timestamp())
    bucket_epoch = epoch - (epoch % bucket_size_seconds)
    return datetime.fromtimestamp(bucket_epoch, UTC).isoformat()


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile_value)))
    return ordered[index]


class MetricRollupService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_metric_rollups_path)

    def update_for_event(self, event: NormalizedEvent, bucket_size_seconds: int = 60) -> dict[str, Any]:
        if get_settings().database_url:
            return self._update_postgres(event, bucket_size_seconds)
        return self._update_local(event, bucket_size_seconds)

    def _update_local(self, event: NormalizedEvent, bucket_size_seconds: int) -> dict[str, Any]:
        rollups = self._read()
        bucket_start = bucket_start_for(event.timestamp, bucket_size_seconds)
        key = "|".join(
            [event.project_id, event.service, event.environment, bucket_start, str(bucket_size_seconds)]
        )
        current = rollups.get(
            key,
            {
                "project_id": event.project_id,
                "service": event.service,
                "environment": event.environment,
                "bucket_start": bucket_start,
                "bucket_size_seconds": bucket_size_seconds,
                "total_events": 0,
                "error_events": 0,
                "warning_events": 0,
                "fatal_events": 0,
                "latency_samples": [],
                "latency_avg_ms": None,
                "latency_p95_ms": None,
            },
        )
        current["total_events"] += 1
        if event.level == "error":
            current["error_events"] += 1
        if event.level == "warn":
            current["warning_events"] += 1
        if event.level == "fatal":
            current["fatal_events"] += 1
        if event.latency_ms is not None:
            current["latency_samples"].append(float(event.latency_ms))
            current["latency_avg_ms"] = sum(current["latency_samples"]) / len(current["latency_samples"])
            current["latency_p95_ms"] = percentile(current["latency_samples"], 0.95)
        rollups[key] = current
        self._write(rollups)
        return current

    def _update_postgres(self, event: NormalizedEvent, bucket_size_seconds: int) -> dict[str, Any]:
        bucket_start = bucket_start_for(event.timestamp, bucket_size_seconds)
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT level, latency_ms
                    FROM events_metadata
                    WHERE project_id = %s
                      AND service = %s
                      AND environment = %s
                      AND timestamp >= %s
                      AND timestamp < (%s::timestamptz + (%s || ' seconds')::interval)
                    """,
                    (
                        event.project_id,
                        event.service,
                        event.environment,
                        bucket_start,
                        bucket_start,
                        bucket_size_seconds,
                    ),
                )
                rows = cur.fetchall()
                latency_samples = [
                    float(row["latency_ms"]) for row in rows if row["latency_ms"] is not None
                ]
                rollup = {
                    "project_id": event.project_id,
                    "service": event.service,
                    "environment": event.environment,
                    "bucket_start": bucket_start,
                    "bucket_size_seconds": bucket_size_seconds,
                    "total_events": len(rows),
                    "error_events": sum(1 for row in rows if row["level"] == "error"),
                    "warning_events": sum(1 for row in rows if row["level"] == "warn"),
                    "fatal_events": sum(1 for row in rows if row["level"] == "fatal"),
                    "latency_avg_ms": (sum(latency_samples) / len(latency_samples)) if latency_samples else None,
                    "latency_p95_ms": percentile(latency_samples, 0.95),
                }
                cur.execute(
                    """
                    INSERT INTO metric_rollups
                      (project_id, service, environment, bucket_start, bucket_size_seconds,
                       total_events, error_events, warning_events, fatal_events,
                       latency_avg_ms, latency_p95_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, service, environment, bucket_start, bucket_size_seconds)
                    DO UPDATE SET
                      total_events = EXCLUDED.total_events,
                      error_events = EXCLUDED.error_events,
                      warning_events = EXCLUDED.warning_events,
                      fatal_events = EXCLUDED.fatal_events,
                      latency_avg_ms = EXCLUDED.latency_avg_ms,
                      latency_p95_ms = EXCLUDED.latency_p95_ms
                    """,
                    (
                        rollup["project_id"],
                        rollup["service"],
                        rollup["environment"],
                        rollup["bucket_start"],
                        rollup["bucket_size_seconds"],
                        rollup["total_events"],
                        rollup["error_events"],
                        rollup["warning_events"],
                        rollup["fatal_events"],
                        rollup["latency_avg_ms"],
                        rollup["latency_p95_ms"],
                    ),
                )
                return rollup

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _write(self, rollups: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rollups, indent=2, sort_keys=True), encoding="utf-8")
