import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.services.event_store_service import EventStoreService


class IncidentQueryService:
    def __init__(
        self,
        incidents_path: str | None = None,
        anomalies_path: str | None = None,
    ) -> None:
        settings = get_settings()
        self.incidents_path = Path(incidents_path or settings.local_incidents_path)
        self.anomalies_path = Path(anomalies_path or settings.local_anomalies_path)

    def list_incidents(
        self,
        *,
        project_id: str,
        status: str | None = None,
        severity: str | None = None,
        service: str | None = None,
        environment: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._list_postgres(
                project_id=project_id,
                status=status,
                severity=severity,
                service=service,
                environment=environment,
                limit=limit,
            )

        data = self._read_incidents()
        incidents = [incident for incident in data["incidents"] if incident.get("project_id") == project_id]
        if status:
            incidents = [incident for incident in incidents if incident.get("status") == status]
        if severity:
            incidents = [incident for incident in incidents if incident.get("severity") == severity]
        if service:
            incidents = [incident for incident in incidents if incident.get("service") == service.lower()]
        if environment:
            incidents = [incident for incident in incidents if incident.get("environment") == environment.lower()]
        return [
            self._with_counts(incident, data["incident_events"])
            for incident in sorted(incidents, key=lambda item: item.get("updated_at", ""), reverse=True)[:limit]
        ]

    def get_incident_detail(self, incident_id: str) -> dict[str, Any] | None:
        if get_settings().database_url:
            return self._detail_postgres(incident_id)

        data = self._read_incidents()
        incident = next((item for item in data["incidents"] if item.get("id") == incident_id), None)
        if incident is None:
            return None
        incident_events = [event for event in data["incident_events"] if event.get("incident_id") == incident_id]
        anomaly_ids = {event.get("anomaly_id") for event in incident_events}
        anomalies = [item for item in self._read_anomalies() if item.get("id") in anomaly_ids]
        fingerprints = sorted(
            {
                value
                for value in [event.get("fingerprint_hash") for event in incident_events]
                + [anomaly.get("fingerprint_hash") for anomaly in anomalies]
                if value
            }
        )
        event_samples = EventStoreService().list_events(
            project_id=incident["project_id"],
            service=incident["service"],
            environment=incident["environment"],
            limit=10,
        )
        return {
            "incident": self._with_counts(incident, data["incident_events"]),
            "related_anomalies": sorted(anomalies, key=lambda item: item.get("created_at", "")),
            "related_fingerprints": fingerprints,
            "event_samples": event_samples,
            "timeline": self._timeline(incident, anomalies),
        }

    def resolve_incident(self, incident_id: str) -> dict[str, Any] | None:
        if get_settings().database_url:
            return self._resolve_postgres(incident_id)

        data = self._read_incidents()
        incident = next((item for item in data["incidents"] if item.get("id") == incident_id), None)
        if incident is None:
            return None
        now = datetime.now(UTC).isoformat()
        incident["status"] = "resolved"
        incident["resolved_at"] = incident.get("resolved_at") or now
        incident["updated_at"] = now
        self._write_incidents(data)
        return self._with_counts(incident, data["incident_events"])

    def count_open(self, project_id: str) -> int:
        return len(self.list_incidents(project_id=project_id, status="open", limit=200))

    def _with_counts(self, incident: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        return normalize_incident({
            **incident,
            "related_anomaly_count": sum(1 for event in events if event.get("incident_id") == incident.get("id")),
        })

    def _timeline(self, incident: dict[str, Any], anomalies: list[dict[str, Any]]) -> list[dict[str, str]]:
        rows = [
            {
                "time": incident["started_at"],
                "label": "Incident opened",
                "description": incident["title"],
            }
        ]
        rows.extend(
            {
                "time": anomaly.get("created_at", anomaly.get("window_start", "")),
                "label": anomaly.get("anomaly_type", "anomaly").replace("_", " "),
                "description": f"{anomaly.get('severity')} severity in {anomaly.get('service')}",
            }
            for anomaly in anomalies
        )
        if incident.get("resolved_at"):
            rows.append(
                {
                    "time": incident["resolved_at"],
                    "label": "Incident resolved",
                    "description": "Resolved manually or by cooldown.",
                }
            )
        return sorted(rows, key=lambda item: item["time"])

    def _read_incidents(self) -> dict[str, list[dict[str, Any]]]:
        if not self.incidents_path.exists():
            return {"incidents": [], "incident_events": []}
        data = json.loads(self.incidents_path.read_text(encoding="utf-8") or "{}")
        return {
            "incidents": data.get("incidents", []),
            "incident_events": data.get("incident_events", []),
        }

    def _write_incidents(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.incidents_path.parent.mkdir(parents=True, exist_ok=True)
        self.incidents_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _read_anomalies(self) -> list[dict[str, Any]]:
        if not self.anomalies_path.exists():
            return []
        return json.loads(self.anomalies_path.read_text(encoding="utf-8") or "[]")

    def _list_postgres(
        self,
        *,
        project_id: str,
        status: str | None,
        severity: str | None,
        service: str | None,
        environment: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["i.project_id = %s"]
        params: list[Any] = [project_id]
        for column, value in {
            "status": status,
            "severity": severity,
            "service": service,
            "environment": environment,
        }.items():
            if value:
                clauses.append(f"i.{column} = %s")
                params.append(value.lower() if column in {"service", "environment"} else value)
        params.append(limit)
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT i.id::text, i.project_id::text, i.title, i.service,
                           i.environment, i.severity, i.status, i.ai_summary,
                           i.likely_cause, i.recommended_actions,
                           i.started_at::text, i.resolved_at::text,
                           i.created_at::text, i.updated_at::text,
                           COUNT(ie.id)::int AS related_anomaly_count
                    FROM incidents i
                    LEFT JOIN incident_events ie ON ie.incident_id = i.id
                    WHERE {' AND '.join(clauses)}
                    GROUP BY i.id
                    ORDER BY i.updated_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [normalize_incident(dict(row)) for row in cur.fetchall()]

    def _detail_postgres(self, incident_id: str) -> dict[str, Any] | None:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT i.id::text, i.project_id::text, i.title, i.service,
                           i.environment, i.severity, i.status, i.ai_summary,
                           i.likely_cause, i.recommended_actions,
                           i.started_at::text, i.resolved_at::text,
                           i.created_at::text, i.updated_at::text,
                           COUNT(ie.id)::int AS related_anomaly_count
                    FROM incidents i
                    LEFT JOIN incident_events ie ON ie.incident_id = i.id
                    WHERE i.id = %s
                    GROUP BY i.id
                    """,
                    (incident_id,),
                )
                incident = cur.fetchone()
                if incident is None:
                    return None
                cur.execute(
                    """
                    SELECT a.id::text, a.project_id::text, a.service, a.environment,
                           a.anomaly_type, a.severity, a.score::float,
                           a.baseline_value::float, a.observed_value::float,
                           a.window_start::text, a.window_end::text, a.status,
                           a.fingerprint_hash, a.metadata, a.created_at::text
                    FROM incident_events ie
                    JOIN anomalies a ON a.id = ie.anomaly_id
                    WHERE ie.incident_id = %s
                    ORDER BY a.created_at ASC
                    """,
                    (incident_id,),
                )
                anomalies = [dict(row) for row in cur.fetchall()]
        incident_dict = normalize_incident(dict(incident))
        event_samples = EventStoreService().list_events(
            project_id=incident_dict["project_id"],
            service=incident_dict["service"],
            environment=incident_dict["environment"],
            limit=10,
        )
        return {
            "incident": incident_dict,
            "related_anomalies": anomalies,
            "related_fingerprints": sorted({item["fingerprint_hash"] for item in anomalies if item["fingerprint_hash"]}),
            "event_samples": event_samples,
            "timeline": self._timeline(incident_dict, anomalies),
        }

    def _resolve_postgres(self, incident_id: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE incidents
                    SET status = 'resolved',
                        resolved_at = COALESCE(resolved_at, %s),
                        updated_at = %s
                    WHERE id = %s
                    RETURNING id::text, project_id::text, title, service,
                              environment, severity, status, ai_summary,
                              likely_cause, recommended_actions,
                              started_at::text, resolved_at::text,
                              created_at::text, updated_at::text
                    """,
                    (now, now, incident_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                incident = dict(row)
                cur.execute("SELECT COUNT(*) FROM incident_events WHERE incident_id = %s", (incident_id,))
                incident["related_anomaly_count"] = cur.fetchone()["count"]
                return normalize_incident(incident)


def normalize_incident(incident: dict[str, Any]) -> dict[str, Any]:
    return {
        **incident,
        "ai_summary_payload": parse_summary_payload(incident.get("ai_summary")),
    }


def parse_summary_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {
            "summary": value,
            "affectedService": "",
            "impact": "",
            "likelyCause": "",
            "timeline": [],
            "recommendedActions": [],
            "confidence": "unknown",
            "source": "legacy",
        }
    return payload if isinstance(payload, dict) else None
