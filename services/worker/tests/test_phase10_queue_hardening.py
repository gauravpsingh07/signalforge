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

    QueueConsumer().requeue({"job_id": "job_retry", "attempt": 1})

    lines = Path(settings.local_queue_path).read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == {"job_id": "job_retry", "attempt": 1}
