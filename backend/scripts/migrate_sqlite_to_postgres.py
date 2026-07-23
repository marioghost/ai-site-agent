"""One-time data migration from a legacy SQLite database to PostgreSQL.

SQLite is no longer supported at runtime. This utility exists only to move data
from an existing SQLite install into a fresh PostgreSQL database (whose schema
must already be created via ``alembic upgrade head``).

Usage (from the backend directory, with the project venv):

    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite-path ./ai_site_agent.db \
        --postgres-url postgresql+psycopg://ai_agent:change_me@localhost:5432/ai_site_agent

Options:
    --sqlite-path PATH       Path to the legacy SQLite file (required)
    --postgres-url URL       Target PostgreSQL URL (default: DATABASE_URL from env/.env)
    --dry-run                Read and report counts; write nothing
    --truncate-target        DELETE existing rows in target tables before copying
    --skip-caches            Do not copy cache tables (default behaviour)
    --include-caches         Copy cache tables (overrides the default skip)
    --skip-logs              Do not copy chat_logs / answer_traces

Defaults: caches are skipped; users, settings, sources, chunks, jobs and logs
are preserved. Row counts are validated after each table.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the backend package importable when run as ``python scripts/...``.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import Boolean, MetaData, Table, create_engine, func, select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from app import models  # noqa: E402,F401  (register models on Base.metadata)
from app.core.config import get_config  # noqa: E402
from app.core.database import Base  # noqa: E402

# FK-safe insertion order. Cache/log groupings are filtered by flags.
TABLE_ORDER = [
    "users",
    "settings",
    "sources",
    "chunks",
    "chat_sessions",
    "chat_messages",
    "index_jobs",
    "profile_generation_jobs",
    "chat_logs",
    "answer_traces",
    "source_intelligence_llm_cache",
    "retrieval_cache",
    "answer_cache",
]

CACHE_TABLES = {
    "retrieval_cache",
    "answer_cache",
    "source_intelligence_llm_cache",
}
LOG_TABLES = {"chat_logs", "answer_traces"}


def _sqlite_url(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        raise SystemExit(f"SQLite file not found: {p}")
    return f"sqlite:///{p.resolve()}"


def _coerce_row(target: Table, row: dict) -> dict:
    """Filter to target columns and coerce SQLite 0/1 into real booleans."""
    out: dict = {}
    for col in target.columns:
        if col.name not in row:
            continue
        val = row[col.name]
        if isinstance(col.type, Boolean) and val is not None:
            val = bool(val)
        out[col.name] = val
    return out


def _reset_sequence(pg_engine: Engine, table: str) -> None:
    """Reset the serial sequence for ``id`` after inserting explicit ids."""
    if "id" not in Base.metadata.tables[table].columns:
        return
    with pg_engine.begin() as conn:
        conn.exec_driver_sql(
            "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
            "COALESCE((SELECT MAX(id) FROM " + table + "), 1), true)",
            (table,),
        )


def migrate_table(
    name: str,
    src_engine: Engine,
    src_meta: MetaData,
    pg_engine: Engine,
    *,
    dry_run: bool,
    truncate: bool,
) -> tuple[int, int]:
    src_table = src_meta.tables.get(name)
    if src_table is None:
        print(f"  - {name}: not present in SQLite, skipping")
        return (0, 0)
    target = Base.metadata.tables[name]

    with src_engine.connect() as sconn:
        src_count = sconn.execute(select(func.count()).select_from(src_table)).scalar_one()
        rows = [dict(r._mapping) for r in sconn.execute(select(src_table)).all()]

    if dry_run:
        print(f"  - {name}: {src_count} rows (dry-run, not written)")
        return (src_count, 0)

    with pg_engine.begin() as conn:
        if truncate:
            conn.exec_driver_sql(f"DELETE FROM {name}")
        written = 0
        if rows:
            payload = [_coerce_row(target, r) for r in rows]
            conn.execute(target.insert(), payload)
            written = len(payload)

    _reset_sequence(pg_engine, name)

    with pg_engine.connect() as conn:
        dst_count = conn.execute(select(func.count()).select_from(target)).scalar_one()

    flag = "OK" if dst_count >= src_count else "MISMATCH"
    print(f"  - {name}: copied {written}; source={src_count} target={dst_count} [{flag}]")
    return (src_count, dst_count)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument("--sqlite-path", required=True, help="Legacy SQLite file path")
    parser.add_argument("--postgres-url", default=None, help="Target PostgreSQL URL")
    parser.add_argument("--dry-run", action="store_true", help="Report only; write nothing")
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="DELETE existing rows in target tables before copying",
    )
    parser.add_argument("--skip-caches", action="store_true", help="Skip cache tables (default)")
    parser.add_argument(
        "--include-caches", action="store_true", help="Include cache tables"
    )
    parser.add_argument("--skip-logs", action="store_true", help="Skip chat_logs/answer_traces")
    args = parser.parse_args(argv)

    pg_url = args.postgres_url or get_config().database_url
    if not pg_url or not pg_url.startswith("postgresql"):
        raise SystemExit(
            "A PostgreSQL --postgres-url (or DATABASE_URL) is required "
            "(postgresql+psycopg://...)."
        )

    include_caches = args.include_caches and not args.skip_caches
    skip_logs = args.skip_logs

    tables = []
    for name in TABLE_ORDER:
        if name in CACHE_TABLES and not include_caches:
            continue
        if name in LOG_TABLES and skip_logs:
            continue
        tables.append(name)

    print("SQLite -> PostgreSQL migration")
    print(f"  source: {args.sqlite_path}")
    print(f"  target: {pg_url.split('@')[-1] if '@' in pg_url else pg_url}")
    print(f"  caches: {'included' if include_caches else 'skipped'}")
    print(f"  logs:   {'skipped' if skip_logs else 'included'}")
    print(f"  mode:   {'DRY-RUN' if args.dry_run else 'WRITE'}")
    print("")

    src_engine = create_engine(_sqlite_url(args.sqlite_path))
    pg_engine = create_engine(pg_url)

    # Verify the target schema exists (migrated) unless dry-running.
    if not args.dry_run:
        from sqlalchemy import inspect

        existing = set(inspect(pg_engine).get_table_names())
        missing = [t for t in tables if t not in existing]
        if missing:
            raise SystemExit(
                "Target schema is not migrated (missing tables: "
                f"{', '.join(missing)}).\nRun: cd backend && alembic upgrade head"
            )

    src_meta = MetaData()
    src_meta.reflect(bind=src_engine)

    totals = {"source": 0, "target": 0}
    for name in tables:
        s, d = migrate_table(
            name,
            src_engine,
            src_meta,
            pg_engine,
            dry_run=args.dry_run,
            truncate=args.truncate_target,
        )
        totals["source"] += s
        totals["target"] += d

    print("")
    print(f"Done. total source rows={totals['source']} target rows={totals['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
