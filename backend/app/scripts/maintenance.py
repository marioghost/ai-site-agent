"""Maintenance tasks for deployment scripts (caches, Qdrant, DB, reindex).

Run from the backend directory with the project venv:

    python -m app.scripts.maintenance clear-caches
    python -m app.scripts.maintenance clear-qdrant --main --answer-cache
    python -m app.scripts.maintenance reset-db
    python -m app.scripts.maintenance trigger-reindex
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.core.alembic_config import upgrade_to_head
from app.core.database import (
    SessionLocal,
    Base,
    current_db_revision,
    engine,
)
from app.core.logging import configure_logging, get_logger
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.source_repository import SourceRepository
from app.services.answer_cache_service import (
    AnswerCacheService,
    answer_cache_collection_name,
)
from app.services.indexing_worker_service import _Overrides, indexing_worker
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.lexical_index_service import LexicalIndexService
from app.services.qdrant_service import QdrantService
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.retrieval_cache_service import RetrievalCacheService

logger = get_logger(__name__)


def cmd_clear_retrieval_cache() -> int:
    with SessionLocal() as db:
        rows = CacheInvalidationService(db).invalidate_retrieval_cache("cli_clear")
    print(f"OK: cleared retrieval cache ({rows} rows)")
    return 0


def cmd_clear_answer_cache() -> int:
    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        CacheInvalidationService(db, settings).invalidate_answer_cache("cli_clear")
    print("OK: cleared answer cache")
    return 0


def cmd_clear_caches() -> int:
    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        retrieval_rows = CacheInvalidationService(db, settings).invalidate_all_caches(
            "cli_clear"
        )
    print(f"OK: cleared retrieval cache ({retrieval_rows} rows) and answer cache")
    return 0


def cmd_clear_qdrant(*, main: bool, answer_cache: bool) -> int:
    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        if main:
            QdrantService(collection=settings.qdrant_collection).delete_collection()
            print(f"OK: cleared Qdrant collection '{settings.qdrant_collection}'")
        if answer_cache:
            name = answer_cache_collection_name(settings.qdrant_collection)
            QdrantService(collection=name).delete_collection()
            print(f"OK: cleared Qdrant collection '{name}'")
    if not main and not answer_cache:
        print("Nothing to do (no collections selected)", file=sys.stderr)
        return 1
    return 0


def cmd_reset_db(*, confirm: str | None = None, i_understand: bool = False) -> int:
    """Drop all application tables and rebuild the schema via Alembic.

    Destructive: removes ALL data in the configured PostgreSQL database.
    Requires ``--i-understand-destructive`` and ``--confirm=<database_name>``.
    Refuses disposable-looking mistakes only by requiring exact DB name match.
    """
    from sqlalchemy.engine import make_url

    from app.core.config import get_config

    cfg = get_config()
    db_name = make_url(cfg.database_url).database or ""
    if not i_understand:
        print(
            "ERROR: refuse reset-db without --i-understand-destructive",
            file=sys.stderr,
        )
        return 2
    if confirm != db_name:
        print(
            f"ERROR: refuse reset-db — pass --confirm={db_name} (exact database name)",
            file=sys.stderr,
        )
        return 2
    # Extra guard: never allow reset against names that look like recovery DBs
    # unless the operator typed that exact name as confirm (already checked).
    print(f"Dropping all application tables in database {db_name!r} (PostgreSQL)...")
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    upgrade_to_head()
    print("OK: recreated empty schema via Alembic (alembic upgrade head)")
    return 0


def cmd_trigger_reindex(*, confirm: str | None = None, i_understand: bool = False) -> int:
    from sqlalchemy.engine import make_url

    from app.core.config import get_config

    db_name = make_url(get_config().database_url).database or ""
    if not i_understand or confirm != db_name:
        print(
            "ERROR: refuse trigger-reindex without "
            f"--i-understand-destructive --confirm={db_name}",
            file=sys.stderr,
        )
        return 2
    with SessionLocal() as db:
        if indexing_worker.is_running():
            print("ERROR: indexing job already running", file=sys.stderr)
            return 1

        settings = SettingsRepository(db).get_or_create()
        try:
            QdrantService(collection=settings.qdrant_collection).delete_collection()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant clear failed: %s", exc)

        removed = SourceRepository(db).delete_all()
        try:
            RetrievalCacheService(db).invalidate_all()
            AnswerCacheService(db, settings).invalidate_all()
            LexicalIndexService(db).delete_all()
            KnowledgeVersionService(db).bump()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache/index clear failed: %s", exc)

        job_id = indexing_worker.start(_Overrides())
        print(f"OK: cleared {removed} sources; reindex started (job {job_id})")
    return 0


def cmd_migrate() -> int:
    upgrade_to_head()
    print(f"OK: database migrated to head (revision {current_db_revision()})")
    return 0


def cmd_status() -> int:
    with SessionLocal() as db:
        settings = SettingsRepository(db).get_or_create()
        job = IndexJobRepository(db).latest()
        qdrant_ok, qdrant_detail = QdrantService(
            collection=settings.qdrant_collection
        ).health()
        print(f"qdrant_collection={settings.qdrant_collection}")
        print(f"answer_cache_collection={answer_cache_collection_name(settings.qdrant_collection)}")
        print("database_engine=PostgreSQL")
        print(f"database_revision={current_db_revision() or 'not-migrated'}")
        print(f"index_job_status={job.status if job else 'idle'}")
        print(f"qdrant_health={'ok' if qdrant_ok else 'error'} ({qdrant_detail})")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="AI Site Agent maintenance")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("clear-caches", help="Clear retrieval + answer caches")
    sub.add_parser("clear-retrieval-cache", help="Clear retrieval cache only")
    sub.add_parser("clear-answer-cache", help="Clear answer cache only")
    sub.add_parser("migrate", help="Run Alembic migrations (upgrade head)")
    reset = sub.add_parser(
        "reset-db", help="DROP all tables and rebuild schema via Alembic (destructive)"
    )
    reset.add_argument(
        "--i-understand-destructive",
        action="store_true",
        help="Required acknowledgement for reset-db",
    )
    reset.add_argument(
        "--confirm",
        default=None,
        help="Must equal the target database name from DATABASE_URL",
    )
    reindex = sub.add_parser(
        "trigger-reindex", help="Clear sources and start full reindex (destructive)"
    )
    reindex.add_argument(
        "--i-understand-destructive",
        action="store_true",
        help="Required acknowledgement for trigger-reindex",
    )
    reindex.add_argument(
        "--confirm",
        default=None,
        help="Must equal the target database name from DATABASE_URL",
    )
    sub.add_parser("status", help="Print maintenance-related status")

    qd = sub.add_parser("clear-qdrant", help="Delete Qdrant collection(s)")
    qd.add_argument("--main", action="store_true", help="Main knowledge collection")
    qd.add_argument(
        "--answer-cache", action="store_true", help="Semantic answer cache collection"
    )

    args = parser.parse_args(argv)

    if args.command == "clear-caches":
        return cmd_clear_caches()
    if args.command == "clear-retrieval-cache":
        return cmd_clear_retrieval_cache()
    if args.command == "clear-answer-cache":
        return cmd_clear_answer_cache()
    if args.command == "clear-qdrant":
        return cmd_clear_qdrant(main=args.main, answer_cache=args.answer_cache)
    if args.command == "reset-db":
        return cmd_reset_db(
            confirm=args.confirm,
            i_understand=bool(args.i_understand_destructive),
        )
    if args.command == "trigger-reindex":
        return cmd_trigger_reindex(
            confirm=args.confirm,
            i_understand=bool(args.i_understand_destructive),
        )
    if args.command == "migrate":
        return cmd_migrate()
    if args.command == "status":
        return cmd_status()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
