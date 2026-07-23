"""PostgreSQL-specific schema extras not expressible via the ORM models.

Currently this is the full-text ``search_vector`` column on ``chunks`` (a
``tsvector`` generated column) and its GIN index, used by the lexical retrieval
path (:mod:`app.services.lexical_index_service`).

Kept here as a single source of truth so both the Alembic migration and the
test/dev schema helper apply exactly the same DDL. All statements are
idempotent.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

# 'simple' config: no language-specific stemming/stopwords, just unicode-aware
# lowercasing. Best fit for Ukrainian + mixed-language content.
ADD_SEARCH_VECTOR = """
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS search_vector tsvector
GENERATED ALWAYS AS (
    setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(heading, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(text, '')), 'C')
) STORED
"""

CREATE_SEARCH_VECTOR_INDEX = (
    "CREATE INDEX IF NOT EXISTS ix_chunks_search_vector "
    "ON chunks USING gin (search_vector)"
)

DROP_SEARCH_VECTOR_INDEX = "DROP INDEX IF EXISTS ix_chunks_search_vector"
DROP_SEARCH_VECTOR = "ALTER TABLE chunks DROP COLUMN IF EXISTS search_vector"


def apply_fulltext_extras(conn: Connection) -> None:
    """Create the chunks full-text column + GIN index (idempotent)."""
    conn.execute(text(ADD_SEARCH_VECTOR))
    conn.execute(text(CREATE_SEARCH_VECTOR_INDEX))


def drop_fulltext_extras(conn: Connection) -> None:
    conn.execute(text(DROP_SEARCH_VECTOR_INDEX))
    conn.execute(text(DROP_SEARCH_VECTOR))
