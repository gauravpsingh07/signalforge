import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class EventStoreService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_event_store_path)

    def list_events(
        self,
        *,
        project_id: str,
        service: str | None = None,
        environment: str | None = None,
        level: str | None = None,
        search: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._list_postgres(
                project_id=project_id,
                service=service,
                environment=environment,
                level=level,
                search=search,
                start=start,
                end=end,
                limit=limit,
            )

        events = [event for event in self._read_all() if event.get("project_id") == project_id]
        if service:
            events = [event for event in events if event.get("service") == service.lower()]
        if environment:
            events = [event for event in events if event.get("environment") == environment.lower()]
        if level:
            events = [event for event in events if event.get("level") == level.lower()]
        if search:
            query = search.lower()
            events = [event for event in events if query in event.get("message", "").lower()]
        if start:
            events = [event for event in events if event.get("timestamp", "") >= start]
        if end:
            events = [event for event in events if event.get("timestamp", "") <= end]

        return sorted(events, key=lambda event: event.get("timestamp", ""), reverse=True)[:limit]

    def _read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _list_postgres(
        self,
        *,
        project_id: str,
        service: str | None,
        environment: str | None,
        level: str | None,
        search: str | None,
        start: str | None,
        end: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["project_id = %s"]
        params: list[Any] = [project_id]
        if service:
            clauses.append("service = %s")
            params.append(service.lower())
        if environment:
            clauses.append("environment = %s")
            params.append(environment.lower())
        if level:
            clauses.append("level = %s")
            params.append(level.lower())
        if search:
            clauses.append("message ILIKE %s")
            params.append(f"%{search}%")
        if start:
            clauses.append("timestamp >= %s")
            params.append(start)
        if end:
            clauses.append("timestamp <= %s")
            params.append(end)
        params.append(limit)

        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT event_id, project_id::text, api_key_prefix, timestamp::text,
                           received_at::text, service, environment, level, message,
                           normalized_message, fingerprint_hash, status_code, latency_ms,
                           trace_id, request_id, metadata
                    FROM events_metadata
                    WHERE {' AND '.join(clauses)}
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]
