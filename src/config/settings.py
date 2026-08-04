"""
Application configuration.
All values are loaded from environment variables / .env file.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "granite3.3"

    # ── External APIs ─────────────────────────────────────────────────────
    openweather_api_key: str = ""
    aviationstack_api_key: str = ""
    sendgrid_api_key: str = ""

    # ── IBM Db2 ───────────────────────────────────────────────────────────
    db2_host: str = ""
    db2_port: int = 50000
    db2_database: str = "AIRLINE"
    db2_username: str = ""
    db2_password: str = ""
    db2_schema: str = "AIRLINE_KB"

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
