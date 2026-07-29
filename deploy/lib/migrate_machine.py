#!/usr/bin/env python3
"""Helpers for `manage_deploy.sh migrate-machine`.

Owns only the parts that are unsafe or unreadable in shell: atomic state,
JSON manifests, machine-to-machine comparison, and retrieval parity.

Never prints secrets. Never mutates the corpus. Every comparison is
expected-vs-actual against a bundle manifest, never against documentation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1

# Retrieval parity thresholds. Do not loosen without recorded evidence.
PARITY_RANK1_REQUIRED_RATIO = 1.0  # rank-1 identical for every query
PARITY_TOP3_MIN_MATCHES = 28  # of 30
PARITY_SCORE_TOLERANCE = 0.01


# --------------------------------------------------------------------------
# small utilities
# --------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_url(url: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]+@", r"\1***@", url or "")


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def write_atomic(path: Path, data: str) -> None:
    """Write via temp file + fsync + rename so power loss cannot truncate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# --------------------------------------------------------------------------
# migration state
# --------------------------------------------------------------------------
def state_path(state_dir: str) -> Path:
    return Path(state_dir) / "state.json"


def state_load(state_dir: str, required: bool = True) -> dict:
    p = state_path(state_dir)
    if not p.exists():
        if required:
            die(f"no migration state at {p}")
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"migration state is corrupt ({exc}); remove {p} after review")
    version = data.get("schema_version")
    if version != STATE_SCHEMA_VERSION:
        die(
            f"migration state schema {version!r} is incompatible with this tool "
            f"(expected {STATE_SCHEMA_VERSION}); do not continue"
        )
    return data


def state_save(state_dir: str, data: dict) -> None:
    data["updated_at"] = now_iso()
    write_atomic(state_path(state_dir), dump_json(data))


def cmd_state_init(args: argparse.Namespace) -> int:
    p = state_path(args.dir)
    if p.exists():
        data = state_load(args.dir)
        if data.get("role") != args.role:
            die(
                f"host already has migration state with role "
                f"{data.get('role')!r}; refusing to re-init as {args.role!r}"
            )
        print(data["migration_id"])
        return 0
    data = {
        "schema_version": STATE_SCHEMA_VERSION,
        "migration_id": args.migration_id,
        "role": args.role,
        "source_hostname": args.source_hostname or "",
        "target_hostname": args.target_hostname or "",
        "c_cut": "",
        "current_phase": "",
        "completed_phases": [],
        "confirmations": [],
        "bundle_id": "",
        "last_error_code": "",
        "next_action": "",
        "created_at": now_iso(),
    }
    state_save(args.dir, data)
    print(data["migration_id"])
    return 0


def cmd_state_get(args: argparse.Namespace) -> int:
    data = state_load(args.dir, required=not args.optional)
    if not data:
        return 0
    val = data.get(args.key, "")
    if isinstance(val, list):
        print("\n".join(str(v) for v in val))
    else:
        print(val)
    return 0


def cmd_state_set(args: argparse.Namespace) -> int:
    data = state_load(args.dir)
    for pair in args.pairs:
        if "=" not in pair:
            die(f"expected key=value, got {pair!r}")
        key, val = pair.split("=", 1)
        data[key] = val
    state_save(args.dir, data)
    return 0


def cmd_state_complete(args: argparse.Namespace) -> int:
    data = state_load(args.dir)
    done = data.get("completed_phases", [])
    if args.phase not in done:
        done.append(args.phase)
    data["completed_phases"] = done
    data["current_phase"] = args.phase
    data["last_error_code"] = ""
    state_save(args.dir, data)
    return 0


def cmd_state_confirm(args: argparse.Namespace) -> int:
    """Record a typed confirmation so destructive work is never auto-repeated."""
    data = state_load(args.dir)
    confs = data.get("confirmations", [])
    entry = f"{args.word}@{now_iso()}"
    if not any(c.split("@", 1)[0] == args.word for c in confs):
        confs.append(entry)
    data["confirmations"] = confs
    state_save(args.dir, data)
    return 0


def cmd_state_has_confirm(args: argparse.Namespace) -> int:
    data = state_load(args.dir)
    confs = data.get("confirmations", [])
    return 0 if any(c.split("@", 1)[0] == args.word for c in confs) else 1


def cmd_state_show(args: argparse.Namespace) -> int:
    data = state_load(args.dir)
    print(f"  migration id : {data.get('migration_id','')}")
    print(f"  host role    : {data.get('role','')}")
    print(f"  phase        : {data.get('current_phase','') or '(none yet)'}")
    done = data.get("completed_phases", [])
    print(f"  completed    : {len(done)} phase(s)")
    if data.get("c_cut"):
        print(f"  cutover code : {data['c_cut'][:12]}")
    return 0


# --------------------------------------------------------------------------
# database facts (psql only — no venv or driver dependency)
# --------------------------------------------------------------------------
def parse_db_url(url: str) -> dict:
    u = url.replace("postgresql+psycopg://", "postgresql://", 1)
    u = u.replace("postgresql+psycopg2://", "postgresql://", 1)
    m = re.match(
        r"^postgresql://(?P<user>[^:/@]+)(?::(?P<password>[^@]*))?@"
        r"(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<db>[^?]+)",
        u,
    )
    if not m:
        die("DATABASE_URL is not a parseable PostgreSQL URL")
    g = m.groupdict()
    return {
        "user": g["user"],
        "password": g.get("password") or "",
        "host": g["host"],
        "port": g.get("port") or "5432",
        "db": g["db"],
    }


def psql(conn: dict, sql: str, db: str | None = None) -> str:
    env = dict(os.environ)
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]
    cmd = [
        "psql", "-At", "-v", "ON_ERROR_STOP=1",
        "-h", conn["host"], "-p", conn["port"], "-U", conn["user"],
        "-d", db or conn["db"], "-c", sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        die(f"psql failed: {res.stderr.strip().splitlines()[-1] if res.stderr.strip() else 'unknown'}")
    return res.stdout.strip()


def _scalar(conn: dict, sql: str) -> Any:
    out = psql(conn, sql)
    return out.splitlines()[0] if out else ""


def collect_db_facts(url: str) -> dict:
    conn = parse_db_url(url)
    facts: dict[str, Any] = {"database_name": conn["db"], "database_url_redacted": redact_url(url)}

    facts["alembic_revision"] = _scalar(conn, "SELECT version_num FROM alembic_version")
    for key, table in (
        ("sources", "sources"),
        ("chunks", "chunks"),
        ("claims", "claim"),
        ("observations", "observation_ref"),
        ("evidence_links", "evidence_link"),
        ("chat_messages", "chat_messages"),
        ("answer_traces", "answer_traces"),
    ):
        facts[key] = int(_scalar(conn, f"SELECT COUNT(*) FROM {table}") or 0)

    for key, table in (("chat_messages", "chat_messages"), ("answer_traces", "answer_traces")):
        facts[f"{key}_max_created_at"] = _scalar(
            conn, f"SELECT COALESCE(MAX(created_at)::text, '') FROM {table}"
        )

    facts["knowledge_version"] = int(
        _scalar(conn, "SELECT knowledge_version FROM settings WHERE id = 1") or 0
    )
    facts["memory_version"] = int(
        _scalar(conn, "SELECT memory_version FROM settings WHERE id = 1") or 0
    )
    facts["lc_collate"] = _scalar(conn, "SHOW lc_collate")
    facts["server_version"] = _scalar(conn, "SHOW server_version")
    facts["encoding"] = _scalar(
        conn, "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = current_database()"
    )

    # Every boolean settings flag, discovered rather than hardcoded.
    flag_rows = psql(
        conn,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='settings' "
        "AND data_type='boolean' ORDER BY column_name",
    )
    flags: dict[str, Any] = {}
    names = [r for r in flag_rows.splitlines() if r]
    if names:
        cols = ", ".join(f'"{n}"' for n in names)
        vals = psql(conn, f"SELECT {cols} FROM settings WHERE id = 1")
        parts = vals.split("|") if vals else []
        for name, val in zip(names, parts):
            flags[name] = val == "t"
    facts["feature_flags"] = flags
    return facts


def cmd_db_facts(args: argparse.Namespace) -> int:
    print(dump_json(collect_db_facts(args.url)), end="")
    return 0


def cmd_db_ping(args: argparse.Namespace) -> int:
    """Connectivity only: an empty database must ping, so no table is touched."""
    conn = parse_db_url(args.url)
    psql(conn, "SELECT 1")
    print(f"OK: {conn['db']} reachable")
    return 0


# --------------------------------------------------------------------------
# service facts (Qdrant / Ollama)
# --------------------------------------------------------------------------
def http_json(url: str, payload: dict | None = None, token: str = "", timeout: int = 60) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def collect_qdrant_facts(base: str, collections: list[str]) -> dict:
    out: dict[str, Any] = {}
    for name in collections:
        try:
            info = http_json(f"{base}/collections/{name}")["result"]
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError):
            out[name] = {"present": False}
            continue
        vectors = ((info.get("config") or {}).get("params") or {}).get("vectors") or {}
        out[name] = {
            "present": True,
            "points": info.get("points_count"),
            "status": info.get("status"),
            "vector_size": vectors.get("size"),
            "distance": vectors.get("distance"),
        }
    return out


def cmd_qdrant_facts(args: argparse.Namespace) -> int:
    print(dump_json(collect_qdrant_facts(args.base, args.collections)), end="")
    return 0


def collect_ollama_facts(base: str, models: list[str]) -> dict:
    out: dict[str, Any] = {"digests": {}, "embedding_length": None}
    try:
        tags = http_json(f"{base}/api/tags").get("models", [])
    except (urllib.error.URLError, urllib.error.HTTPError):
        return out
    by_name = {m.get("name", ""): m for m in tags}
    for want in models:
        entry = by_name.get(want) or by_name.get(f"{want}:latest")
        digest = (entry or {}).get("digest", "")
        out["digests"][want] = digest.replace("sha256:", "") if digest else ""
    try:
        show = http_json(f"{base}/api/show", {"name": models[0]}) if models else {}
        info = show.get("model_info") or {}
        for key, val in info.items():
            if key.endswith("embedding_length"):
                out["embedding_length"] = val
                break
    except (urllib.error.URLError, urllib.error.HTTPError):
        pass
    return out


def cmd_ollama_facts(args: argparse.Namespace) -> int:
    print(dump_json(collect_ollama_facts(args.base, args.models)), end="")
    return 0


# --------------------------------------------------------------------------
# retrieval baseline and parity
# --------------------------------------------------------------------------
def chunk_identity(chunk: dict) -> str:
    """Content-derived chunk identity.

    The chat trace exposes no chunk primary key, so identity is composed from
    content that a correct restore preserves byte-for-byte: url, heading, and a
    text prefix. Surrogate ids are preserved by pg_restore but are not visible
    through the API, so they cannot be used here.
    """
    parts = (
        str(chunk.get("url", "")),
        str(chunk.get("heading", "")),
        str(chunk.get("text_preview", ""))[:120],
    )
    return sha256_text("\x1f".join(parts))[:16]


def login(base: str, user: str, password: str) -> str:
    return http_json(f"{base}/api/auth/login", {"username": user, "password": password})["access_token"]


def capture_baseline(base: str, user: str, password: str, golden: str, top_k: int) -> dict:
    fixture = json.loads(Path(golden).read_text(encoding="utf-8"))
    queries = fixture.get("queries", [])
    if not queries:
        die(f"golden fixture has no queries: {golden}")
    token = login(base, user, password)
    records = []
    for item in queries:
        qid = item.get("id", "")
        text = item.get("query", "")
        resp = http_json(
            f"{base}/api/chat",
            {"message": text, "debug": True, "bypass_cache": True},
            token=token,
            timeout=300,
        )
        chunks = (resp.get("trace") or {}).get("retrieved_chunks") or []
        top = [
            {"identity": chunk_identity(c), "final_score": round(float(c.get("final_score") or 0.0), 6)}
            for c in chunks[:top_k]
        ]
        records.append({"id": qid, "query": text, "top": top, "retrieved_total": len(chunks)})
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "captured_at": now_iso(),
        "golden_fixture": str(golden),
        "query_count": len(records),
        "top_k": top_k,
        "identity_scheme": "sha256(url|heading|text_preview[:120])[:16]",
        "queries": records,
    }


def cmd_baseline_capture(args: argparse.Namespace) -> int:
    data = capture_baseline(args.base, args.user, args.password, args.golden, args.top_k)
    write_atomic(Path(args.out), dump_json(data))
    print(f"OK: retrieval baseline captured ({data['query_count']} queries) → {args.out}")
    return 0


def compare_baseline(expected: dict, actual: dict) -> dict:
    exp = {q["id"]: q for q in expected.get("queries", [])}
    act = {q["id"]: q for q in actual.get("queries", [])}
    total = len(exp)
    rank1_ok = 0
    top3_ok = 0
    score_violations: list[dict] = []
    per_query = []
    for qid, e in exp.items():
        a = act.get(qid)
        e_top = e.get("top", [])
        a_top = (a or {}).get("top", [])
        e_ids = [t["identity"] for t in e_top]
        a_ids = [t["identity"] for t in a_top]
        r1 = bool(e_ids) and bool(a_ids) and e_ids[0] == a_ids[0]
        t3 = set(e_ids[:3]) == set(a_ids[:3])
        rank1_ok += 1 if r1 else 0
        top3_ok += 1 if t3 else 0
        a_scores = {t["identity"]: t["final_score"] for t in a_top}
        worst = 0.0
        for t in e_top:
            if t["identity"] in a_scores:
                delta = abs(a_scores[t["identity"]] - t["final_score"])
                worst = max(worst, delta)
                if delta > PARITY_SCORE_TOLERANCE:
                    score_violations.append(
                        {"id": qid, "identity": t["identity"], "delta": round(delta, 6)}
                    )
        per_query.append(
            {"id": qid, "rank1": r1, "top3": t3, "worst_score_delta": round(worst, 6),
             "missing": a is None}
        )
    rank1_required = int(round(total * PARITY_RANK1_REQUIRED_RATIO))
    passed = (
        total > 0
        and rank1_ok >= rank1_required
        and top3_ok >= min(PARITY_TOP3_MIN_MATCHES, total)
        and not score_violations
    )
    return {
        "total": total,
        "rank1_matches": rank1_ok,
        "rank1_required": rank1_required,
        "top3_matches": top3_ok,
        "top3_required": min(PARITY_TOP3_MIN_MATCHES, total),
        "score_tolerance": PARITY_SCORE_TOLERANCE,
        "score_violations": score_violations,
        "passed": passed,
        "per_query": per_query,
    }


def cmd_baseline_compare(args: argparse.Namespace) -> int:
    expected = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
    result = compare_baseline(expected, actual)
    write_atomic(Path(args.out), dump_json(result))
    print(
        f"retrieval parity: rank1 {result['rank1_matches']}/{result['total']} "
        f"top3 {result['top3_matches']}/{result['total']} "
        f"violations {len(result['score_violations'])}"
    )
    return 0 if result["passed"] else 1


# --------------------------------------------------------------------------
# bundle manifest
# --------------------------------------------------------------------------
def cmd_bundle_manifest(args: argparse.Namespace) -> int:
    db = json.loads(Path(args.db_facts).read_text(encoding="utf-8"))
    qd = json.loads(Path(args.qdrant_facts).read_text(encoding="utf-8"))
    ol = json.loads(Path(args.ollama_facts).read_text(encoding="utf-8"))
    baseline = Path(args.baseline)

    dump = Path(args.dump)
    if not dump.is_file():
        die(f"dump missing: {dump}")

    snapshots = []
    for spec in args.snapshot or []:
        name, path = spec.split("=", 1)
        p = Path(path)
        if not p.is_file():
            die(f"snapshot missing: {p}")
        snapshots.append(
            {
                "collection": name,
                "filename": p.name,
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
        )

    knowledge = qd.get("site_knowledge") or {}
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "migration_id": args.migration_id,
        "captured_at": now_iso(),
        "source_hostname": args.source_hostname,
        "operator": args.operator,
        "release": args.release,
        "c_cut": args.c_cut,
        "alembic_revision": db.get("alembic_revision"),
        "database_name": db.get("database_name"),
        "dump": {
            "filename": dump.name,
            "bytes": dump.stat().st_size,
            "sha256": sha256_file(dump),
        },
        "qdrant_snapshots": snapshots,
        "answer_cache_decision": "recreate-empty (1024/Cosine)",
        "counts": {
            "sources": db.get("sources"),
            "chunks": db.get("chunks"),
            "claims": db.get("claims"),
            "observations": db.get("observations"),
            "evidence_links": db.get("evidence_links"),
            "chat_messages": db.get("chat_messages"),
            "answer_traces": db.get("answer_traces"),
        },
        "chat_messages_max_created_at": db.get("chat_messages_max_created_at"),
        "answer_traces_max_created_at": db.get("answer_traces_max_created_at"),
        "knowledge_version": db.get("knowledge_version"),
        "memory_version": db.get("memory_version"),
        "qdrant": {
            "points": knowledge.get("points"),
            "vector_size": knowledge.get("vector_size"),
            "distance": knowledge.get("distance"),
        },
        "models": {
            "digests": ol.get("digests", {}),
            "embedding_length": ol.get("embedding_length"),
        },
        "feature_flags": db.get("feature_flags", {}),
        "retrieval_baseline_sha256": sha256_file(baseline) if baseline.is_file() else "",
        "postgres": {
            "lc_collate": db.get("lc_collate"),
            "encoding": db.get("encoding"),
            "server_version": db.get("server_version"),
        },
    }
    write_atomic(Path(args.out_json), dump_json(manifest))
    write_atomic(Path(args.out_md), manifest_markdown(manifest))
    print(f"OK: bundle manifest → {args.out_json}")
    return 0


def manifest_markdown(m: dict) -> str:
    lines = [
        "# Migration bundle manifest",
        "",
        f"- migration id: `{m['migration_id']}`",
        f"- captured: {m['captured_at']}",
        f"- source host: {m['source_hostname']}",
        f"- operator: {m['operator']}",
        f"- release: {m['release']}",
        f"- cutover commit: `{m['c_cut']}`",
        f"- alembic revision: `{m['alembic_revision']}`",
        f"- database: `{m['database_name']}`",
        "",
        "## Payload",
        "",
        "| Artifact | Bytes | SHA256 |",
        "|---|---|---|",
        f"| {m['dump']['filename']} | {m['dump']['bytes']} | `{m['dump']['sha256']}` |",
    ]
    for s in m.get("qdrant_snapshots", []):
        lines.append(f"| {s['filename']} | {s['bytes']} | `{s['sha256']}` |")
    lines += [
        "",
        "## Expected state on the target",
        "",
        "| Fact | Expected |",
        "|---|---|",
    ]
    for key, val in sorted(m.get("counts", {}).items()):
        lines.append(f"| {key} | {val} |")
    lines += [
        f"| knowledge_version | {m.get('knowledge_version')} |",
        f"| memory_version | {m.get('memory_version')} |",
        f"| qdrant points | {(m.get('qdrant') or {}).get('points')} |",
        f"| vector size | {(m.get('qdrant') or {}).get('vector_size')} |",
        f"| distance | {(m.get('qdrant') or {}).get('distance')} |",
        f"| embedding length | {(m.get('models') or {}).get('embedding_length')} |",
        "",
        "The operator compares none of these by hand; the target evaluates them.",
        "",
    ]
    return "\n".join(lines)


def cmd_bundle_verify(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    bundle = Path(args.bundle)
    problems = []

    if manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        problems.append(
            f"manifest schema {manifest.get('manifest_schema_version')!r} != {MANIFEST_SCHEMA_VERSION}"
        )
    if args.migration_id and manifest.get("migration_id") != args.migration_id:
        problems.append(
            f"migration id {manifest.get('migration_id')!r} != expected {args.migration_id!r}"
        )

    dump = bundle / manifest["dump"]["filename"]
    if not dump.is_file():
        problems.append(f"dump missing from bundle: {dump.name}")
    else:
        actual = sha256_file(dump)
        if actual != manifest["dump"]["sha256"]:
            problems.append(f"dump sha256 mismatch for {dump.name}")
        if dump.stat().st_size != manifest["dump"]["bytes"]:
            problems.append(f"dump byte size mismatch for {dump.name}")

    for s in manifest.get("qdrant_snapshots", []):
        p = bundle / s["filename"]
        if not p.is_file():
            problems.append(f"snapshot missing from bundle: {s['filename']}")
            continue
        if sha256_file(p) != s["sha256"]:
            problems.append(f"snapshot sha256 mismatch for {s['filename']}")

    baseline = bundle / "retrieval-baseline.json"
    if manifest.get("retrieval_baseline_sha256"):
        if not baseline.is_file():
            problems.append("retrieval-baseline.json missing from bundle")
        elif sha256_file(baseline) != manifest["retrieval_baseline_sha256"]:
            problems.append("retrieval baseline sha256 mismatch")

    if problems:
        for p in problems:
            print(f"BUNDLE INVALID: {p}", file=sys.stderr)
        return 1
    print(f"OK: bundle verified (migration {manifest['migration_id']})")
    return 0


# --------------------------------------------------------------------------
# acceptance report
# --------------------------------------------------------------------------
def build_criteria(manifest: dict, actual: dict, parity: dict | None) -> list[dict]:
    rows: list[dict] = []

    def add(name: str, expected: Any, got: Any) -> None:
        rows.append(
            {
                "criterion": name,
                "expected": "" if expected is None else str(expected),
                "actual": "" if got is None else str(got),
                "result": "PASS" if str(expected) == str(got) else "FAIL",
            }
        )

    db = actual.get("db", {})
    qd = (actual.get("qdrant") or {}).get("site_knowledge", {}) or {}
    cache = (actual.get("qdrant") or {}).get("site_knowledge_answer_cache", {}) or {}
    ol = actual.get("ollama", {})

    add("alembic revision", manifest.get("alembic_revision"), db.get("alembic_revision"))
    for key, expected in sorted((manifest.get("counts") or {}).items()):
        add(key, expected, db.get(key))
    add("chat_messages max(created_at)", manifest.get("chat_messages_max_created_at"),
        db.get("chat_messages_max_created_at"))
    add("answer_traces max(created_at)", manifest.get("answer_traces_max_created_at"),
        db.get("answer_traces_max_created_at"))
    add("knowledge_version", manifest.get("knowledge_version"), db.get("knowledge_version"))
    add("memory_version", manifest.get("memory_version"), db.get("memory_version"))

    mq = manifest.get("qdrant") or {}
    add("qdrant points", mq.get("points"), qd.get("points"))
    add("qdrant vector size", mq.get("vector_size"), qd.get("vector_size"))
    add("qdrant distance", mq.get("distance"), qd.get("distance"))
    add("qdrant status", "green", qd.get("status"))
    add("answer cache present", True, cache.get("present"))
    add("answer cache vector size", mq.get("vector_size"), cache.get("vector_size"))

    for model, digest in sorted(((manifest.get("models") or {}).get("digests") or {}).items()):
        add(f"{model} digest", digest, (ol.get("digests") or {}).get(model))
    add("embedding length", (manifest.get("models") or {}).get("embedding_length"),
        ol.get("embedding_length"))

    for flag, expected in sorted((manifest.get("feature_flags") or {}).items()):
        add(f"flag {flag}", expected, (db.get("feature_flags") or {}).get(flag))

    pg = manifest.get("postgres") or {}
    add("lc_collate", pg.get("lc_collate"), db.get("lc_collate"))
    add("encoding", pg.get("encoding"), db.get("encoding"))

    add("deployed commit", manifest.get("c_cut"), actual.get("deployed_commit"))
    add("release", manifest.get("release"), actual.get("release"))

    for name, key in (
        ("health", "health"),
        ("smoke", "smoke"),
        ("verify-release", "verify_release"),
    ):
        add(name, "pass", actual.get(key))

    if parity is not None:
        rows.append(
            {
                "criterion": "retrieval rank-1",
                "expected": f"{parity['rank1_required']}/{parity['total']}",
                "actual": f"{parity['rank1_matches']}/{parity['total']}",
                "result": "PASS" if parity["rank1_matches"] >= parity["rank1_required"] else "FAIL",
            }
        )
        rows.append(
            {
                "criterion": "retrieval top-3",
                "expected": f">={parity['top3_required']}/{parity['total']}",
                "actual": f"{parity['top3_matches']}/{parity['total']}",
                "result": "PASS" if parity["top3_matches"] >= parity["top3_required"] else "FAIL",
            }
        )
        rows.append(
            {
                "criterion": "retrieval score drift",
                "expected": f"<={parity['score_tolerance']}",
                "actual": f"{len(parity['score_violations'])} violation(s)",
                "result": "PASS" if not parity["score_violations"] else "FAIL",
            }
        )
    return rows


def cmd_accept_report(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
    parity = None
    if args.parity and Path(args.parity).is_file():
        parity = json.loads(Path(args.parity).read_text(encoding="utf-8"))

    rows = build_criteria(manifest, actual, parity)
    failed = [r for r in rows if r["result"] != "PASS"]
    overall = "PASS" if not failed else "FAIL"

    report = {
        "migration_id": manifest.get("migration_id"),
        "evaluated_at": now_iso(),
        "criteria_total": len(rows),
        "criteria_passed": len(rows) - len(failed),
        "result": overall,
        "criteria": rows,
    }
    write_atomic(Path(args.out_json), dump_json(report))

    width = max((len(r["criterion"]) for r in rows), default=20) + 2
    ew = max((len(r["expected"]) for r in rows), default=8) + 2
    ew = min(ew, 34)
    aw = ew
    lines = [f"ACCEPTANCE — {len(rows)} criteria", ""]
    lines.append(f"{'CRITERION'.ljust(width)}{'EXPECTED'.ljust(ew)}{'ACTUAL'.ljust(aw)}RESULT")
    for r in rows:
        lines.append(
            f"{r['criterion'].ljust(width)}"
            f"{r['expected'][:ew - 2].ljust(ew)}"
            f"{r['actual'][:aw - 2].ljust(aw)}"
            f"{r['result']}"
        )
    lines += ["", f"RESULT: {overall} ({report['criteria_passed']}/{len(rows)})", ""]
    text = "\n".join(lines)
    write_atomic(Path(args.out_md), text)
    print(text)
    return 0 if overall == "PASS" else 1


# --------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="migrate_machine.py", add_help=True)
    sub = ap.add_subparsers(dest="op", required=True)

    p = sub.add_parser("state-init"); p.add_argument("--dir", required=True)
    p.add_argument("--role", required=True); p.add_argument("--migration-id", required=True)
    p.add_argument("--source-hostname", default=""); p.add_argument("--target-hostname", default="")
    p.set_defaults(func=cmd_state_init)

    p = sub.add_parser("state-get"); p.add_argument("--dir", required=True)
    p.add_argument("--key", required=True); p.add_argument("--optional", action="store_true")
    p.set_defaults(func=cmd_state_get)

    p = sub.add_parser("state-set"); p.add_argument("--dir", required=True)
    p.add_argument("pairs", nargs="+"); p.set_defaults(func=cmd_state_set)

    p = sub.add_parser("state-complete"); p.add_argument("--dir", required=True)
    p.add_argument("--phase", required=True); p.set_defaults(func=cmd_state_complete)

    p = sub.add_parser("state-confirm"); p.add_argument("--dir", required=True)
    p.add_argument("--word", required=True); p.set_defaults(func=cmd_state_confirm)

    p = sub.add_parser("state-has-confirm"); p.add_argument("--dir", required=True)
    p.add_argument("--word", required=True); p.set_defaults(func=cmd_state_has_confirm)

    p = sub.add_parser("state-show"); p.add_argument("--dir", required=True)
    p.set_defaults(func=cmd_state_show)

    p = sub.add_parser("db-facts"); p.add_argument("--url", required=True)
    p.set_defaults(func=cmd_db_facts)

    p = sub.add_parser("db-ping"); p.add_argument("--url", required=True)
    p.set_defaults(func=cmd_db_ping)

    p = sub.add_parser("qdrant-facts"); p.add_argument("--base", required=True)
    p.add_argument("--collections", nargs="+", required=True); p.set_defaults(func=cmd_qdrant_facts)

    p = sub.add_parser("ollama-facts"); p.add_argument("--base", required=True)
    p.add_argument("--models", nargs="+", required=True); p.set_defaults(func=cmd_ollama_facts)

    p = sub.add_parser("baseline-capture")
    p.add_argument("--base", required=True); p.add_argument("--user", required=True)
    p.add_argument("--password", required=True); p.add_argument("--golden", required=True)
    p.add_argument("--out", required=True); p.add_argument("--top-k", type=int, default=5)
    p.set_defaults(func=cmd_baseline_capture)

    p = sub.add_parser("baseline-compare"); p.add_argument("--baseline", required=True)
    p.add_argument("--actual", required=True); p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_baseline_compare)

    p = sub.add_parser("bundle-manifest")
    for flag in ("--migration-id", "--source-hostname", "--operator", "--release", "--c-cut",
                 "--db-facts", "--qdrant-facts", "--ollama-facts", "--dump", "--baseline",
                 "--out-json", "--out-md"):
        p.add_argument(flag, required=True)
    p.add_argument("--snapshot", action="append", default=[])
    p.set_defaults(func=cmd_bundle_manifest)

    p = sub.add_parser("bundle-verify"); p.add_argument("--bundle", required=True)
    p.add_argument("--manifest", required=True); p.add_argument("--migration-id", default="")
    p.set_defaults(func=cmd_bundle_verify)

    p = sub.add_parser("accept-report"); p.add_argument("--manifest", required=True)
    p.add_argument("--actual", required=True); p.add_argument("--parity", default="")
    p.add_argument("--out-json", required=True); p.add_argument("--out-md", required=True)
    p.set_defaults(func=cmd_accept_report)

    p = sub.add_parser("sha256"); p.add_argument("path"); p.set_defaults(
        func=lambda a: (print(sha256_file(a.path)), 0)[1]
    )

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
