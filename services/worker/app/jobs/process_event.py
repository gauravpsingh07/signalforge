from typing import Any

from app.config import get_settings
from app.services.anomaly_service import AnomalyService
from app.services.event_normalizer import normalize_event_job
from app.services.event_store_service import EventStoreService
from app.services.fingerprint_store_service import FingerprintStoreService
from app.services.job_status_service import LocalJobStatusService
from app.services.metric_rollup_service import MetricRollupService
from app.services.queue_service import QueueConsumer


class EventJobProcessor:
    def __init__(
        self,
        queue: QueueConsumer | None = None,
        event_store: EventStoreService | None = None,
        fingerprint_store: FingerprintStoreService | None = None,
        metric_rollups: MetricRollupService | None = None,
        anomaly_service: AnomalyService | None = None,
        job_status: LocalJobStatusService | None = None,
    ) -> None:
        self.queue = queue or QueueConsumer()
        self.event_store = event_store or EventStoreService()
        self.fingerprint_store = fingerprint_store or FingerprintStoreService()
        self.metric_rollups = metric_rollups or MetricRollupService()
        self.anomaly_service = anomaly_service or AnomalyService()
        self.job_status = job_status or LocalJobStatusService()

    async def process_next(self) -> dict[str, Any]:
        job = await self.queue.pop()
        if job is None:
            return {"processed": False, "reason": "queue_empty"}
        return await self.process_job(job)

    async def process_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("job_id") or "")
        attempts = int(job.get("attempt", 0)) + 1
        max_attempts = int(job.get("max_attempts") or get_settings().max_job_attempts)
        if not job_id:
            raise ValueError("job is missing job_id")

        self.job_status.mark(job_id, "processing", attempts)
        try:
            event = normalize_event_job(job)
            inserted = await self.event_store.store_event(event)
            if inserted:
                fingerprint = self.fingerprint_store.update(event)
                self.metric_rollups.update_for_event(event)
                self.anomaly_service.detect_for_event(event, fingerprint)
            self.job_status.mark(job_id, "completed", attempts)
            return {
                "processed": True,
                "job_id": job_id,
                "status": "completed",
                "event_id": event.event_id,
                "inserted": inserted,
            }
        except Exception as exc:
            status = "dead_letter" if attempts >= max_attempts else "failed"
            self.job_status.mark(job_id, status, attempts, str(exc))
            if status == "failed":
                job["attempt"] = attempts
                job["max_attempts"] = max_attempts
                self.queue.requeue(job)
            return {
                "processed": False,
                "job_id": job_id,
                "status": status,
                "attempts": attempts,
                "error": str(exc),
            }
