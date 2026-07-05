import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.services.queue_service import QueueConsumer


def test_local_queue_consumes_fifo_and_preserves_remaining_jobs(tmp_path: Path) -> None:
    settings = get_settings()
    settings.database_url = ""
    settings.upstash_redis_rest_url = ""
    settings.upstash_redis_rest_token = ""
    settings.local_queue_path = str(tmp_path / "queue.jsonl")
    queue_path = Path(settings.local_queue_path)
    queue_path.write_text(
        "\n".join(
            [
                json.dumps({"job_id": "job_1", "attempt": 0}),
                json.dumps({"job_id": "job_2", "attempt": 0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = asyncio.run(QueueConsumer().pop())

    assert first == {"job_id": "job_1", "attempt": 0}
    remaining = queue_path.read_text(encoding="utf-8").splitlines()
    assert len(remaining) == 1
    assert json.loads(remaining[0])["job_id"] == "job_2"


def test_local_queue_requeue_appends_failed_job(tmp_path: Path) -> None:
    settings = get_settings()
    settings.database_url = ""
    settings.upstash_redis_rest_url = ""
    settings.upstash_redis_rest_token = ""
    settings.local_queue_path = str(tmp_path / "queue.jsonl")

    asyncio.run(QueueConsumer().requeue({"job_id": "job_retry", "attempt": 1}))

    lines = Path(settings.local_queue_path).read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == {"job_id": "job_retry", "attempt": 1}


def test_requeue_pushes_to_upstash_when_configured(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    settings.database_url = ""
    settings.local_queue_path = str(tmp_path / "queue.jsonl")
    settings.upstash_redis_rest_url = "https://example.upstash.io"
    settings.upstash_redis_rest_token = "test-token"
    pushed: list[dict] = []

    async def fake_push(self, payload: dict) -> None:
        pushed.append(payload)

    monkeypatch.setattr(QueueConsumer, "_push_upstash", fake_push)
    try:
        asyncio.run(QueueConsumer().requeue({"job_id": "job_retry", "attempt": 2}))
    finally:
        settings.upstash_redis_rest_url = ""
        settings.upstash_redis_rest_token = ""

    assert pushed == [{"job_id": "job_retry", "attempt": 2}]
    assert not Path(settings.local_queue_path).exists()


def test_upstash_pop_tolerates_double_encoded_payloads(monkeypatch) -> None:
    settings = get_settings()
    settings.database_url = ""
    settings.upstash_redis_rest_url = "https://example.upstash.io"
    settings.upstash_redis_rest_token = "test-token"
    payload = {"job_id": "job_1", "attempt": 0}

    class FakeResponse:
        def __init__(self, result: str) -> None:
            self._result = result

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"result": self._result}

    class FakeClient:
        def __init__(self, result: str) -> None:
            self._result = result

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse(self._result)

    import app.services.queue_service as queue_module

    try:
        for stored in (json.dumps(payload), json.dumps(json.dumps(payload))):
            monkeypatch.setattr(
                queue_module.httpx,
                "AsyncClient",
                lambda timeout, stored=stored: FakeClient(stored),
            )
            popped = asyncio.run(QueueConsumer().pop())
            assert popped == payload
    finally:
        settings.upstash_redis_rest_url = ""
        settings.upstash_redis_rest_token = ""
