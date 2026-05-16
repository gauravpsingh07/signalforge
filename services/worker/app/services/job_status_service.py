import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from app.config import get_settings


class LocalJobStatusService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_worker_jobs_path)

    def mark(self, job_id: str, status: str, attempts: int, error_message: str | None = None) -> None:
        if get_settings().database_url:
            self._mark_postgres(job_id, status, attempts, error_message)
            return
        jobs = self._read()
        current = jobs.get(job_id, {})
        now = datetime.now(UTC).isoformat()
        current.update(
            {
                "id": job_id,
                "status": status,
                "attempts": attempts,
                "error_message": error_message,
                "created_at": current.get("created_at") or now,
            }
        )
        if status == "processing":
            current["started_at"] = current.get("started_at") or now
            current["completed_at"] = None
        elif status in {"completed", "failed", "dead_letter"}:
            current["completed_at"] = now
        jobs[job_id] = current
        self._write(jobs)

    def _mark_postgres(
        self,
        job_id: str,
        status: str,
        attempts: int,
        error_message: str | None,
    ) -> None:
        if status == "processing":
            timestamp_sql = "started_at = COALESCE(started_at, now()), completed_at = NULL"
        elif status in {"completed", "failed", "dead_letter"}:
            timestamp_sql = "completed_at = now()"
        else:
            timestamp_sql = "completed_at = completed_at"

        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE worker_jobs
                    SET status = %s,
                        attempts = %s,
                        error_message = %s,
                        {timestamp_sql}
                    WHERE id = %s
                    """,
                    (status, attempts, error_message, job_id),
                )

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self._read().get(job_id)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _write(self, jobs: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(jobs, indent=2, sort_keys=True), encoding="utf-8")
