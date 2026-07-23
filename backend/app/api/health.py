"""Health endpoint reporting app, database, Ollama and Qdrant status."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import current_db_revision, get_db, pool_diagnostics
from app.core.slow_query import recent_slow_queries
from app.repositories.settings_repository import SettingsRepository
from app.schemas.common import DatabaseHealth, HealthComponent, HealthResponse
from app.services.health_cache import health_cache

router = APIRouter(tags=["health"])


def _database_health(db: Session) -> DatabaseHealth:
    """Probe PostgreSQL: connectivity, query latency, migration, pool stats."""
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
    except Exception as exc:  # noqa: BLE001
        return DatabaseHealth(
            status="error", detail=f"PostgreSQL unreachable: {exc}"
        )

    revision = current_db_revision()
    pool_info = pool_diagnostics()
    pool_status: str | None = None
    if pool_info:
        pool_status = (
            f"{pool_info.get('checked_out', 0)}/{pool_info.get('size', 0)} in use, "
            f"{pool_info.get('overflow', 0)} overflow"
        )

    detail = f"PostgreSQL · rev {revision or 'unknown'} · {latency_ms} ms"
    if pool_status:
        detail += f" · pool {pool_status}"
    return DatabaseHealth(
        status="ok",
        detail=detail,
        engine="PostgreSQL",
        migration_version=revision,
        latency_ms=latency_ms,
        pool=pool_status,
        pool_checked_out=int(pool_info.get("checked_out", 0)) if pool_info else None,
        pool_size=int(pool_info.get("size", 0)) if pool_info else None,
        pool_overflow=int(pool_info.get("overflow", 0)) if pool_info else None,
        slow_queries=recent_slow_queries(5),
    )


@router.get("/api/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = SettingsRepository(db).get_or_create()

    ollama_ok, ollama_detail = health_cache.ollama()
    qdrant_ok, qdrant_detail = health_cache.qdrant(settings.qdrant_collection)

    return HealthResponse(
        app=HealthComponent(status="ok", detail="Backend running"),
        database=_database_health(db),
        ollama=HealthComponent(
            status="ok" if ollama_ok else "error", detail=ollama_detail
        ),
        qdrant=HealthComponent(
            status="ok" if qdrant_ok else "error", detail=qdrant_detail
        ),
    )
