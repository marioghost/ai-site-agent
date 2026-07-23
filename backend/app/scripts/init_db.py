"""Apply database migrations (Alembic) — PostgreSQL only.

Run during deploy/redeploy:

    python -m app.scripts.init_db

This runs ``alembic upgrade head`` against the configured PostgreSQL
``DATABASE_URL``. It is safe to run repeatedly. There is no SQLite support and
no runtime table auto-creation — the schema is owned by Alembic migrations.
"""
from __future__ import annotations

from app.core.alembic_config import upgrade_to_head
from app.core.database import current_db_revision
from app.core.logging import configure_logging, get_logger


def main() -> None:
    configure_logging()
    logger = get_logger(__name__)
    logger.info("Applying database migrations (alembic upgrade head)")
    upgrade_to_head()
    logger.info("Database schema is up to date (revision %s)", current_db_revision())


if __name__ == "__main__":
    main()
