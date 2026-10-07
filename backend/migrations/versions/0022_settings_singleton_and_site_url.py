"""Enforce singleton Settings row; backfill site_url from indexed corpus.

Release 1.1 Wave A — runtime truth.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

import sqlalchemy as sa
from alembic import op

revision = "0022_settings_singleton_and_site_url"
down_revision = "0021_knowledge_understanding_phase0"
branch_labels = None
depends_on = None


def _origin_from_url(url: str) -> str | None:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{parsed.scheme.lower()}://{host}"


def upgrade() -> None:
    conn = op.get_bind()

    # Keep the lowest-id settings row (application always reads ORDER BY id LIMIT 1).
    conn.execute(
        sa.text(
            "DELETE FROM settings WHERE id NOT IN (SELECT MIN(id) FROM settings)"
        )
    )

    # Prevent a second settings row (PostgreSQL expression unique index).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_settings_singleton ON settings ((true))"
    )

    row = conn.execute(
        sa.text(
            "SELECT id, site_url FROM settings ORDER BY id ASC LIMIT 1"
        )
    ).mappings().first()
    if row is None:
        return
    if (row["site_url"] or "").strip():
        return

    urls = conn.execute(
        sa.text(
            "SELECT url FROM sources "
            "WHERE indexed_at IS NOT NULL AND url IS NOT NULL "
            "LIMIT 5000"
        )
    ).scalars().all()
    origins: Counter[str] = Counter()
    for url in urls:
        origin = _origin_from_url(url or "")
        if origin:
            origins[origin] += 1
    if not origins:
        return
    site_url = origins.most_common(1)[0][0]
    conn.execute(
        sa.text("UPDATE settings SET site_url = :u WHERE id = :id"),
        {"u": site_url, "id": row["id"]},
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_settings_singleton")
