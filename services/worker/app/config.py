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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
