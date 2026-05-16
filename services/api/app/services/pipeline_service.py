import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


JOB_STATUSES = ["queued", "processing", "completed", "failed", "dead_letter"]


class PipelineService:
    def health(self, allowed_project_ids: set[str] | None = None) -> dict[str, Any]:
        jobs = self._scope_jobs(self._list_all_jobs(), allowed_project_ids)
        counts = Counter(job.get("status", "unknown") for job in jobs)
        durations = [duration for job in jobs if (duration := duration_ms(job)) is not None]
        completed = [job for job in jobs if job.get("completed_at")]
        recent_cutoff = datetime.now(UTC) - timedelta(hours=1)
        completed_last_hour = [
            job for job in completed
            if parse_dt(job["completed_at"]) >= recent_cutoff
        ]
        return {
            "api": {
                "service": get_settings().app_name,
                "status": "healthy",
                "version": get_settings().version,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "queue": {
                "provider": self.queue_provider(),
                "depth": self.queue_depth(),
            },
            "jobs": {
                "counts": {status: counts.get(status, 0) for status in JOB_STATUSES},
                "failedOrDeadLetter": counts.get("failed", 0) + counts.get("dead_letter", 0),
                "completedLastHour": len(completed_last_hour),
                "averageProcessingLatencyMs": round(sum(durations) / len(durations), 2) if durations else None,
                "lastProcessedAt": max((job["completed_at"] for job in completed), default=None),
            },
            "ingestion": {
                "eventsAcceptedLastHour": len([
                    job for job in jobs
                    if job.get("job_type") == "process_event"
                    and job.get("created_at")
                    and parse_dt(job["created_at"]) >= recent_cutoff
                ]),
            },
            "alerts": {
                "failedDeliveries": self.alert_failure_count(allowed_project_ids),
            },
        }

    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
        allowed_project_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        jobs = self._scope_jobs(self._list_all_jobs(), allowed_project_ids)
        if status:
            jobs = [job for job in jobs if job.get("status") == status]
        if job_type:
            jobs = [job for job in jobs if job.get("job_type") == job_type]
        if start:
            start_dt = parse_dt(start)
            jobs = [job for job in jobs if parse_dt(job["created_at"]) >= start_dt]
        if end:
            end_dt = parse_dt(end)
            jobs = [job for job in jobs if parse_dt(job["created_at"]) <= end_dt]
        return [
            public_job(job)
            for job in sorted(jobs, key=lambda item: item.get("created_at", ""), reverse=True)[:limit]
        ]

    def retry_job(self, job_id: str, allowed_project_ids: set[str] | None = None) -> dict[str, Any] | None:
        if get_settings().database_url:
            return self._retry_postgres(job_id, allowed_project_ids)
        jobs = self._read_local_jobs()
        job = jobs.get(job_id)
        if not job or job.get("status") not in {"failed", "dead_letter"}:
            return None
        if allowed_project_ids is not None and job_project_id(job) not in allowed_project_ids:
            return None
        payload = job.get("payload")
        if not isinstance(payload, dict):
            return None
        queued_payload = {"job_id": job_id, **payload, "attempt": int(job.get("attempts", 0))}
        self._append_queue(queued_payload)
        job["status"] = "queued"
        job["error_message"] = None
        job["started_at"] = None
        job["completed_at"] = None
        jobs[job_id] = job
        self._write_local_jobs(jobs)
        return public_job(job)

    def queue_provider(self) -> str:
        settings = get_settings()
        if settings.qstash_token:
            return "qstash"
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            return "redis"
        return "local"

    def queue_depth(self) -> int | None:
        if self.queue_provider() != "local":
            return None
        path = Path(get_settings().local_queue_path)
        if not path.exists():
            return 0
        return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])

    def alert_failure_count(self, allowed_project_ids: set[str] | None = None) -> int:
        if get_settings().database_url:
            with psycopg.connect(get_settings().database_url) as conn:
                with conn.cursor() as cur:
                    if allowed_project_ids is None:
                        cur.execute("SELECT COUNT(*) FROM alerts WHERE status = 'failed'")
                    elif not allowed_project_ids:
                        return 0
                    else:
                        cur.execute(
                            "SELECT COUNT(*) FROM alerts WHERE status = 'failed' AND project_id::text = ANY(%s)",
                            (list(allowed_project_ids),),
                        )
                    return int(cur.fetchone()[0])
        path = Path(get_settings().local_alerts_path)
        if not path.exists():
            return 0
        alerts = json.loads(path.read_text(encoding="utf-8") or "[]")
        return sum(
            1
            for alert in alerts
            if alert.get("status") == "failed"
            and (allowed_project_ids is None or alert.get("project_id") in allowed_project_ids)
        )

    def _list_all_jobs(self) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._list_postgres_jobs()
        return list(self._read_local_jobs().values())

    def _read_local_jobs(self) -> dict[str, dict[str, Any]]:
        path = Path(get_settings().local_worker_jobs_path)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8") or "{}")

    def _write_local_jobs(self, jobs: dict[str, dict[str, Any]]) -> None:
        path = Path(get_settings().local_worker_jobs_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(jobs, indent=2, sort_keys=True), encoding="utf-8")

    def _append_queue(self, payload: dict[str, Any]) -> None:
        path = Path(get_settings().local_queue_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(json.dumps(payload, default=str) + "\n")

    def _list_postgres_jobs(self) -> list[dict[str, Any]]:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id::text, job_type, entity_id::text, status, attempts,
                           max_attempts, error_message, payload, created_at::text,
                           started_at::text, completed_at::text
                    FROM worker_jobs
                    ORDER BY created_at DESC
                    LIMIT 1000
                    """
                )
                return [dict(row) for row in cur.fetchall()]

    def _retry_postgres(self, job_id: str, allowed_project_ids: set[str] | None = None) -> dict[str, Any] | None:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id::text, job_type, entity_id::text, status, attempts,
                           max_attempts, error_message, payload, created_at::text,
                           started_at::text, completed_at::text
                    FROM worker_jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                job = cur.fetchone()
                if not job or job["status"] not in {"failed", "dead_letter"} or not job["payload"]:
                    return None
                if allowed_project_ids is not None and job_project_id(dict(job)) not in allowed_project_ids:
                    return None
                queued_payload = {"job_id": job_id, **job["payload"], "attempt": int(job["attempts"])}
                self._append_queue(queued_payload)
                cur.execute(
                    """
                    UPDATE worker_jobs
                    SET status = 'queued', error_message = NULL, started_at = NULL, completed_at = NULL
                    WHERE id = %s
                    RETURNING id::text, job_type, entity_id::text, status, attempts,
                              max_attempts, error_message, payload, created_at::text,
                              started_at::text, completed_at::text
                    """,
                    (job_id,),
                )
                return public_job(dict(cur.fetchone()))

    def _scope_jobs(
        self,
        jobs: list[dict[str, Any]],
        allowed_project_ids: set[str] | None,
    ) -> list[dict[str, Any]]:
        if allowed_project_ids is None:
            return jobs
        return [job for job in jobs if job_project_id(job) in allowed_project_ids]


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "job_type": job.get("job_type"),
        "entity_id": job.get("entity_id"),
        "status": job.get("status"),
        "attempts": int(job.get("attempts", 0)),
        "max_attempts": int(job.get("max_attempts", 0)),
        "error_message": job.get("error_message"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "processing_latency_ms": duration_ms(job),
        "has_payload": isinstance(job.get("payload"), dict),
    }


def job_project_id(job: dict[str, Any]) -> str | None:
    entity_id = job.get("entity_id")
    if entity_id:
        return str(entity_id)
    payload = job.get("payload")
    if isinstance(payload, dict) and payload.get("project_id"):
        return str(payload["project_id"])
    return None


def duration_ms(job: dict[str, Any]) -> float | None:
    if not job.get("started_at") or not job.get("completed_at"):
        return None
    return round((parse_dt(job["completed_at"]) - parse_dt(job["started_at"])).total_seconds() * 1000, 2)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
