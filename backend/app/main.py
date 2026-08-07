"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analytics,
    auth,
    build,
    chat,
    chat_sessions,
    health,
    indexing,
    knowledge_profile,
    knowledge_profile_generate,
    knowledge_understanding,
    llm,
    logs,
    metrics,
    models,
    overview,
    settings,
    sources,
    traces,
    understanding,
    users,
)
from app.core.config import ConfigError, get_config
from app.core.database import SessionLocal, bootstrap_data, verify_database
from app.core.logging import configure_logging, get_logger
from app.repositories.index_job_repository import IndexJobRepository

configure_logging()
logger = get_logger(__name__)
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Site Agent backend (env=%s)", config.app_env)
    if not config.jwt_secret_key:
        if config.is_production:
            logger.error(
                "JWT_SECRET_KEY is not set — set it in .env before production use"
            )
        else:
            logger.warning(
                "JWT_SECRET_KEY is not set — using insecure development default"
            )
    try:
        verify_database()
    except ConfigError as exc:
        logger.error("Database validation failed — refusing to start:\n%s", exc)
        raise
    bootstrap_data()
    db = SessionLocal()
    try:
        healed = IndexJobRepository(db).fail_stale_running()
        if healed:
            logger.info("Marked %d stale 'running' job(s) as failed", healed)
        from app.repositories.source_repository import SourceRepository

        repaired = SourceRepository(db).repair_error_sources_with_chunks()
        if repaired:
            logger.info(
                "Repaired %d source(s) stuck as error with existing chunks",
                repaired,
            )
        from app.repositories.settings_repository import SettingsRepository
        from app.services.model_warmup_service import ModelWarmupService
        from app.services.ollama_service import OllamaService

        settings = SettingsRepository(db).get_or_create()
        warmup_enabled = getattr(settings, "enable_llm_warmup", True) and config.ollama_warmup_enabled
        if warmup_enabled:
            eff_keep = (
                (getattr(settings, "llm_keep_alive", None) or "").strip()
                or config.ollama_keep_alive
                or "30m"
            )
            warmup_model = (
                config.ollama_warmup_model.strip()
                or settings.llm_model
            )
            import threading

            threading.Thread(
                target=ModelWarmupService.warmup,
                kwargs={
                    "ollama": OllamaService(timeout=float(settings.ollama_generation_timeout_seconds or 60)),
                    "model": warmup_model,
                    "keep_alive": eff_keep,
                    "enabled": True,
                },
                daemon=True,
                name="llm-warmup",
            ).start()
    finally:
        db.close()
    from app.services.analytics_aggregation_worker import analytics_aggregation_worker
    from app.services.cache_cleanup_worker import cache_cleanup_worker
    from app.services.executive.maintenance_cycle_invoker import (
        maintenance_cycle_invoker,
    )

    cache_cleanup_worker.start()
    analytics_aggregation_worker.start()
    maintenance_cycle_invoker.start()
    yield
    maintenance_cycle_invoker.stop()
    logger.info("Shutting down AI Site Agent backend")

app = FastAPI(
    title="AI Site Agent",
    description="Local website knowledge agent with grounded RAG over a local LLM.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(build.router)
app.include_router(metrics.router)
app.include_router(overview.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(settings.router)
app.include_router(sources.router)
app.include_router(indexing.router)
app.include_router(knowledge_profile.router)
app.include_router(knowledge_profile_generate.router)
app.include_router(chat.router)
app.include_router(chat_sessions.router)
app.include_router(logs.router)
app.include_router(models.router)
app.include_router(llm.router)
app.include_router(traces.router)
app.include_router(analytics.router)
app.include_router(understanding.router)
app.include_router(knowledge_understanding.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "ai-site-agent", "status": "ok"}
