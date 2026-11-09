from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://qeai:qeai@localhost:5432/quantaedge_ai"
    redis_url: str = "redis://localhost:6379/0"
    ollama_base_url: str = "http://127.0.0.1:11434"
    config_dir: Path = Path(__file__).resolve().parents[4] / "config"
    data_dir: Path = Path(__file__).resolve().parents[4] / "data"
    service_api_keys: str = "{}"
    api_request_timeout_seconds: int = Field(default=180, ge=10, le=900)

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

    @property
    def api_keys(self) -> dict[str, dict]:
        import json

        try:
            value = json.loads(self.service_api_keys)
        except json.JSONDecodeError as exc:
            raise ValueError("SERVICE_API_KEYS must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("SERVICE_API_KEYS must be a JSON object")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
