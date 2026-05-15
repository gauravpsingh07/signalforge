import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings
from app.services.event_normalizer import NormalizedEvent


class EventStoreService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_event_store_path)

    async def store_event(self, event: NormalizedEvent) -> bool:
        if get_settings().database_url:
            return self._store_postgres(event)

        if self._exists(event.project_id, event.event_id):
            return False

        if get_settings().clickhouse_host:
            try:
                await self._insert_clickhouse(event)
            except Exception:
                # Keep the local store as the reliable demo fallback if external analytics is unavailable.
                pass

        self._append_local(event)
        return True

    def list_events(
        self,
        *,
        project_id: str,
        service: str | None = None,
        environment: str | None = None,
        level: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
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
        return sorted(events, key=lambda event: event.get("timestamp", ""), reverse=True)[:limit]

    def _exists(self, project_id: str, event_id: str) -> bool:
        return any(
            event.get("project_id") == project_id and event.get("event_id") == event_id
            for event in self._read_all()
        )

    def _append_local(self, event: NormalizedEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as event_file:
            event_file.write(json.dumps(asdict(event), default=str) + "\n")

    def _store_postgres(self, event: NormalizedEvent) -> bool:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM events_metadata
                    WHERE project_id = %s AND event_id = %s
                    """,
                    (event.project_id, event.event_id),
                )
                if cur.fetchone():
                    return False
                cur.execute(
                    """
                    INSERT INTO events_metadata
                      (project_id, event_id, api_key_prefix, timestamp, received_at, service,
                       environment, level, message, normalized_message, fingerprint_hash,
                       status_code, latency_ms, trace_id, request_id, metadata)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.project_id,
                        event.event_id,
                        event.api_key_prefix,
                        event.timestamp,
                        event.received_at,
                        event.service,
                        event.environment,
                        event.level,
                        event.message,
                        event.normalized_message,
                        event.fingerprint_hash,
                        event.status_code,
                        event.latency_ms,
                        event.trace_id,
                        event.request_id,
                        Jsonb(event.metadata),
                    ),
                )
                return True

    def _read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    async def _insert_clickhouse(self, event: NormalizedEvent) -> None:
        settings = get_settings()
        payload = asdict(event)
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                settings.clickhouse_host,
                auth=(settings.clickhouse_user, settings.clickhouse_password),
                json=payload,
            )
