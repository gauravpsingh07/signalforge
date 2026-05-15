import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.utils.fingerprints import fingerprint_hash, normalize_message


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    project_id: str
    api_key_prefix: str
    timestamp: str
    received_at: str
    service: str
    environment: str
    level: str
    message: str
    normalized_message: str
    fingerprint_hash: str
    status_code: int | None
    latency_ms: int | None
    trace_id: str | None
    request_id: str | None
    metadata: dict[str, Any]


def normalize_event_job(job: dict[str, Any]) -> NormalizedEvent:
    event = job.get("event")
    if not isinstance(event, dict):
        raise ValueError("job payload is missing event object")

    project_id = _required_string(job, "project_id")
    api_key_prefix = _required_string(job, "api_key_prefix")
    message = _required_string(event, "message")
    service = _required_string(event, "service").strip().lower()
    level = _required_string(event, "level").strip().lower()
    environment = str(event.get("environment") or "production").strip().lower()
    timestamp = _normalize_datetime(event.get("timestamp"))
    received_at = _normalize_datetime(job.get("received_at"))
    metadata = _sanitize_metadata(event.get("metadata", {}))
    normalized_message = normalize_message(message)
    status_code = event.get("statusCode")

    return NormalizedEvent(
        event_id=str(event.get("eventId") or uuid4()),
        project_id=project_id,
        api_key_prefix=api_key_prefix,
        timestamp=timestamp,
        received_at=received_at,
        service=service,
        environment=environment or "production",
        level=level,
        message=message.strip(),
        normalized_message=normalized_message,
        fingerprint_hash=fingerprint_hash(
            service=service,
            environment=environment or "production",
            level=level,
            status_code=status_code,
            normalized_message=normalized_message,
        ),
        status_code=status_code,
        latency_ms=event.get("latencyMs"),
        trace_id=event.get("traceId"),
        request_id=event.get("requestId"),
        metadata=metadata,
    )


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required string field: {key}")
    return value


def _normalize_datetime(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).isoformat()
        except ValueError as exc:
            raise ValueError(f"invalid datetime: {text}") from exc
    return datetime.now(UTC).isoformat()


def _sanitize_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata must be an object")

    encoded = json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
    if len(encoded) > get_settings().ingest_max_metadata_bytes:
        raise ValueError("metadata exceeds configured size limit")
    return value
