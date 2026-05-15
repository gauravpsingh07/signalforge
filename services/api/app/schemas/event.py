import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings

EventLevel = Literal["debug", "info", "warn", "error", "fatal"]


class EventIngestRequest(BaseModel):
    eventId: str | None = Field(default=None, max_length=120)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    service: str = Field(min_length=2, max_length=80)
    environment: str = Field(default="production", min_length=2, max_length=80)
    level: EventLevel
    message: str = Field(min_length=1)
    statusCode: int | None = Field(default=None, ge=100, le=599)
    latencyMs: int | None = Field(default=None, ge=0)
    traceId: str | None = Field(default=None, max_length=200)
    requestId: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message_size(cls, value: str) -> str:
        max_length = get_settings().ingest_max_message_length
        if len(value) > max_length:
            raise ValueError(f"message must be {max_length} characters or fewer")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        size = len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"))
        max_size = get_settings().ingest_max_metadata_bytes
        if size > max_size:
            raise ValueError(f"metadata must be {max_size} bytes or fewer")
        return value


class BatchEventIngestRequest(BaseModel):
    events: list[EventIngestRequest] = Field(min_length=1)

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, value: list[EventIngestRequest]) -> list[EventIngestRequest]:
        max_size = get_settings().ingest_max_batch_size
        if len(value) > max_size:
            raise ValueError(f"batch must contain {max_size} events or fewer")
        return value


class EventAcceptedResponse(BaseModel):
    eventId: str
    jobId: str
    status: str = "accepted"


class BatchEventAcceptedResponse(BaseModel):
    acceptedCount: int
    jobIds: list[str]
    status: str = "accepted"
