from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    service_name: str = "signalforge-worker"
    version: str = "0.0.1"
    worker_concurrency: int = 2
    max_job_attempts: int = 3
    database_url: str = ""
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    qstash_token: str = ""
    clickhouse_host: str = ""
    clickhouse_user: str = ""
    clickhouse_password: str = ""
    clickhouse_database: str = ""
    gemini_api_key: str = ""
    discord_webhook_url: str = ""
    local_queue_path: str = "../../tmp/signalforge-events.jsonl"
    local_event_store_path: str = "../../tmp/signalforge-processed-events.jsonl"
    local_worker_jobs_path: str = "../../tmp/signalforge-worker-jobs.json"
    local_fingerprints_path: str = "../../tmp/signalforge-fingerprints.json"
    local_metric_rollups_path: str = "../../tmp/signalforge-metric-rollups.json"
    local_anomalies_path: str = "../../tmp/signalforge-anomalies.json"
    ingest_max_metadata_bytes: int = 8192
    anomaly_min_sample_count: int = 5
    anomaly_repeated_fingerprint_threshold: int = 5
    anomaly_fatal_burst_threshold: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
