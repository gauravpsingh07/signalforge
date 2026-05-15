from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SignalForge API"
    version: str = "0.0.1"
    allowed_origins: str = "http://localhost:5173"
    database_url: str = ""
    jwt_secret: str = ""
    api_key_pepper: str = ""
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    qstash_token: str = ""
    clickhouse_host: str = ""
    clickhouse_user: str = ""
    clickhouse_password: str = ""
    clickhouse_database: str = ""
    gemini_api_key: str = ""
    discord_webhook_url: str = ""
    ingest_rate_limit_per_minute: int = 60
    ingest_rate_limit_per_ip_minute: int = 120
    ingest_max_batch_size: int = 25
    ingest_max_message_length: int = 2000
    ingest_max_metadata_bytes: int = 8192
    local_queue_path: str = "../../tmp/signalforge-events.jsonl"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
