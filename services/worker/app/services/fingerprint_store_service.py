import json
from pathlib import Path

import psycopg

from app.config import get_settings
from app.services.event_normalizer import NormalizedEvent


class FingerprintStoreService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().local_fingerprints_path)

    def update(self, event: NormalizedEvent) -> dict:
        if get_settings().database_url:
            return self._update_postgres(event)

        fingerprints = self._read()
        current = fingerprints.get(event.fingerprint_hash)
        if current is None:
            current = {
                "project_id": event.project_id,
                "service": event.service,
                "environment": event.environment,
                "level": event.level,
                "status_code": event.status_code,
                "fingerprint_hash": event.fingerprint_hash,
                "normalized_message": event.normalized_message,
                "first_seen_at": event.timestamp,
                "last_seen_at": event.timestamp,
                "occurrence_count": 0,
            }
        current["last_seen_at"] = event.timestamp
        current["occurrence_count"] += 1
        fingerprints[event.fingerprint_hash] = current
        self._write(fingerprints)
        return current

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _write(self, fingerprints: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(fingerprints, indent=2, sort_keys=True), encoding="utf-8")

    def _update_postgres(self, event: NormalizedEvent) -> dict:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO event_fingerprints
                      (project_id, service, environment, level, status_code,
                       fingerprint_hash, normalized_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, fingerprint_hash)
                    DO UPDATE SET
                      last_seen_at = now(),
                      occurrence_count = event_fingerprints.occurrence_count + 1
                    """,
                    (
                        event.project_id,
                        event.service,
                        event.environment,
                        event.level,
                        event.status_code,
                        event.fingerprint_hash,
                        event.normalized_message,
                    ),
                )
        return {
            "project_id": event.project_id,
            "fingerprint_hash": event.fingerprint_hash,
            "normalized_message": event.normalized_message,
        }
