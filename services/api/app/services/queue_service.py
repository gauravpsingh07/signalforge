import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.event import EventIngestRequest
from app.services.metadata_store import ApiKeyRecord, MetadataStore, WorkerJobRecord, utc_now


class QueueService:
    def __init__(self, store: MetadataStore) -> None:
        self.store = store

    async def enqueue_event(
        self,
        api_key: ApiKeyRecord,
        event: EventIngestRequest,
    ) -> WorkerJobRecord:
        payload = {
            "project_id": api_key.project_id,
            "api_key_prefix": api_key.key_prefix,
            "received_at": utc_now(),
            "event": event.model_dump(mode="json"),
            "attempt": 0,
        }
        job = await self.store.create_worker_job(
            job_type="process_event",
            entity_id=api_key.project_id,
            payload=payload,
            max_attempts=3,
        )
        queued_payload = {"job_id": job.id, **payload}
        self._write_local_worker_job(job)
        await self._write_queue_payload(queued_payload)
        return job

    async def enqueue_batch(
        self,
        api_key: ApiKeyRecord,
        events: list[EventIngestRequest],
    ) -> list[WorkerJobRecord]:
        jobs = []
        for event in events:
            jobs.append(await self.enqueue_event(api_key, event))
        return jobs

    async def _write_queue_payload(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            await self._write_upstash_payload(payload)
            return
        self._write_jsonl_payload(payload)

    async def _write_upstash_payload(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        url = settings.upstash_redis_rest_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{url}/lpush/signalforge:jobs",
                headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
                json=json.dumps(payload),
            )

    def _write_jsonl_payload(self, payload: dict[str, Any]) -> None:
        path = Path(get_settings().local_queue_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(json.dumps(payload, default=str) + "\n")

    def _write_local_worker_job(self, job: WorkerJobRecord) -> None:
        if get_settings().database_url:
            return
        path = Path(get_settings().local_worker_jobs_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        jobs = json.loads(path.read_text(encoding="utf-8") or "{}") if path.exists() else {}
        jobs[job.id] = asdict(job)
        path.write_text(json.dumps(jobs, indent=2, sort_keys=True, default=str), encoding="utf-8")


def serialize_worker_job(job: WorkerJobRecord) -> dict[str, Any]:
    return asdict(job)
