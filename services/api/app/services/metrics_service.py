import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.services.incident_service import IncidentQueryService


def calculate_error_rate(total_events: int, error_events: int, fatal_events: int = 0) -> float:
    if total_events <= 0:
        return 0.0
    return (error_events + fatal_events) / total_events


class MetricsService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_metric_rollups_path)

    def get_project_metrics(
        self,
        *,
        project_id: str,
        range_value: str = "1h",
        service: str | None = None,
        environment: str | None = None,
        bucket_size: int = 60,
    ) -> dict[str, Any]:
        rollups = self._load_rollups(
            project_id=project_id,
            service=service,
            environment=environment,
            bucket_size=bucket_size,
        )
        filtered = self._filter_range(rollups, range_value)
        series = [self._public_bucket(bucket) for bucket in sorted(filtered, key=lambda item: item["bucket_start"])]
        totals = self._totals(filtered)
        services = self._services(rollups)
        top_services = self._top_services(filtered)

        return {
            "range": range_value,
            "bucketSize": bucket_size,
            "summary": {
                **totals,
                "errorRate": calculate_error_rate(
                    totals["totalEvents"],
                    totals["errorEvents"],
                    totals["fatalEvents"],
                ),
                "activeIncidents": IncidentQueryService().count_open(project_id),
            },
            "series": series,
            "services": services,
            "topServices": top_services,
        }

    def _load_rollups(
        self,
        *,
        project_id: str,
        service: str | None,
        environment: str | None,
        bucket_size: int,
    ) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._load_postgres(project_id, service, environment, bucket_size)
        return self._load_local(project_id, service, environment, bucket_size)

    def _load_local(
        self,
        project_id: str,
        service: str | None,
        environment: str | None,
        bucket_size: int,
    ) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        rollups = [
            bucket for bucket in data.values()
            if bucket.get("project_id") == project_id
            and bucket.get("bucket_size_seconds") == bucket_size
        ]
        if service:
            rollups = [bucket for bucket in rollups if bucket.get("service") == service.lower()]
        if environment:
            rollups = [bucket for bucket in rollups if bucket.get("environment") == environment.lower()]
        return rollups

    def _load_postgres(
        self,
        project_id: str,
        service: str | None,
        environment: str | None,
        bucket_size: int,
    ) -> list[dict[str, Any]]:
        clauses = ["project_id = %s", "bucket_size_seconds = %s"]
        params: list[Any] = [project_id, bucket_size]
        if service:
            clauses.append("service = %s")
            params.append(service.lower())
        if environment:
            clauses.append("environment = %s")
            params.append(environment.lower())
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT project_id::text, service, environment, bucket_start::text,
                           bucket_size_seconds, total_events, error_events,
                           warning_events, fatal_events, latency_avg_ms, latency_p95_ms
                    FROM metric_rollups
                    WHERE {' AND '.join(clauses)}
                    ORDER BY bucket_start ASC
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def _filter_range(self, rollups: list[dict[str, Any]], range_value: str) -> list[dict[str, Any]]:
        hours = {"1h": 1, "6h": 6, "24h": 24}.get(range_value, 1)
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        return [
            bucket for bucket in rollups
            if datetime.fromisoformat(bucket["bucket_start"].replace("Z", "+00:00")) >= cutoff
        ]

    def _public_bucket(self, bucket: dict[str, Any]) -> dict[str, Any]:
        total = int(bucket.get("total_events", 0))
        errors = int(bucket.get("error_events", 0))
        fatal = int(bucket.get("fatal_events", 0))
        return {
            "bucketStart": bucket["bucket_start"],
            "service": bucket["service"],
            "environment": bucket["environment"],
            "totalEvents": total,
            "errorEvents": errors,
            "warningEvents": int(bucket.get("warning_events", 0)),
            "fatalEvents": fatal,
            "errorRate": calculate_error_rate(total, errors, fatal),
            "latencyAvgMs": _float_or_none(bucket.get("latency_avg_ms")),
            "latencyP95Ms": _float_or_none(bucket.get("latency_p95_ms")),
        }

    def _totals(self, rollups: list[dict[str, Any]]) -> dict[str, Any]:
        total_events = sum(int(bucket.get("total_events", 0)) for bucket in rollups)
        error_events = sum(int(bucket.get("error_events", 0)) for bucket in rollups)
        warning_events = sum(int(bucket.get("warning_events", 0)) for bucket in rollups)
        fatal_events = sum(int(bucket.get("fatal_events", 0)) for bucket in rollups)
        latency_values = [
            float(bucket["latency_p95_ms"]) for bucket in rollups if bucket.get("latency_p95_ms") is not None
        ]
        return {
            "totalEvents": total_events,
            "errorEvents": error_events,
            "warningEvents": warning_events,
            "fatalEvents": fatal_events,
            "latencyP95Ms": max(latency_values) if latency_values else None,
        }

    def _services(self, rollups: list[dict[str, Any]]) -> list[str]:
        return sorted({bucket["service"] for bucket in rollups})

    def _top_services(self, rollups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for bucket in rollups:
            service = bucket["service"]
            current = grouped.setdefault(
                service,
                {"service": service, "totalEvents": 0, "errorEvents": 0, "fatalEvents": 0},
            )
            current["totalEvents"] += int(bucket.get("total_events", 0))
            current["errorEvents"] += int(bucket.get("error_events", 0))
            current["fatalEvents"] += int(bucket.get("fatal_events", 0))
        for row in grouped.values():
            row["errorRate"] = calculate_error_rate(
                row["totalEvents"],
                row["errorEvents"],
                row["fatalEvents"],
            )
        return sorted(grouped.values(), key=lambda row: row["totalEvents"], reverse=True)


def _float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None
