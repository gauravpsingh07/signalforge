import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_metadata_store
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    store = InMemoryMetadataStore()
    settings = get_settings()
    settings.database_url = ""
    settings.local_queue_path = str(tmp_path / "queue.jsonl")
    settings.local_worker_jobs_path = str(tmp_path / "jobs.json")
    settings.local_alerts_path = str(tmp_path / "alerts.json")
    app.dependency_overrides[get_metadata_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_project(client: TestClient, token: str) -> dict:
    response = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Checkout Service Demo"},
    )
    assert response.status_code == 201
    return response.json()


def write_jobs(project_id: str, other_project_id: str = "other_project") -> None:
    settings = get_settings()
    Path(settings.local_queue_path).write_text('{"job_id":"queued_job"}\n', encoding="utf-8")
    Path(settings.local_worker_jobs_path).write_text(
        json.dumps(
            {
                "queued_job": job("queued_job", project_id, "queued"),
                "processing_job": job("processing_job", project_id, "processing", started_at="2026-05-15T15:59:00+00:00"),
                "completed_job": job(
                    "completed_job",
                    project_id,
                    "completed",
                    started_at="2026-05-15T16:00:00+00:00",
                    completed_at="2026-05-15T16:00:02+00:00",
                ),
                "failed_job": job(
                    "failed_job",
                    project_id,
                    "failed",
                    attempts=2,
                    error_message="message field required",
                    started_at="2026-05-15T16:01:00+00:00",
                    completed_at="2026-05-15T16:01:01+00:00",
                ),
                "dead_job": job(
                    "dead_job",
                    project_id,
                    "dead_letter",
                    attempts=3,
                    error_message="max attempts reached",
                    completed_at="2026-05-15T16:02:00+00:00",
                ),
                "other_job": job("other_job", other_project_id, "failed"),
            }
        ),
        encoding="utf-8",
    )
    Path(settings.local_alerts_path).write_text(
        json.dumps(
            [
                {"id": "alert_1", "project_id": project_id, "status": "failed"},
                {"id": "alert_2", "project_id": other_project_id, "status": "failed"},
            ]
        ),
        encoding="utf-8",
    )


def job(
    job_id: str,
    project_id: str,
    status: str,
    attempts: int = 0,
    error_message: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict:
    return {
        "id": job_id,
        "job_type": "process_event",
        "entity_id": project_id,
        "status": status,
        "attempts": attempts,
        "max_attempts": 3,
        "error_message": error_message,
        "payload": {
            "project_id": project_id,
            "api_key_prefix": "sf_demo_test",
            "received_at": "2026-05-15T16:00:00+00:00",
            "event": {
                "eventId": f"evt_{job_id}",
                "timestamp": "2026-05-15T16:00:00Z",
                "service": "checkout-api",
                "environment": "production",
                "level": "error",
                "message": "checkout failed",
            },
        },
        "created_at": "2026-05-15T16:00:00+00:00",
        "started_at": started_at,
        "completed_at": completed_at,
    }


def test_pipeline_health_returns_counts_and_latency(client: TestClient) -> None:
    token = register(client, "pipeline@example.com")
    project = create_project(client, token)
    write_jobs(project["id"])

    response = client.get("/pipeline-health", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["api"]["status"] == "healthy"
    assert body["queue"]["provider"] == "local"
    assert body["queue"]["depth"] == 1
    assert body["jobs"]["counts"]["queued"] == 1
    assert body["jobs"]["counts"]["failed"] == 1
    assert body["jobs"]["counts"]["dead_letter"] == 1
    assert body["jobs"]["failedOrDeadLetter"] == 2
    assert body["jobs"]["averageProcessingLatencyMs"] == 1500.0
    assert body["alerts"]["failedDeliveries"] == 1


def test_pipeline_jobs_filters_failed_jobs(client: TestClient) -> None:
    token = register(client, "pipeline-jobs@example.com")
    project = create_project(client, token)
    write_jobs(project["id"])

    response = client.get("/pipeline/jobs?status=failed", headers=auth_headers(token))

    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert [job["id"] for job in jobs] == ["failed_job"]
    assert jobs[0]["error_message"] == "message field required"
    assert jobs[0]["has_payload"] is True


def test_retry_failed_job_requeues_payload(client: TestClient) -> None:
    token = register(client, "pipeline-retry@example.com")
    project = create_project(client, token)
    write_jobs(project["id"])

    response = client.post("/pipeline/jobs/failed_job/retry", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "queued"
    jobs = json.loads(Path(get_settings().local_worker_jobs_path).read_text(encoding="utf-8"))
    assert jobs["failed_job"]["status"] == "queued"
    assert jobs["failed_job"]["error_message"] is None
    queue_lines = Path(get_settings().local_queue_path).read_text(encoding="utf-8").splitlines()
    assert len(queue_lines) == 2
    assert json.loads(queue_lines[-1])["job_id"] == "failed_job"


def test_pipeline_health_requires_auth(client: TestClient) -> None:
    response = client.get("/pipeline-health")

    assert response.status_code == 401
