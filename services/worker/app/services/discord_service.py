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


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class DiscordAlertService:
    def __init__(
        self,
        path: str | None = None,
        sender: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.path = Path(path or get_settings().local_alerts_path)
        self.sender = sender

    def handle_incident_update(
        self,
        incident: dict[str, Any],
        previous_severity: str | None,
    ) -> dict[str, Any] | None:
        alert_type = alert_type_for_incident(incident, previous_severity)
        if alert_type is None:
            return None
        return self.send_once(incident, alert_type)

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
            return self._dedupe_exists_postgres(incident_id, alert_type)
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
            return self._record_postgres(
                incident=incident,
                status=status,
                payload=payload,
                sent_at=sent_at,
                error_message=error_message,
            )
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

    def _dedupe_exists_postgres(self, incident_id: str, alert_type: str) -> bool:
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

    def _record_postgres(
        self,
        *,
        incident: dict[str, Any],
        status: str,
        payload: dict[str, Any],
        sent_at: str | None,
        error_message: str | None,
    ) -> dict[str, Any]:
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

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def _write(self, alerts: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(alerts, indent=2, sort_keys=True), encoding="utf-8")


def alert_type_for_incident(incident: dict[str, Any], previous_severity: str | None) -> str | None:
    severity = incident.get("severity", "")
    if SEVERITY_RANK.get(severity, 0) < SEVERITY_RANK["high"]:
        return None
    if previous_severity is None:
        return "opened"
    if (
        SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(previous_severity, 0)
        and severity == "critical"
    ):
        return "escalated"
    return None


def build_discord_payload(incident: dict[str, Any], alert_type: str) -> dict[str, Any]:
    title_prefix = {
        "opened": "Incident opened",
        "escalated": "Incident escalated",
        "resolved": "Incident resolved",
    }.get(alert_type, "Incident update")
    summary = _summary_text(incident)
    color = 0xDC2626 if incident.get("severity") == "critical" else 0xD97706
    if alert_type == "resolved":
        color = 0x059669
    fields = [
        {"name": "Severity", "value": str(incident.get("severity", "unknown")), "inline": True},
        {"name": "Service", "value": str(incident.get("service", "unknown")), "inline": True},
        {"name": "Environment", "value": str(incident.get("environment", "unknown")), "inline": True},
        {"name": "Status", "value": str(incident.get("status", "unknown")), "inline": True},
    ]
    dashboard_url = _dashboard_url(incident)
    if dashboard_url:
        fields.append({"name": "Dashboard", "value": dashboard_url, "inline": False})
    return {
        "alert_type": alert_type,
        "content": f"{title_prefix}: {incident.get('title', 'SignalForge incident')}",
        "embeds": [
            {
                "title": incident.get("title", "SignalForge incident"),
                "description": summary,
                "color": color,
                "fields": fields,
                "timestamp": _now(),
                "footer": {"text": "SignalForge"},
            }
        ],
    }


def _summary_text(incident: dict[str, Any]) -> str:
    payload = incident.get("ai_summary_payload")
    if isinstance(payload, dict) and payload.get("summary"):
        return str(payload["summary"])
    raw_summary = incident.get("ai_summary")
    if isinstance(raw_summary, str) and raw_summary.strip():
        try:
            parsed = json.loads(raw_summary)
            if isinstance(parsed, dict) and parsed.get("summary"):
                return str(parsed["summary"])
        except json.JSONDecodeError:
            return raw_summary[:500]
    return f"{incident.get('severity', 'Unknown').title()} incident in {incident.get('service', 'service')}."


def _dashboard_url(incident: dict[str, Any]) -> str | None:
    base = get_settings().dashboard_base_url.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/projects/{incident['project_id']}/incidents/{incident['id']}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
