import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_metadata_store
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    store = InMemoryMetadataStore()
    settings = get_settings()
    settings.database_url = ""
    settings.max_request_body_bytes = 128
    settings.local_queue_path = str(tmp_path / "queue.jsonl")
    settings.local_worker_jobs_path = str(tmp_path / "jobs.json")
    app.dependency_overrides[get_metadata_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    settings.max_request_body_bytes = 1_048_576


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


def test_request_size_guard_returns_consistent_json_error(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        content="x" * 512,
        headers={"Content-Type": "application/json", "Content-Length": "512"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_project_collection_routes_reject_unbounded_limits(client: TestClient) -> None:
    token = register(client, "limits@example.com")
    project = create_project(client, token)

    response = client.get(
        f"/projects/{project['id']}/events?limit=1000",
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_demo_scripts_support_dry_run() -> None:
    scripts = [
        "send_demo_events.py",
        "generate_error_spike.py",
        "generate_latency_spike.py",
        "generate_recovery_events.py",
        "reset_demo_project.py",
    ]
    for script in scripts:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / script),
                "--api-url",
                "http://localhost:8000",
                "--project-key",
                "sf_demo_test_key",
                "--dry-run",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "dry-run" in result.stdout
