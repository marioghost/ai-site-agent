"""Application configuration loaded from environment variables.

These are process-level / deployment settings. Agent behaviour settings
(models, thresholds, prompts, etc.) live in the database `settings` table and
are editable from the dashboard.

The application is PostgreSQL-only. ``DATABASE_URL`` is required and must use a
``postgresql`` driver (e.g. ``postgresql+psycopg``). There is no SQLite fallback.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when required deployment configuration is missing or invalid."""


class AppConfig(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    # PostgreSQL connection string. Required — no default, no SQLite fallback.
    # Example: postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent
    database_url: str = Field(default="", alias="DATABASE_URL")

    # SQLAlchemy connection pool tuning (PostgreSQL).
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, alias="DB_POOL_TIMEOUT_SECONDS")
    db_pool_recycle_seconds: int = Field(
        default=1800, alias="DB_POOL_RECYCLE_SECONDS"
    )
    db_pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")
    db_slow_query_ms: int = Field(default=500, alias="DB_SLOW_QUERY_MS")

    # Batch write defaults for workers.
    db_write_batch_size: int = Field(default=50, alias="DB_WRITE_BATCH_SIZE")
    indexing_db_batch_size: int = Field(default=50, alias="INDEXING_DB_BATCH_SIZE")
    source_intelligence_db_batch_size: int = Field(
        default=50, alias="SOURCE_INTELLIGENCE_DB_BATCH_SIZE"
    )

    # Throttled progress persistence for long-running jobs.
    progress_flush_interval_seconds: float = Field(
        default=3.0, alias="PROGRESS_FLUSH_INTERVAL_SECONDS"
    )
    progress_flush_every_items: int = Field(
        default=10, alias="PROGRESS_FLUSH_EVERY_ITEMS"
    )

    # Background cache cleanup.
    cache_cleanup_batch_size: int = Field(default=1000, alias="CACHE_CLEANUP_BATCH_SIZE")
    cache_cleanup_interval_minutes: int = Field(
        default=30, alias="CACHE_CLEANUP_INTERVAL_MINUTES"
    )

    # Analytics aggregation interval (minutes).
    analytics_aggregation_interval_minutes: int = Field(
        default=15, alias="ANALYTICS_AGGREGATION_INTERVAL_MINUTES"
    )

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL"
    )
    ollama_warmup_enabled: bool = Field(default=True, alias="OLLAMA_WARMUP_ENABLED")
    ollama_warmup_model: str = Field(default="", alias="OLLAMA_WARMUP_MODEL")
    ollama_keep_alive: str = Field(default="30m", alias="OLLAMA_KEEP_ALIVE")

    qdrant_host: str = Field(default="127.0.0.1", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")

    default_llm_model: str = Field(default="qwen2.5:3b", alias="DEFAULT_LLM_MODEL")
    default_embedding_model: str = Field(
        default="bge-m3", alias="DEFAULT_EMBEDDING_MODEL"
    )
    default_qdrant_collection: str = Field(
        default="site_knowledge", alias="DEFAULT_QDRANT_COLLECTION"
    )

    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_expire_minutes: int = Field(default=480, alias="JWT_EXPIRE_MINUTES")

    # Knowledge OS migration flags (RFC-100 Step 063 — default ON for Release 1.0).
    # Emergency rollback: set env to false/0/off and restart.
    knowledge_os_executive_enabled: bool = Field(
        default=True, alias="KNOWLEDGE_OS_EXECUTIVE_ENABLED"
    )
    reasoning_service_enabled: bool = Field(
        default=True, alias="REASONING_SERVICE_ENABLED"
    )
    evidence_assembly_enabled: bool = Field(
        default=True, alias="EVIDENCE_ASSEMBLY_ENABLED"
    )
    reasoning_speech_acts_enabled: bool = Field(
        default=True, alias="REASONING_SPEECH_ACTS_ENABLED"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def validate_database_url(self) -> None:
        """Fail fast unless DATABASE_URL is a PostgreSQL connection string.

        Raises ``ConfigError`` with an actionable message. Called at startup so
        the backend refuses to run without a valid PostgreSQL configuration.
        """
        url = (self.database_url or "").strip()
        if not url:
            raise ConfigError(
                "DATABASE_URL is not set. PostgreSQL is required.\n"
                "Set it in your .env, for example:\n"
                "  DATABASE_URL=postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent"
            )
        if not url.startswith("postgresql"):
            raise ConfigError(
                "DATABASE_URL must be a PostgreSQL URL (got scheme "
                f"{url.split('://', 1)[0]!r}). SQLite and other engines are not supported.\n"
                "Use: DATABASE_URL=postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent"
            )


@lru_cache
def get_config() -> AppConfig:
    """Return a cached singleton of the application config."""
    return AppConfig()
