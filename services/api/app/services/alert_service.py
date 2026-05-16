import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings


class AlertService:
    def __init__(
        self,
        path: str | None = None,
        sender: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.path = Path(path or get_settings().local_alerts_path)
        self.sender = sender

    def list_alerts(
        self,
        *,
        project_id: str,
        incident_id: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._list_postgres(
                project_id=project_id,
                incident_id=incident_id,
                status=status,
                channel=channel,
                limit=limit,
            )
        alerts = [alert for alert in self._read() if alert.get("project_id") == project_id]
        if incident_id:
            alerts = [alert for alert in alerts if alert.get("incident_id") == incident_id]
        if status:
            alerts = [alert for alert in alerts if alert.get("status") == status]
        if channel:
            alerts = [alert for alert in alerts if alert.get("channel") == channel]
        return sorted(alerts, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]

    def discord_configured(self) -> bool:
        return bool(get_settings().discord_webhook_url)

    def handle_incident_resolved(self, incident: dict[str, Any]) -> dict[str, Any] | None:
        if incident.get("status") != "resolved":
            return None
        return self.send_once(incident, "resolved")

    def send_once(self, incident: dict[str, Any], alert_type: str) -> dict[str, Any] | None:
        if self._dedupe_exists(incident["id"], alert_type):
            return None
        payload = build_discord_payload(incident, alert_type)
        status = "skipped"
        error_message = None
        sent_at = None
        webhook_url = get_settings().discord_webhook_url
        if webhook_url:
            try:
                self._send(webhook_url, payload)
                status = "sent"
                sent_at = _now()
            except Exception as exc:
                status = "failed"
                error_message = str(exc)
        else:
            error_message = "DISCORD_WEBHOOK_URL is not configured"
        return self._record_alert(
            incident=incident,
            status=status,
            payload=payload,
            sent_at=sent_at,
            error_message=error_message,
        )

    def _send(self, webhook_url: str, payload: dict[str, Any]) -> None:
        if self.sender:
            self.sender(webhook_url, payload)
            return
        with httpx.Client(timeout=8.0) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()

    def _dedupe_exists(self, incident_id: str, alert_type: str) -> bool:
        if get_settings().database_url:
            with psycopg.connect(get_settings().database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM alerts
                        WHERE incident_id = %s
                          AND channel = 'discord'
                          AND payload->>'alert_type' = %s
                        """,
                        (incident_id, alert_type),
                    )
                    return cur.fetchone() is not None
        return any(
            alert.get("incident_id") == incident_id
            and alert.get("channel") == "discord"
            and alert.get("payload", {}).get("alert_type") == alert_type
            for alert in self._read()
        )

    def _record_alert(
        self,
        *,
        incident: dict[str, Any],
        status: str,
        payload: dict[str, Any],
        sent_at: str | None,
        error_message: str | None,
    ) -> dict[str, Any]:
        if get_settings().database_url:
            alert_id = str(uuid4())
            with psycopg.connect(get_settings().database_url) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO alerts
                          (id, project_id, incident_id, channel, status, payload, sent_at, error_message)
                        VALUES (%s, %s, %s, 'discord', %s, %s, %s, %s)
                        RETURNING id::text, project_id::text, incident_id::text, channel,
                                  status, payload, sent_at::text, error_message, created_at::text
                        """,
                        (
                            alert_id,
                            incident["project_id"],
                            incident["id"],
                            status,
                            Jsonb(payload),
                            sent_at,
                            error_message,
                        ),
                    )
                    return dict(cur.fetchone())
        alerts = self._read()
        alert = {
            "id": str(uuid4()),
            "project_id": incident["project_id"],
            "incident_id": incident["id"],
            "channel": "discord",
            "status": status,
            "payload": payload,
            "sent_at": sent_at,
            "error_message": error_message,
            "created_at": _now(),
        }
        alerts.append(alert)
        self._write(alerts)
        return alert

    def _list_postgres(
        self,
        *,
        project_id: str,
        incident_id: str | None,
        status: str | None,
        channel: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["project_id = %s"]
        params: list[Any] = [project_id]
        if incident_id:
            clauses.append("incident_id = %s")
            params.append(incident_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        if channel:
            clauses.append("channel = %s")
            params.append(channel)
        params.append(limit)
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT id::text, project_id::text, incident_id::text, channel,
                           status, payload, sent_at::text, error_message, created_at::text
                    FROM alerts
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def _write(self, alerts: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(alerts, indent=2, sort_keys=True), encoding="utf-8")


def build_discord_payload(incident: dict[str, Any], alert_type: str) -> dict[str, Any]:
    return {
        "alert_type": alert_type,
        "content": f"Incident {alert_type}: {incident.get('title', 'SignalForge incident')}",
        "embeds": [
            {
                "title": incident.get("title", "SignalForge incident"),
                "description": incident.get("ai_summary_payload", {}).get("summary")
                if isinstance(incident.get("ai_summary_payload"), dict)
                else f"{incident.get('severity', 'Unknown').title()} incident in {incident.get('service', 'service')}.",
                "fields": [
                    {"name": "Severity", "value": str(incident.get("severity", "unknown")), "inline": True},
                    {"name": "Service", "value": str(incident.get("service", "unknown")), "inline": True},
                    {"name": "Environment", "value": str(incident.get("environment", "unknown")), "inline": True},
                    {"name": "Status", "value": str(incident.get("status", "unknown")), "inline": True},
                ],
                "timestamp": _now(),
                "footer": {"text": "SignalForge"},
            }
        ],
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()
