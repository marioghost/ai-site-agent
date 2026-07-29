#!/usr/bin/env python3
"""Empty-target schema bootstrap for migrate-machine rehearsal.

Historical Alembic 0001 uses Base.metadata.create_all() of *current* ORM models,
so empty ``alembic upgrade head`` fails at 0003 (DuplicateTable job_events).

This helper provides a fail-closed, TARGET-only path:

  recreate empty ai_site_agent (C.UTF-8) → init_db() → seven head indexes →
  catalog verify → alembic stamp 0019

Never a public CLI. Invoked only from migrate_machine.sh. Never prints secrets.
Does not rewrite historical migrations. Does not touch Qdrant/Ollama/product code.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

HEAD_REVISION = "0019_legacy_doc_type_canonical_enabled"
REQUIRED_DB_NAME = "ai_site_agent"
REQUIRED_COLLATE = "C.UTF-8"
REQUIRED_CTYPE = "C.UTF-8"
REQUIRED_ENCODING = "UTF8"

# Indexes required at head but absent from current ORM metadata / init_db().
REQUIRED_INDEXES: list[dict[str, str]] = [
    {
        "name": "ix_sources_needs_intelligence_true",
        "table": "sources",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_sources_needs_intelligence_true "
            "ON sources (needs_intelligence) WHERE needs_intelligence IS TRUE"
        ),
        "expect_indexdef_substr": "WHERE (needs_intelligence IS TRUE)",
    },
    {
        "name": "ix_sources_needs_reprocess_true",
        "table": "sources",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_sources_needs_reprocess_true "
            "ON sources (needs_reprocess) WHERE needs_reprocess IS TRUE"
        ),
        "expect_indexdef_substr": "WHERE (needs_reprocess IS TRUE)",
    },
    {
        "name": "ix_index_jobs_running",
        "table": "index_jobs",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_index_jobs_running "
            "ON index_jobs (status) WHERE status = 'running'"
        ),
        "expect_indexdef_substr": "WHERE (status = 'running'::text)",
    },
    {
        "name": "ix_index_jobs_status_updated_at",
        "table": "index_jobs",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_index_jobs_status_updated_at "
            "ON index_jobs (status, updated_at)"
        ),
        "expect_indexdef_substr": "USING btree (status, updated_at)",
    },
    {
        "name": "ix_sources_source_type_status",
        "table": "sources",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_sources_source_type_status "
            "ON sources (source_type, status)"
        ),
        "expect_indexdef_substr": "USING btree (source_type, status)",
    },
    {
        "name": "ix_claim_superseded_by_id",
        "table": "claim",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_claim_superseded_by_id "
            "ON claim (superseded_by_id)"
        ),
        "expect_indexdef_substr": "USING btree (superseded_by_id)",
    },
    {
        "name": "ix_claim_revision_of_id",
        "table": "claim",
        "create_sql": (
            "CREATE INDEX IF NOT EXISTS ix_claim_revision_of_id "
            "ON claim (revision_of_id)"
        ),
        "expect_indexdef_substr": "USING btree (revision_of_id)",
    },
]

REQUIRED_TABLES = (
    "sources",
    "chunks",
    "settings",
    "index_jobs",
    "job_events",
    "analytics_hourly",
    "users",
    "claim",
    "observation_ref",
    "evidence_link",
    "chat_messages",
    "chat_sessions",
    "answer_traces",
    "alembic_version",
)

APP_DATA_TABLES = (
    "sources",
    "chunks",
    "claim",
    "observation_ref",
    "evidence_link",
    "chat_messages",
    "answer_traces",
)

# Disposable DB names allowed only when MM_EMPTY_TARGET_BOOTSTRAP_TEST=1.
_TEST_DB_RE = re.compile(r"^mm_empty_bootstrap_[a-z0-9_]+$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact_url(url: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]+@", r"\1***@", url or "")


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def write_atomic(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parse_db_url(url: str) -> dict[str, str]:
    raw = url.replace("postgresql+psycopg://", "postgresql://", 1)
    raw = raw.replace("postgresql+psycopg2://", "postgresql://", 1)
    u = urlparse(raw)
    if u.scheme not in ("postgresql", "postgres") or not u.path or u.path == "/":
        die("DATABASE_URL is not a parseable PostgreSQL URL")
    return {
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "host": u.hostname or "127.0.0.1",
        "port": str(u.port or 5432),
        "db": unquote(u.path.lstrip("/").split("?")[0]),
    }


def psql(conn: dict[str, str], sql: str, db: str | None = None) -> str:
    env = dict(os.environ)
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]
    cmd = [
        "psql",
        "-At",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        conn["host"],
        "-p",
        conn["port"],
        "-U",
        conn["user"],
        "-d",
        db or conn["db"],
        "-c",
        sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        err = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "unknown"
        die(f"psql failed: {err}")
    return res.stdout.strip()


def load_state(state_dir: str) -> dict[str, Any]:
    p = Path(state_dir) / "state.json"
    if not p.is_file():
        die(f"migration state missing: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def allow_test_db(name: str) -> bool:
    return os.environ.get("MM_EMPTY_TARGET_BOOTSTRAP_TEST") == "1" and bool(
        _TEST_DB_RE.match(name)
    )


def assert_db_name_allowed(name: str) -> None:
    if name == REQUIRED_DB_NAME:
        return
    if allow_test_db(name):
        return
    die(f"refusing database name '{name}' (only '{REQUIRED_DB_NAME}' allowed)")


def gate_migration_state(state: dict[str, Any], role_arg: str) -> list[str]:
    """Return list of gate failures (empty = ok)."""
    fails: list[str] = []
    role = (state.get("role") or role_arg or "").strip()
    if role != "target":
        fails.append(f"host role is '{role or 'unknown'}', not target")
    completed = list(state.get("completed_phases") or [])
    if "target_rehearse" in completed:
        fails.append("target_rehearse already completed")
    if "target_accept" in completed:
        fails.append("target already accepted")
    if "target_switch" in completed:
        fails.append("target already switched")
    if "target_restore" in completed:
        fails.append("source bundle already restored (target_restore completed)")
    confirms = list(state.get("confirmations") or [])
    if "ERASE" in confirms:
        fails.append("ERASE already confirmed")
    for token in ("ACCEPT", "SWITCH"):
        if token in confirms:
            fails.append(f"{token} already confirmed — target must not be treated as authoritative bootstrap")
    if state.get("bundle_id"):
        fails.append("bundle_id present — treat as restored/incoming cutover state")
    if state.get("authoritative") is True:
        fails.append("state marks host authoritative — refusing empty-target bootstrap")
    return fails


def db_identity(conn: dict[str, str]) -> dict[str, str]:
    row = psql(
        conn,
        "SELECT datname||'|'||pg_encoding_to_char(encoding)||'|'||datcollate||'|'||datctype "
        "FROM pg_database WHERE datname = current_database()",
    )
    parts = row.split("|")
    if len(parts) != 4:
        die("could not read database identity from pg_database")
    return {
        "database": parts[0],
        "encoding": parts[1],
        "collate": parts[2],
        "ctype": parts[3],
    }


def recovery_db_exists(conn: dict[str, str]) -> bool:
    out = psql(
        conn,
        "SELECT COUNT(*) FROM pg_database WHERE datname LIKE '%recovery%'",
        db="postgres" if conn["db"] != "postgres" else conn["db"],
    )
    # When connected user cannot see other DBs, fall back to current-only check.
    try:
        return int(out or "0") > 0
    except ValueError:
        return "recovery" in (out or "")


def table_exists(conn: dict[str, str], table: str) -> bool:
    out = psql(
        conn,
        "SELECT COUNT(*) FROM information_schema.tables "
        f"WHERE table_schema='public' AND table_name='{table}'",
    )
    return int(out or "0") > 0


def app_data_counts(conn: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in APP_DATA_TABLES:
        if not table_exists(conn, table):
            counts[table] = 0
            continue
        counts[table] = int(psql(conn, f"SELECT COUNT(*) FROM {table}") or 0)
    return counts


def is_empty_of_app_data(counts: dict[str, int]) -> bool:
    return all(v == 0 for v in counts.values())


def index_catalog(conn: dict[str, str]) -> dict[str, str]:
    """name -> pg_get_indexdef text for public indexes."""
    out = psql(
        conn,
        "SELECT indexname||'|'||pg_get_indexdef((quote_ident(schemaname)||'.'||quote_ident(indexname))::regclass) "
        "FROM pg_indexes WHERE schemaname='public'",
    )
    result: dict[str, str] = {}
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, definition = line.split("|", 1)
        result[name] = definition
    return result


def fulltext_objects(conn: dict[str, str]) -> dict[str, Any]:
    col = psql(
        conn,
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='chunks' AND column_name='search_vector'",
    )
    attis = ""
    if int(col or "0") > 0:
        attis = psql(
            conn,
            "SELECT a.attgenerated||'|'||format_type(a.atttypid,a.atttypmod) "
            "FROM pg_attribute a "
            "JOIN pg_class c ON c.oid=a.attrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname='chunks' AND a.attname='search_vector' "
            "AND a.attnum>0 AND NOT a.attisdropped",
        )
    gin = psql(
        conn,
        "SELECT COUNT(*) FROM pg_indexes "
        "WHERE schemaname='public' AND indexname='ix_chunks_search_vector'",
    )
    gin_def = ""
    if int(gin or "0") > 0:
        idxs = index_catalog(conn)
        gin_def = idxs.get("ix_chunks_search_vector", "")
    generated = ""
    typ = ""
    if "|" in attis:
        generated, typ = attis.split("|", 1)
    return {
        "search_vector_present": int(col or "0") > 0,
        "search_vector_generated": generated,  # 's' = stored generated
        "search_vector_type": typ,
        "ix_chunks_search_vector_present": int(gin or "0") > 0,
        "ix_chunks_search_vector_def": gin_def,
    }


def alembic_revision(conn: dict[str, str]) -> str | None:
    if not table_exists(conn, "alembic_version"):
        return None
    rows = psql(conn, "SELECT version_num FROM alembic_version ORDER BY version_num")
    lines = [ln for ln in rows.splitlines() if ln.strip()]
    if len(lines) > 1:
        die(f"alembic_version has multiple rows: {lines}")
    return lines[0] if lines else None


def _table_columns(conn: dict[str, str], table: str) -> list[dict[str, str]]:
    out = psql(
        conn,
        "SELECT column_name||'|'||udt_name||'|'||is_nullable||'|'||coalesce(column_default,'')||'|'||"
        "coalesce(generation_expression,'') "
        "FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{table}' "
        "ORDER BY ordinal_position",
    )
    rows: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) < 4:
            continue
        rows.append(
            {
                "name": parts[0],
                "udt_name": parts[1],
                "is_nullable": parts[2],
                "column_default": parts[3],
                "generation_expression": parts[4] if len(parts) > 4 else "",
            }
        )
    return rows


def _table_constraints(conn: dict[str, str], table: str) -> dict[str, list[str]]:
    """Return primary/unique/foreign constraint names from pg_constraint."""
    out = psql(
        conn,
        "SELECT c.contype||'|'||c.conname "
        "FROM pg_constraint c "
        "JOIN pg_class t ON t.oid=c.conrelid "
        "JOIN pg_namespace n ON n.oid=t.relnamespace "
        f"WHERE n.nspname='public' AND t.relname='{table}' "
        "AND c.contype IN ('p','u','f') "
        "ORDER BY c.contype, c.conname",
    )
    result: dict[str, list[str]] = {"primary": [], "unique": [], "foreign": []}
    for line in out.splitlines():
        if "|" not in line:
            continue
        ctype, name = line.split("|", 1)
        if ctype == "p":
            result["primary"].append(name)
        elif ctype == "u":
            result["unique"].append(name)
        elif ctype == "f":
            result["foreign"].append(name)
    return result


def catalog_structure(conn: dict[str, str]) -> dict[str, Any]:
    """Machine-enforced structure report from PostgreSQL catalogs (not ORM-only)."""
    tables: dict[str, Any] = {}
    structure_ok = True
    for table in REQUIRED_TABLES:
        if table == "alembic_version":
            continue
        if not table_exists(conn, table):
            tables[table] = {"present": False}
            structure_ok = False
            continue
        cols = _table_columns(conn, table)
        cons = _table_constraints(conn, table)
        present = True
        has_cols = len(cols) > 0
        has_pk = len(cons["primary"]) >= 1
        if not has_cols or not has_pk:
            structure_ok = False
        tables[table] = {
            "present": present,
            "columns": cols,
            "column_count": len(cols),
            "constraints": cons,
            "has_primary_key": has_pk,
            "ok": has_cols and has_pk,
        }
    return {"tables": tables, "ok": structure_ok}


def verify_orm_catalog_match(
    backend_dir: Path, database_url: str
) -> dict[str, Any]:
    """Compare live PG catalogs to ORM expectations via SQLAlchemy Inspector.

    Reads catalogs through the DBAPI (not metadata alone). Failures listed
    explicitly; used as an additional gate before stamp.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(backend_dir)
    py = backend_dir / ".venv" / "bin" / "python"
    python = str(py) if py.is_file() else sys.executable
    code = r"""
import json, sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

url = sys.argv[1]
try:
    from app import models  # noqa: F401
    from app.core.database import Base
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"import: {exc}"}))
    raise SystemExit(0)

eng = create_engine(url)
try:
    insp = inspect(eng)
except SQLAlchemyError as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    raise SystemExit(0)

failures = []
checked = {"tables": 0, "columns": 0, "pks": 0, "fks": 0, "uniques": 0}
db_tables = set(insp.get_table_names())
for table_name, table in Base.metadata.tables.items():
    checked["tables"] += 1
    if table_name not in db_tables:
        failures.append(f"missing table {table_name}")
        continue
    cols = {c["name"]: c for c in insp.get_columns(table_name)}
    for col in table.columns:
        checked["columns"] += 1
        if col.name not in cols:
            failures.append(f"{table_name}.{col.name}: missing column")
            continue
        live = cols[col.name]
        if bool(live.get("nullable", True)) != bool(col.nullable):
            # Generated / server-default columns can differ; flag only clear mismatches
            if col.nullable is False and live.get("nullable", True) is True and live.get("default") is None and live.get("computed") is None:
                failures.append(
                    f"{table_name}.{col.name}: nullable mismatch orm={col.nullable} db={live.get('nullable')}"
                )
    pk = insp.get_pk_constraint(table_name) or {}
    pk_cols = list(pk.get("constrained_columns") or [])
    orm_pk = [c.name for c in table.primary_key.columns]
    checked["pks"] += 1
    if sorted(pk_cols) != sorted(orm_pk):
        failures.append(f"{table_name}: pk mismatch orm={orm_pk} db={pk_cols}")
    for fk in insp.get_foreign_keys(table_name):
        checked["fks"] += 1
        if not fk.get("constrained_columns"):
            failures.append(f"{table_name}: empty foreign key")
    for uq in insp.get_unique_constraints(table_name):
        checked["uniques"] += 1
        if not uq.get("column_names"):
            failures.append(f"{table_name}: empty unique constraint")
print(json.dumps({"ok": not failures, "failures": failures[:50], "checked": checked}))
"""
    res = subprocess.run(
        [python, "-c", code, database_url],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "orm catalog match failed").strip()
        return {"ok": False, "error": err.splitlines()[-1], "failures": []}
    line = (res.stdout or "").strip().splitlines()
    if not line:
        return {"ok": False, "error": "empty orm-match output", "failures": []}
    try:
        return json.loads(line[-1])
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid orm-match json", "failures": [line[-1][:200]]}


def verify_schema(
    conn: dict[str, str],
    *,
    backend_dir: Path | None = None,
    database_url: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Catalog verification against expected head shape. Does not stamp."""
    identity = db_identity(conn)
    counts = app_data_counts(conn)
    idxs = index_catalog(conn)
    ft = fulltext_objects(conn)
    structure = catalog_structure(conn)
    tables_ok = {t: table_exists(conn, t) for t in REQUIRED_TABLES if t != "alembic_version"}
    # alembic_version may be absent before stamp
    tables_ok["alembic_version"] = table_exists(conn, "alembic_version")

    index_results: list[dict[str, Any]] = []
    indexes_ok = True
    for spec in REQUIRED_INDEXES:
        name = spec["name"]
        definition = idxs.get(name, "")
        present = name in idxs
        pred_ok = (
            spec["expect_indexdef_substr"].lower() in definition.lower() if present else False
        )
        # PG may normalize casts; also accept without ::text for running predicate
        if present and not pred_ok and "WHERE" in spec["expect_indexdef_substr"]:
            soft = True
            if "needs_intelligence" in name and "needs_intelligence" not in definition:
                soft = False
            if "needs_reprocess" in name and "needs_reprocess" not in definition:
                soft = False
            if name == "ix_index_jobs_running" and (
                "running" not in definition or "status" not in definition
            ):
                soft = False
            if name == "ix_index_jobs_status_updated_at" and (
                "status" not in definition or "updated_at" not in definition
            ):
                soft = False
            if name == "ix_sources_source_type_status" and (
                "source_type" not in definition or "status" not in definition
            ):
                soft = False
            if name.endswith("superseded_by_id") and "superseded_by_id" not in definition:
                soft = False
            if name.endswith("revision_of_id") and "revision_of_id" not in definition:
                soft = False
            pred_ok = soft
        elif present and not pred_ok:
            # Non-partial indexes: require column fragments
            soft = True
            for frag in (
                "superseded_by_id",
                "revision_of_id",
                "source_type",
                "updated_at",
            ):
                if frag in spec["expect_indexdef_substr"] and frag not in definition:
                    soft = False
            pred_ok = soft
        ok = present and pred_ok
        if not ok:
            indexes_ok = False
        index_results.append(
            {
                "name": name,
                "present": present,
                "definition": definition,
                "predicate_or_columns_ok": pred_ok,
                "ok": ok,
            }
        )

    ft_ok = (
        ft["search_vector_present"]
        and ft["search_vector_generated"] == "s"
        and "tsvector" in (ft["search_vector_type"] or "")
        and ft["ix_chunks_search_vector_present"]
        and "gin" in (ft["ix_chunks_search_vector_def"] or "").lower()
    )

    collate_ok = identity["collate"] == REQUIRED_COLLATE
    ctype_ok = identity["ctype"] == REQUIRED_CTYPE
    encoding_ok = identity["encoding"] == REQUIRED_ENCODING
    empty_ok = is_empty_of_app_data(counts)
    tables_all = all(tables_ok[t] for t in REQUIRED_TABLES if t != "alembic_version")

    orm_match: dict[str, Any] | None = None
    orm_ok = True
    if backend_dir is not None and database_url:
        orm_match = verify_orm_catalog_match(backend_dir, database_url)
        orm_ok = bool(orm_match.get("ok"))

    report = {
        "identity": identity,
        "collate_ok": collate_ok,
        "ctype_ok": ctype_ok,
        "encoding_ok": encoding_ok,
        "tables": tables_ok,
        "tables_ok": tables_all,
        "catalog_structure": structure,
        "catalog_structure_ok": structure["ok"],
        "orm_catalog_match": orm_match,
        "orm_catalog_match_ok": orm_ok,
        "app_data_counts": counts,
        "empty_of_app_data": empty_ok,
        "indexes": index_results,
        "indexes_ok": indexes_ok,
        "fulltext": ft,
        "fulltext_ok": ft_ok,
        "alembic_revision": alembic_revision(conn),
    }
    ok = (
        collate_ok
        and ctype_ok
        and encoding_ok
        and tables_all
        and structure["ok"]
        and orm_ok
        and indexes_ok
        and ft_ok
        and empty_ok
    )
    report["ok"] = ok
    return ok, report


def apply_required_indexes(conn: dict[str, str]) -> None:
    for spec in REQUIRED_INDEXES:
        psql(conn, spec["create_sql"])


def run_init_db(backend_dir: Path, database_url: str) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(backend_dir)
    # Prefer project venv when present (rehearsal /opt tree).
    py = backend_dir / ".venv" / "bin" / "python"
    python = str(py) if py.is_file() else sys.executable
    code = (
        "from app.core.database import init_db\n"
        "init_db()\n"
        "print('OK: init_db')\n"
    )
    res = subprocess.run(
        [python, "-c", code],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "init_db failed").strip()
        die(f"init_db failed: {err.splitlines()[-1]}")


def alembic_stamp_head(backend_dir: Path, database_url: str) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(backend_dir)
    py = backend_dir / ".venv" / "bin" / "python"
    python = str(py) if py.is_file() else sys.executable
    code = (
        "from alembic import command\n"
        "from app.core.alembic_config import make_alembic_config\n"
        f"command.stamp(make_alembic_config({database_url!r}), {HEAD_REVISION!r})\n"
        "print('OK: stamped')\n"
    )
    res = subprocess.run(
        [python, "-c", code],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "stamp failed").strip()
        die(f"alembic stamp failed: {err.splitlines()[-1]}")


def prove_alembic_upgrade_duplicate(backend_dir: Path, database_url: str) -> dict[str, Any]:
    """On a disposable empty DB, show upgrade head hits DuplicateTable (test aid)."""
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(backend_dir)
    py = backend_dir / ".venv" / "bin" / "python"
    python = str(py) if py.is_file() else sys.executable
    code = (
        "from app.core.alembic_config import upgrade_to_head\n"
        "try:\n"
        f"    upgrade_to_head({database_url!r})\n"
        "    print('UNEXPECTED_SUCCESS')\n"
        "except Exception as exc:\n"
        "    print(type(exc).__name__ + ':' + str(exc))\n"
    )
    res = subprocess.run(
        [python, "-c", code],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    text = (res.stdout or "") + (res.stderr or "")
    return {
        "exit_code": res.returncode,
        "output_tail": text.strip().splitlines()[-5:],
        "duplicate_table_seen": "DuplicateTable" in text or "already exists" in text,
    }


def _write_report(path: str, report: dict[str, Any]) -> None:
    write_atomic(Path(path), json.dumps(report, indent=2, sort_keys=True) + "\n")


def probe_bootstrap_need(args: argparse.Namespace) -> int:
    """Exit 0=ready, 10=needs bootstrap, 1=refuse."""
    conn = parse_db_url(args.database_url)
    assert_db_name_allowed(conn["db"])
    state = load_state(args.state_dir)
    gate_fails = gate_migration_state(state, args.role)
    if gate_fails:
        print("REFUSE: " + "; ".join(gate_fails), file=sys.stderr)
        return 1
    try:
        rec = psql(
            conn,
            "SELECT COUNT(*) FROM pg_database WHERE datname = 'ai_site_agent_recovery'",
            db="postgres",
        )
        if int(rec or "0") > 0 and not allow_test_db(conn["db"]):
            print("REFUSE: ai_site_agent_recovery exists", file=sys.stderr)
            return 1
    except SystemExit:
        # Non-superuser may not connect to postgres DB; fail closed only for prod name.
        if not allow_test_db(conn["db"]):
            # Continue — recovery check best-effort when lacking rights.
            pass

    identity = db_identity(conn)
    if identity["collate"] != REQUIRED_COLLATE or identity["ctype"] != REQUIRED_CTYPE:
        print(
            f"REFUSE: wrong collation {identity['collate']}/{identity['ctype']}",
            file=sys.stderr,
        )
        return 1
    if identity["encoding"] != REQUIRED_ENCODING:
        print(f"REFUSE: wrong encoding {identity['encoding']}", file=sys.stderr)
        return 1

    counts = app_data_counts(conn)
    if not is_empty_of_app_data(counts):
        print("REFUSE: database has application data", file=sys.stderr)
        return 1

    backend_arg = getattr(args, "backend_dir", None) or None
    backend_path = Path(backend_arg) if backend_arg else None
    ok, _ = verify_schema(
        conn,
        backend_dir=backend_path,
        database_url=args.database_url if backend_path else None,
    )
    rev = alembic_revision(conn)
    if ok and rev == HEAD_REVISION:
        print("READY")
        return 0
    print("NEEDS_BOOTSTRAP")
    return 10


def cmd_bootstrap(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {
        "checked_at": now_iso(),
        "schema_bootstrap_method": "init_db+seven_indexes+stamp_0019",
        "database_url_redacted": redact_url(args.database_url),
        "result": "FAIL",
    }
    try:
        conn = parse_db_url(args.database_url)
        assert_db_name_allowed(conn["db"])
        report["database"] = conn["db"]

        state = load_state(args.state_dir)
        gate_fails = gate_migration_state(state, args.role)
        report["gates"] = {"ok": not gate_fails, "failures": gate_fails}
        if gate_fails:
            die("bootstrap refused: " + "; ".join(gate_fails))

        try:
            rec = psql(
                conn,
                "SELECT COUNT(*) FROM pg_database WHERE datname = 'ai_site_agent_recovery'",
                db="postgres",
            )
            if int(rec or "0") > 0 and not allow_test_db(conn["db"]):
                die("ai_site_agent_recovery exists — refusing bootstrap on this host layout")
        except SystemExit:
            if not allow_test_db(conn["db"]):
                pass

        identity = db_identity(conn)
        report["encoding"] = identity["encoding"]
        report["collation"] = identity["collate"]
        report["ctype"] = identity["ctype"]

        if identity["collate"] != REQUIRED_COLLATE or identity["ctype"] != REQUIRED_CTYPE:
            die(
                f"wrong collation/ctype {identity['collate']}/{identity['ctype']} "
                f"(require {REQUIRED_COLLATE}/{REQUIRED_CTYPE})"
            )
        if identity["encoding"] != REQUIRED_ENCODING:
            die(f"wrong encoding {identity['encoding']} (require {REQUIRED_ENCODING})")

        counts = app_data_counts(conn)
        report["pre_bootstrap_app_data_counts"] = counts
        if not is_empty_of_app_data(counts):
            die("database is not empty of application data — refusing bootstrap")

        backend = Path(args.backend_dir)
        if not (backend / "alembic.ini").is_file():
            die(f"backend_dir missing alembic.ini: {backend}")

        # Idempotent path: already verified head schema + stamp.
        ok, schema_rep = verify_schema(
            conn, backend_dir=backend, database_url=args.database_url
        )
        rev = alembic_revision(conn)
        if ok and rev == HEAD_REVISION:
            report["orm_init_result"] = "skipped_already_bootstrapped"
            report["pre_stamp_verification"] = schema_rep
            report["stamped_revision"] = rev
            report["post_stamp_verification"] = schema_rep
            report["indexes"] = schema_rep["indexes"]
            report["fulltext"] = schema_rep["fulltext"]
            report["catalog_structure"] = schema_rep.get("catalog_structure")
            report["result"] = "PASS"
            report["mode"] = "idempotent_verify_only"
            _write_report(args.report, report)
            print("OK: empty-target schema already verified at head (idempotent)")
            return 0

        if args.verify_only:
            report["pre_stamp_verification"] = schema_rep
            report["result"] = "FAIL"
            _write_report(args.report, report)
            die("verify-only: schema not at expected empty-target head state")

        if not args.skip_recreate:
            die(
                "database recreate must be performed by the shell caller "
                "(--skip-recreate after empty recreate)"
            )

        # Ensure we do not stamp before verification: init → indexes → verify → stamp.
        report["orm_init_result"] = "pending"
        run_init_db(backend, args.database_url)
        report["orm_init_result"] = "ok"

        apply_required_indexes(conn)

        ok, schema_rep = verify_schema(
            conn, backend_dir=backend, database_url=args.database_url
        )
        report["pre_stamp_verification"] = schema_rep
        report["indexes"] = schema_rep["indexes"]
        report["fulltext"] = schema_rep["fulltext"]
        report["catalog_structure"] = schema_rep.get("catalog_structure")
        if not ok:
            _write_report(args.report, report)
            die("pre-stamp schema verification FAILED — not stamping")

        # Stamp only after verification passes.
        if alembic_revision(conn) != HEAD_REVISION:
            alembic_stamp_head(backend, args.database_url)
        report["stamped_revision"] = alembic_revision(conn)

        ok2, schema_rep2 = verify_schema(
            conn, backend_dir=backend, database_url=args.database_url
        )
        report["post_stamp_verification"] = schema_rep2
        if report["stamped_revision"] != HEAD_REVISION:
            die(f"stamp mismatch: {report['stamped_revision']}")
        if not ok2:
            die("post-stamp schema verification FAILED")

        n = int(psql(conn, "SELECT COUNT(*) FROM alembic_version") or "0")
        if n != 1:
            die(f"alembic_version row count is {n}, want 1")

        report["result"] = "PASS"
        report["mode"] = "bootstrap"
        _write_report(args.report, report)
        print("OK: empty-target schema bootstrap PASS")
        return 0
    except SystemExit:
        if report.get("result") != "PASS":
            try:
                _write_report(args.report, report)
            except Exception:
                pass
        raise


def cmd_prove_duplicate(args: argparse.Namespace) -> int:
    """Test helper: empty DB + alembic upgrade head must show DuplicateTable."""
    backend = Path(args.backend_dir)
    info = prove_alembic_upgrade_duplicate(backend, args.database_url)
    print(json.dumps(info, indent=2))
    return 0 if info.get("duplicate_table_seen") else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="bootstrap_empty_target_schema.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe")
    p.add_argument("--database-url", required=True)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--role", default="target")
    p.add_argument(
        "--backend-dir",
        default="",
        help="Optional backend for ORM↔catalog match during READY check",
    )
    p.set_defaults(func=probe_bootstrap_need)

    p = sub.add_parser("bootstrap")
    p.add_argument("--database-url", required=True)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--backend-dir", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--role", default="target")
    p.add_argument(
        "--skip-recreate",
        action="store_true",
        help="Caller already recreated the empty database",
    )
    p.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify; never init/stamp",
    )
    p.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("prove-duplicate-upgrade")
    p.add_argument("--database-url", required=True)
    p.add_argument("--backend-dir", required=True)
    p.set_defaults(func=cmd_prove_duplicate)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
