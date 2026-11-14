from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    All settings use the ``THESIUM_`` environment prefix. The defaults are
    development-safe: local Postgres, local bind address, no admin token.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="THESIUM_",
        extra="ignore",
    )

    app_name: str = "Thesium"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    bind_host: str = "127.0.0.1"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://thesium:thesium@localhost:5432/thesium"

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    admin_token: str | None = None
    secret_key: str | None = None

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()