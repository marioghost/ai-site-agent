#!/usr/bin/env python3
"""Read-only validation of a restored recovery database."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def load_env(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", default="ai_site_agent_recovery")
    ap.add_argument("--env-file", default="/opt/ai-site-agent/.env")
    args = ap.parse_args()

    env = load_env(Path(args.env_file))
    base = make_url(env["DATABASE_URL"]).set(database=args.database)
    url = base.render_as_string(hide_password=False)
    engine = create_engine(url, future=True)
    report: dict = {"database": args.database}
    with engine.connect() as conn:
        report["current_database"] = conn.execute(text("SELECT current_database()")).scalar()
        report["alembic_revision"] = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        report["sources"] = conn.execute(text("SELECT COUNT(*) FROM sources")).scalar()
        report["chunks"] = conn.execute(text("SELECT COUNT(*) FROM chunks")).scalar()
        report["users"] = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        report["settings"] = conn.execute(text("SELECT COUNT(*) FROM settings")).scalar()
        report["fixture_example"] = conn.execute(
            text("SELECT COUNT(*) FROM sources WHERE url ILIKE '%fixture.example%'")
        ).scalar()
        report["real_urls"] = conn.execute(
            text(
                "SELECT COUNT(*) FROM sources WHERE COALESCE(url,'') NOT ILIKE '%fixture.example%'"
            )
        ).scalar()
        age = conn.execute(
            text(
                "SELECT MIN(first_seen_at), MAX(first_seen_at), MIN(id), MAX(id) FROM sources"
            )
        ).one()
        report["oldest_first_seen"] = str(age[0])
        report["newest_first_seen"] = str(age[1])
        report["min_id"] = age[2]
        report["max_id"] = age[3]
        ukr = conn.execute(
            text(
                "SELECT id, url FROM sources WHERE url ILIKE '%ukrsibbank.com%' "
                "ORDER BY id LIMIT 5"
            )
        ).all()
        report["sample_ukrsib"] = [{"id": r[0], "url": r[1]} for r in ukr]
    engine.dispose()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["fixture_example"] != 0:
        print("WARN: fixture.example rows present", file=sys.stderr)
        return 2
    if report["sources"] < 1000:
        print("WARN: unexpectedly low source count", file=sys.stderr)
        return 2
    print("VALIDATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
