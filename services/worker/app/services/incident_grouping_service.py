import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class IncidentGroupingService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_incidents_path)

    def handle_created_anomalies(self, anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        incidents = []
        for anomaly in anomalies:
            incidents.append(self.group_anomaly(anomaly))
        self.auto_resolve()
        return incidents

    def group_anomaly(self, anomaly: dict[str, Any]) -> dict[str, Any]:
        if get_settings().database_url:
            return self._group_postgres(anomaly)
        data = self._read()
        now = _incident_time(anomaly)
        existing = self._find_related_local(data, anomaly)
        if existing:
            incident = self._attach_local(data, existing, anomaly, now)
        else:
            incident = self._create_local(data, anomaly, now)
        self._write(data)
        return incident

    def auto_resolve(self, current_time: datetime | None = None) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._auto_resolve_postgres(current_time)
        data = self._read()
        now = current_time or datetime.now(UTC)
        cooldown = timedelta(minutes=get_settings().incident_auto_resolve_cooldown_minutes)
        resolved = []
        for incident in data["incidents"]:
            if incident.get("status") != "open":
                continue
            updated_at = _parse_dt(incident["updated_at"])
            if now - updated_at >= cooldown:
                incident["status"] = "resolved"
                incident["resolved_at"] = now.isoformat()
                incident["updated_at"] = now.isoformat()
                resolved.append(incident)
        if resolved:
            self._write(data)
        return resolved

    def _find_related_local(self, data: dict[str, list[dict[str, Any]]], anomaly: dict[str, Any]) -> dict[str, Any] | None:
        anomaly_time = _parse_dt(anomaly.get("created_at") or anomaly["window_end"])
        cutoff = anomaly_time - timedelta(minutes=get_settings().incident_grouping_window_minutes)
        for incident in data["incidents"]:
            if (
                incident.get("status") == "open"
                and incident.get("project_id") == anomaly.get("project_id")
                and incident.get("service") == anomaly.get("service")
                and incident.get("environment") == anomaly.get("environment")
                and _parse_dt(incident["updated_at"]) >= cutoff
                and self._is_related_local(data, incident["id"], anomaly)
            ):
                return incident
        return None

    def _is_related_local(
        self,
        data: dict[str, list[dict[str, Any]]],
        incident_id: str,
        anomaly: dict[str, Any],
    ) -> bool:
        related_events = [event for event in data["incident_events"] if event["incident_id"] == incident_id]
        if not related_events:
            return True
        fingerprint_hash = anomaly.get("fingerprint_hash")
        anomaly_type = anomaly.get("anomaly_type")
        for event in related_events:
            if fingerprint_hash and event.get("fingerprint_hash") == fingerprint_hash:
                return True
            if event.get("anomaly_type") == anomaly_type:
                return True
        return False

    def _attach_local(
        self,
        data: dict[str, list[dict[str, Any]]],
        incident: dict[str, Any],
        anomaly: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        incident["severity"] = max_severity(incident["severity"], anomaly["severity"])
        incident["updated_at"] = now
        if not any(
            event.get("incident_id") == incident["id"] and event.get("anomaly_id") == anomaly["id"]
            for event in data["incident_events"]
        ):
            data["incident_events"].append(_incident_event(incident["id"], anomaly, now))
        return incident

    def _create_local(
        self,
        data: dict[str, list[dict[str, Any]]],
        anomaly: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        incident = {
            "id": str(uuid4()),
            "project_id": anomaly["project_id"],
            "title": title_for_anomaly(anomaly),
            "service": anomaly["service"],
            "environment": anomaly["environment"],
            "severity": anomaly["severity"],
            "status": "open",
            "ai_summary": None,
            "likely_cause": None,
            "recommended_actions": None,
            "started_at": anomaly.get("window_start") or now,
            "resolved_at": None,
            "created_at": now,
            "updated_at": now,
        }
        data["incidents"].append(incident)
        data["incident_events"].append(_incident_event(incident["id"], anomaly, now))
        return incident

    def _group_postgres(self, anomaly: dict[str, Any]) -> dict[str, Any]:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                incident = self._find_related_postgres(cur, anomaly)
                if incident:
                    incident_id = incident["id"]
                    cur.execute(
                        """
                        UPDATE incidents
                        SET severity = %s, updated_at = now()
                        WHERE id = %s
                        RETURNING id::text, project_id::text, title, service, environment,
                                  severity, status, ai_summary, likely_cause,
                                  recommended_actions, started_at::text, resolved_at::text,
                                  created_at::text, updated_at::text
                        """,
                        (max_severity(incident["severity"], anomaly["severity"]), incident_id),
                    )
                    incident = dict(cur.fetchone())
                else:
                    incident_id = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO incidents
                          (id, project_id, title, service, environment, severity, started_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id::text, project_id::text, title, service, environment,
                                  severity, status, ai_summary, likely_cause,
                                  recommended_actions, started_at::text, resolved_at::text,
                                  created_at::text, updated_at::text
                        """,
                        (
                            incident_id,
                            anomaly["project_id"],
                            title_for_anomaly(anomaly),
                            anomaly["service"],
                            anomaly["environment"],
                            anomaly["severity"],
                            anomaly["window_start"],
                        ),
                    )
                    incident = dict(cur.fetchone())
                self._attach_postgres(cur, incident_id, anomaly)
                return incident

    def _find_related_postgres(self, cur, anomaly: dict[str, Any]) -> dict[str, Any] | None:
        cutoff = _parse_dt(anomaly.get("created_at") or anomaly["window_end"]) - timedelta(
            minutes=get_settings().incident_grouping_window_minutes
        )
        cur.execute(
            """
            SELECT id::text, project_id::text, title, service, environment, severity,
                   status, ai_summary, likely_cause, recommended_actions,
                   started_at::text, resolved_at::text, created_at::text, updated_at::text
            FROM incidents
            WHERE project_id = %s AND service = %s AND environment = %s
              AND status = 'open' AND updated_at >= %s
            ORDER BY updated_at DESC
            """,
            (anomaly["project_id"], anomaly["service"], anomaly["environment"], cutoff.isoformat()),
        )
        for incident in cur.fetchall():
            if self._is_related_postgres(cur, incident["id"], anomaly):
                return dict(incident)
        return None

    def _is_related_postgres(self, cur, incident_id: str, anomaly: dict[str, Any]) -> bool:
        cur.execute(
            """
            SELECT a.anomaly_type, a.fingerprint_hash
            FROM incident_events ie
            JOIN anomalies a ON a.id = ie.anomaly_id
            WHERE ie.incident_id = %s
            """,
            (incident_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return True
        fingerprint_hash = anomaly.get("fingerprint_hash")
        return any(
            (fingerprint_hash and row["fingerprint_hash"] == fingerprint_hash)
            or row["anomaly_type"] == anomaly["anomaly_type"]
            for row in rows
        )

    def _attach_postgres(self, cur, incident_id: str, anomaly: dict[str, Any]) -> None:
        cur.execute(
            "SELECT 1 FROM incident_events WHERE incident_id = %s AND anomaly_id = %s",
            (incident_id, anomaly["id"]),
        )
        if cur.fetchone():
            return
        cur.execute(
            """
            INSERT INTO incident_events (id, incident_id, anomaly_id, fingerprint_id)
            VALUES (
              %s,
              %s,
              %s,
              (
                SELECT id FROM event_fingerprints
                WHERE project_id = %s AND fingerprint_hash = %s
                LIMIT 1
              )
            )
            """,
            (
                str(uuid4()),
                incident_id,
                anomaly["id"],
                anomaly["project_id"],
                anomaly.get("fingerprint_hash"),
            ),
        )

    def _auto_resolve_postgres(self, current_time: datetime | None = None) -> list[dict[str, Any]]:
        now = current_time or datetime.now(UTC)
        cutoff = now - timedelta(minutes=get_settings().incident_auto_resolve_cooldown_minutes)
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE incidents
                    SET status = 'resolved', resolved_at = %s, updated_at = %s
                    WHERE status = 'open' AND updated_at <= %s
                    RETURNING id::text, project_id::text, title, service, environment,
                              severity, status, ai_summary, likely_cause,
                              recommended_actions, started_at::text, resolved_at::text,
                              created_at::text, updated_at::text
                    """,
                    (now.isoformat(), now.isoformat(), cutoff.isoformat()),
                )
                return [dict(row) for row in cur.fetchall()]

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {"incidents": [], "incident_events": []}
        data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        return {
            "incidents": data.get("incidents", []),
            "incident_events": data.get("incident_events", []),
        }

    def _write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def title_for_anomaly(anomaly: dict[str, Any]) -> str:
    service = anomaly.get("service", "service")
    anomaly_type = anomaly.get("anomaly_type")
    if anomaly_type == "error_rate_spike":
        return f"High error rate in {service}"
    if anomaly_type == "latency_spike":
        return f"Latency spike in {service}"
    if anomaly_type == "new_repeated_error":
        return f"Repeated errors in {service}"
    if anomaly_type == "fatal_event_burst":
        return f"Fatal event burst in {service}"
    return f"Incident in {service}"


def max_severity(current: str, candidate: str) -> str:
    return candidate if SEVERITY_RANK.get(candidate, 0) > SEVERITY_RANK.get(current, 0) else current


def _incident_event(incident_id: str, anomaly: dict[str, Any], now: str) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "incident_id": incident_id,
        "anomaly_id": anomaly["id"],
        "fingerprint_id": None,
        "fingerprint_hash": anomaly.get("fingerprint_hash"),
        "anomaly_type": anomaly.get("anomaly_type"),
        "event_external_id": None,
        "created_at": now,
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _incident_time(anomaly: dict[str, Any]) -> str:
    return _parse_dt(anomaly.get("created_at") or anomaly.get("window_end") or _now()).isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
