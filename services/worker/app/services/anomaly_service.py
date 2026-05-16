import json
import math
from dataclasses import dataclass, asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from app.config import get_settings
from app.services.event_normalizer import NormalizedEvent


@dataclass(frozen=True)
class AnomalyCandidate:
    project_id: str
    service: str
    environment: str
    anomaly_type: str
    severity: str
    score: float
    baseline_value: float | None
    observed_value: float
    window_start: str
    window_end: str
    fingerprint_hash: str | None = None
    metadata: dict[str, Any] | None = None


def z_score(observed: float, baseline_mean: float, baseline_stdev: float) -> float:
    if baseline_stdev == 0:
        return math.inf if observed > baseline_mean else 0.0
    return (observed - baseline_mean) / baseline_stdev


def error_rate(total_events: int, error_events: int, fatal_events: int = 0) -> float:
    if total_events <= 0:
        return 0.0
    return (error_events + fatal_events) / total_events


class AnomalyService:
    def __init__(
        self,
        rollups_path: str | None = None,
        fingerprints_path: str | None = None,
        anomalies_path: str | None = None,
    ) -> None:
        settings = get_settings()
        self.rollups_path = Path(rollups_path or settings.local_metric_rollups_path)
        self.fingerprints_path = Path(fingerprints_path or settings.local_fingerprints_path)
        self.anomalies_path = Path(anomalies_path or settings.local_anomalies_path)

    def detect_for_event(
        self,
        event: NormalizedEvent,
        fingerprint: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        candidates = self.build_candidates(event, fingerprint)
        created = []
        for candidate in candidates:
            anomaly = self.create_if_not_duplicate(candidate)
            if anomaly:
                created.append(anomaly)
        return created

    def build_candidates(
        self,
        event: NormalizedEvent,
        fingerprint: dict[str, Any] | None = None,
    ) -> list[AnomalyCandidate]:
        rollups = self._load_rollups(event.project_id, event.service, event.environment)
        window_start, window_end = five_minute_window(event.timestamp)
        current = aggregate_rollups(rollups, window_start, window_end)
        baseline_start = window_start - timedelta(minutes=60)
        baseline_end = window_start - timedelta(minutes=5)
        baseline = [
            bucket for bucket in rollups
            if baseline_start <= parse_dt(bucket["bucket_start"]) < baseline_end
        ]
        candidates: list[AnomalyCandidate] = []
        candidates.extend(self._error_rate_candidates(event, current, baseline, window_start, window_end))
        candidates.extend(self._latency_candidates(event, current, baseline, window_start, window_end))
        candidates.extend(self._fingerprint_candidates(event, fingerprint, window_start, window_end))
        return candidates

    def create_if_not_duplicate(self, candidate: AnomalyCandidate) -> dict[str, Any] | None:
        if get_settings().database_url:
            return self._create_postgres(candidate)
        anomalies = self._read_anomalies()
        for anomaly in anomalies:
            if (
                anomaly["project_id"] == candidate.project_id
                and anomaly["service"] == candidate.service
                and anomaly["environment"] == candidate.environment
                and anomaly["anomaly_type"] == candidate.anomaly_type
                and anomaly["window_start"] == candidate.window_start
                and anomaly.get("fingerprint_hash") == candidate.fingerprint_hash
                and anomaly["status"] == "open"
            ):
                return None
        anomaly = {
            "id": str(uuid4()),
            **asdict(candidate),
            "status": "open",
            "created_at": datetime.now(UTC).isoformat(),
        }
        anomalies.append(anomaly)
        self._write_anomalies(anomalies)
        return anomaly

    def _error_rate_candidates(
        self,
        event: NormalizedEvent,
        current: dict[str, Any],
        baseline: list[dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
    ) -> list[AnomalyCandidate]:
        settings = get_settings()
        candidates = []
        observed_total = int(current["total_events"])
        if observed_total < settings.anomaly_min_sample_count:
            return []

        current_error_rate = error_rate(
            observed_total,
            int(current["error_events"]),
            int(current["fatal_events"]),
        )
        baseline_rates = [
            error_rate(int(bucket.get("total_events", 0)), int(bucket.get("error_events", 0)), int(bucket.get("fatal_events", 0)))
            for bucket in baseline
            if int(bucket.get("total_events", 0)) > 0
        ]
        baseline_mean = mean(baseline_rates) if baseline_rates else 0.0
        baseline_stdev = pstdev(baseline_rates) if len(baseline_rates) > 1 else 0.0
        score = z_score(current_error_rate, baseline_mean, baseline_stdev)

        if current_error_rate > 0.50:
            candidates.append(self._candidate(event, "error_rate_spike", "critical", score, baseline_mean, current_error_rate, window_start, window_end))
        elif current_error_rate > 0.20 and score >= 3.0:
            candidates.append(self._candidate(event, "error_rate_spike", "high", score, baseline_mean, current_error_rate, window_start, window_end))

        if int(current["fatal_events"]) >= settings.anomaly_fatal_burst_threshold:
            candidates.append(
                self._candidate(
                    event,
                    "fatal_event_burst",
                    "critical",
                    float(current["fatal_events"]),
                    float(settings.anomaly_fatal_burst_threshold),
                    float(current["fatal_events"]),
                    window_start,
                    window_end,
                )
            )
        return candidates

    def _latency_candidates(
        self,
        event: NormalizedEvent,
        current: dict[str, Any],
        baseline: list[dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
    ) -> list[AnomalyCandidate]:
        if int(current["total_events"]) < get_settings().anomaly_min_sample_count:
            return []
        observed = current.get("latency_p95_ms")
        if observed is None:
            return []
        baseline_values = [
            float(bucket["latency_p95_ms"])
            for bucket in baseline
            if bucket.get("latency_p95_ms") is not None
        ]
        baseline_p95 = mean(baseline_values) if baseline_values else None
        if baseline_p95 is None or baseline_p95 <= 0:
            return []
        if float(observed) > baseline_p95 * 3 and float(observed) > 1000:
            return [
                self._candidate(
                    event,
                    "latency_spike",
                    "high",
                    float(observed) / baseline_p95,
                    baseline_p95,
                    float(observed),
                    window_start,
                    window_end,
                )
            ]
        return []

    def _fingerprint_candidates(
        self,
        event: NormalizedEvent,
        fingerprint: dict[str, Any] | None,
        window_start: datetime,
        window_end: datetime,
    ) -> list[AnomalyCandidate]:
        if event.level not in {"error", "fatal"}:
            return []
        if not fingerprint:
            return []
        occurrence_count = int(fingerprint.get("occurrence_count", 0))
        if occurrence_count < get_settings().anomaly_repeated_fingerprint_threshold:
            return []
        first_seen = parse_dt(fingerprint.get("first_seen_at", event.timestamp))
        if first_seen < window_start:
            return []
        return [
            self._candidate(
                event,
                "new_repeated_error",
                "high",
                float(occurrence_count),
                float(get_settings().anomaly_repeated_fingerprint_threshold),
                float(occurrence_count),
                window_start,
                window_end,
                fingerprint_hash=event.fingerprint_hash,
                metadata={"normalized_message": event.normalized_message},
            )
        ]

    def _candidate(
        self,
        event: NormalizedEvent,
        anomaly_type: str,
        severity: str,
        score: float,
        baseline_value: float | None,
        observed_value: float,
        window_start: datetime,
        window_end: datetime,
        fingerprint_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnomalyCandidate:
        return AnomalyCandidate(
            project_id=event.project_id,
            service=event.service,
            environment=event.environment,
            anomaly_type=anomaly_type,
            severity=severity,
            score=score if math.isfinite(score) else 999.0,
            baseline_value=baseline_value,
            observed_value=observed_value,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            fingerprint_hash=fingerprint_hash,
            metadata=metadata or {},
        )

    def _load_rollups(self, project_id: str, service: str, environment: str) -> list[dict[str, Any]]:
        if get_settings().database_url:
            return self._load_rollups_postgres(project_id, service, environment)
        if not self.rollups_path.exists():
            return []
        data = json.loads(self.rollups_path.read_text(encoding="utf-8") or "{}")
        return [
            bucket for bucket in data.values()
            if bucket.get("project_id") == project_id
            and bucket.get("service") == service
            and bucket.get("environment") == environment
        ]

    def _load_rollups_postgres(self, project_id: str, service: str, environment: str) -> list[dict[str, Any]]:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT project_id::text, service, environment, bucket_start::text,
                           bucket_size_seconds, total_events, error_events,
                           warning_events, fatal_events, latency_avg_ms, latency_p95_ms
                    FROM metric_rollups
                    WHERE project_id = %s AND service = %s AND environment = %s
                    """,
                    (project_id, service, environment),
                )
                cols = [desc.name for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _create_postgres(self, candidate: AnomalyCandidate) -> dict[str, Any] | None:
        with psycopg.connect(get_settings().database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM anomalies
                    WHERE project_id = %s AND service = %s AND environment = %s
                      AND anomaly_type = %s AND window_start = %s
                      AND COALESCE(fingerprint_hash, '') = COALESCE(%s, '')
                      AND status = 'open'
                    """,
                    (
                        candidate.project_id,
                        candidate.service,
                        candidate.environment,
                        candidate.anomaly_type,
                        candidate.window_start,
                        candidate.fingerprint_hash,
                    ),
                )
                if cur.fetchone():
                    return None
                anomaly_id = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO anomalies
                      (id, project_id, service, environment, anomaly_type, severity,
                       score, baseline_value, observed_value, window_start, window_end,
                       fingerprint_hash, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        anomaly_id,
                        candidate.project_id,
                        candidate.service,
                        candidate.environment,
                        candidate.anomaly_type,
                        candidate.severity,
                        candidate.score,
                        candidate.baseline_value,
                        candidate.observed_value,
                        candidate.window_start,
                        candidate.window_end,
                        candidate.fingerprint_hash,
                        Jsonb(candidate.metadata or {}),
                    ),
                )
        return {"id": anomaly_id, **asdict(candidate), "status": "open"}

    def _read_anomalies(self) -> list[dict[str, Any]]:
        if not self.anomalies_path.exists():
            return []
        return json.loads(self.anomalies_path.read_text(encoding="utf-8") or "[]")

    def _write_anomalies(self, anomalies: list[dict[str, Any]]) -> None:
        self.anomalies_path.parent.mkdir(parents=True, exist_ok=True)
        self.anomalies_path.write_text(json.dumps(anomalies, indent=2, sort_keys=True), encoding="utf-8")


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def five_minute_window(timestamp: str) -> tuple[datetime, datetime]:
    parsed = parse_dt(timestamp)
    epoch = int(parsed.timestamp())
    window_epoch = epoch - (epoch % 300)
    start = datetime.fromtimestamp(window_epoch, UTC)
    return start, start + timedelta(minutes=5)


def aggregate_rollups(
    rollups: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    selected = [
        bucket for bucket in rollups
        if window_start <= parse_dt(bucket["bucket_start"]) < window_end
    ]
    latency_values = [
        float(bucket["latency_p95_ms"])
        for bucket in selected
        if bucket.get("latency_p95_ms") is not None
    ]
    return {
        "total_events": sum(int(bucket.get("total_events", 0)) for bucket in selected),
        "error_events": sum(int(bucket.get("error_events", 0)) for bucket in selected),
        "warning_events": sum(int(bucket.get("warning_events", 0)) for bucket in selected),
        "fatal_events": sum(int(bucket.get("fatal_events", 0)) for bucket in selected),
        "latency_p95_ms": max(latency_values) if latency_values else None,
    }
