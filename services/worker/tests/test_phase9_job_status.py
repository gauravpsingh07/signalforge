from pathlib import Path

from app.config import get_settings
from app.services.job_status_service import LocalJobStatusService


def test_local_job_status_records_processing_and_completion_timestamps(tmp_path: Path) -> None:
    settings = get_settings()
    settings.database_url = ""
    settings.local_worker_jobs_path = str(tmp_path / "jobs.json")
    service = LocalJobStatusService()

    service.mark("job_1", "processing", 1)
    processing = service.get("job_1")
    assert processing is not None
    assert processing["status"] == "processing"
    assert processing["started_at"] is not None
    assert processing["completed_at"] is None

    service.mark("job_1", "completed", 1)
    completed = service.get("job_1")
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["started_at"] == processing["started_at"]
    assert completed["completed_at"] is not None


def test_local_job_status_preserves_payload_for_retry_visibility(tmp_path: Path) -> None:
    settings = get_settings()
    settings.database_url = ""
    settings.local_worker_jobs_path = str(tmp_path / "jobs.json")
    service = LocalJobStatusService()
    service._write(
        {
            "job_1": {
                "id": "job_1",
                "job_type": "process_event",
                "entity_id": "project_1",
                "payload": {"project_id": "project_1", "event": {"eventId": "evt_1"}},
                "created_at": "2026-05-15T16:00:00+00:00",
            }
        }
    )

    service.mark("job_1", "dead_letter", 3, "message field required")

    status = service.get("job_1")
    assert status is not None
    assert status["payload"]["project_id"] == "project_1"
    assert status["error_message"] == "message field required"
    assert status["completed_at"] is not None
