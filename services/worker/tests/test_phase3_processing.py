import json
import asyncio
from pathlib import Path

import pytest

from app.config import get_settings
from app.jobs.process_event import EventJobProcessor
from app.services.event_store_service import EventStoreService
from app.services.fingerprint_store_service import FingerprintStoreService
from app.services.job_status_service import LocalJobStatusService
from app.services.queue_service import QueueConsumer
from app.utils.fingerprints import fingerprint_hash, normalize_message


@pytest.fixture()
def paths(tmp_path: Path) -> dict[str, Path]:
    settings = get_settings()
    values = {
        "queue": tmp_path / "queue.jsonl",
        "events": tmp_path / "events.jsonl",
        "jobs": tmp_path / "jobs.json",
        "fingerprints": tmp_path / "fingerprints.json",
    }
    settings.local_queue_path = str(values["queue"])
    settings.local_event_store_path = str(values["events"])
    settings.local_worker_jobs_path = str(values["jobs"])
    settings.local_fingerprints_path = str(values["fingerprints"])
    settings.max_job_attempts = 2
    return values


def queued_job(event_id: str = "evt_1", message: str = "Stripe checkout timeout for request req_123 after 2380ms") -> dict:
    return {
        "job_id": f"job_{event_id}",
        "project_id": "project_123",
        "api_key_prefix": "sf_demo_test",
        "received_at": "2026-05-15T15:45:01+00:00",
        "attempt": 0,
        "max_attempts": 2,
        "event": {
            "eventId": event_id,
            "timestamp": "2026-05-15T15:45:00Z",
            "service": "Payment-API",
            "environment": "Production",
            "level": "ERROR",
            "message": message,
            "statusCode": 504,
            "latencyMs": 2380,
            "traceId": "trace_abc123",
            "requestId": "req_123",
            "metadata": {"route": "/checkout"},
        },
    }


def write_queue(path: Path, *jobs: dict) -> None:
    path.write_text("\n".join(json.dumps(job) for job in jobs) + "\n", encoding="utf-8")


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_message_normalization_handles_uuid_request_ids_and_numbers() -> None:
    message = "Stripe timeout for request req_456 uuid 123e4567-e89b-12d3-a456-426614174000 after 2510ms"

    normalized = normalize_message(message)

    assert "req_<id>" in normalized
    assert "<uuid>" in normalized
    assert "<number>" in normalized
    assert "2510" not in normalized


def test_fingerprint_stable_for_repeated_timeout_messages() -> None:
    first = normalize_message("Stripe checkout timeout for request req_123 after 2380ms")
    second = normalize_message("Stripe checkout timeout for request req_456 after 2510ms")

    first_hash = fingerprint_hash(
        service="payment-api",
        environment="production",
        level="error",
        status_code=504,
        normalized_message=first,
    )
    second_hash = fingerprint_hash(
        service="payment-api",
        environment="production",
        level="error",
        status_code=504,
        normalized_message=second,
    )

    assert first == second
    assert first_hash == second_hash


def test_worker_processes_queued_event_successfully(paths: dict[str, Path]) -> None:
    write_queue(paths["queue"], queued_job())
    processor = EventJobProcessor()

    result = asyncio.run(processor.process_next())

    assert result["status"] == "completed"
    events = read_events(paths["events"])
    assert len(events) == 1
    assert events[0]["service"] == "payment-api"
    assert events[0]["environment"] == "production"
    assert events[0]["fingerprint_hash"]


def test_failed_job_increments_attempts(paths: dict[str, Path]) -> None:
    bad_job = queued_job()
    bad_job["event"].pop("message")
    write_queue(paths["queue"], bad_job)

    result = asyncio.run(EventJobProcessor().process_next())

    assert result["status"] == "failed"
    assert result["attempts"] == 1
    status = LocalJobStatusService().get(bad_job["job_id"])
    assert status is not None
    assert status["attempts"] == 1


def test_job_moves_to_dead_letter_after_max_attempts(paths: dict[str, Path]) -> None:
    bad_job = queued_job()
    bad_job["max_attempts"] = 1
    bad_job["event"].pop("message")
    write_queue(paths["queue"], bad_job)

    result = asyncio.run(EventJobProcessor().process_next())

    assert result["status"] == "dead_letter"
    status = LocalJobStatusService().get(bad_job["job_id"])
    assert status is not None
    assert status["status"] == "dead_letter"


def test_duplicate_event_id_does_not_duplicate_records(paths: dict[str, Path]) -> None:
    write_queue(paths["queue"], queued_job("evt_duplicate"), queued_job("evt_duplicate"))
    processor = EventJobProcessor(
        queue=QueueConsumer(),
        event_store=EventStoreService(),
        fingerprint_store=FingerprintStoreService(),
        job_status=LocalJobStatusService(),
    )

    asyncio.run(processor.process_next())
    asyncio.run(processor.process_next())

    events = read_events(paths["events"])
    assert len(events) == 1
