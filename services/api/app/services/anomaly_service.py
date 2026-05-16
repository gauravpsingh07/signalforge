import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class AnomalyQueryService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_anomalies_path)

    def list_anomalies(
        self,
        *,
        project_id: str,
        service: str | None = None,
        environment: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        anomaly_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._list_postgres(
                project_id=project_id,
                service=service,
                environment=environment,
                severity=severity,
                status=status,
                anomaly_type=anomaly_type,
                start=start,
                end=end,
                limit=limit,
            )
        anomalies = [
            anomaly for anomaly in self._read()
            if anomaly.get("project_id") == project_id
        ]
        if service:
            anomalies = [item for item in anomalies if item.get("service") == service.lower()]
        if environment:
            anomalies = [item for item in anomalies if item.get("environment") == environment.lower()]
        if severity:
            anomalies = [item for item in anomalies if item.get("severity") == severity]
        if status:
            anomalies = [item for item in anomalies if item.get("status") == status]
        if anomaly_type:
            anomalies = [item for item in anomalies if item.get("anomaly_type") == anomaly_type]
        if start:
            anomalies = [item for item in anomalies if item.get("window_start", "") >= start]
        if end:
            anomalies = [item for item in anomalies if item.get("window_end", "") <= end]
        return sorted(anomalies, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def _list_postgres(
        self,
        *,
        project_id: str,
        service: str | None,
        environment: str | None,
        severity: str | None,
        status: str | None,
        anomaly_type: str | None,
        start: str | None,
        end: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["project_id = %s"]
        params: list[Any] = [project_id]
        for column, value in {
            "service": service,
            "environment": environment,
            "severity": severity,
            "status": status,
            "anomaly_type": anomaly_type,
        }.items():
            if value:
                clauses.append(f"{column} = %s")
                params.append(value.lower() if column in {"service", "environment"} else value)
        if start:
            clauses.append("window_start >= %s")
            params.append(start)
        if end:
            clauses.append("window_end <= %s")
            params.append(end)
        params.append(limit)

        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT id::text, project_id::text, service, environment,
                           anomaly_type, severity, score::float, baseline_value::float,
                           observed_value::float, window_start::text, window_end::text,
                           status, fingerprint_hash, metadata, created_at::text
                    FROM anomalies
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]
