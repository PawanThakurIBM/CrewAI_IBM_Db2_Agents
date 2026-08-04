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
    db2_database: str = ""
    db2_username: str = ""
    db2_password: str = ""
    db2_protocol: str = "TCPIP"
    db2_schema: str = "AIRLINE_KB"

    # ── Haystack / Knowledge pipeline (Pawan) ─────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_top_k: int = 10
    reranker_top_k: int = 5
    data_dir: str = "src/data"

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def db2_dsn(self) -> str:
        """IBM Db2 DSN connection string for ibm_db.connect()."""
        return (
            f"DATABASE={self.db2_database};"
            f"HOSTNAME={self.db2_host};"
            f"PORT={self.db2_port};"
            f"PROTOCOL={self.db2_protocol};"
            f"UID={self.db2_username};"
            f"PWD={self.db2_password};"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
