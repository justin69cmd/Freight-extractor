"""Database bootstrap — create the pgvector extension and all tables.

For production use Alembic migrations (`alembic upgrade head`). This script is a
fast path for local/dev and CI: it ensures the `vector` extension exists, then
creates every table from the ORM metadata. Idempotent (create-if-not-exists).

    python -m scripts.init_db
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.canonical import models  # noqa: F401 — register all tables on Base.metadata
from app.core.logging import setup_logging
from app.db import Base, engine

log = logging.getLogger("freight.init_db")


def main() -> None:
    setup_logging()
    # pgvector extension only exists on Postgres; SQLite (local mode) skips it.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    log.info("database initialized (%s): %d tables", engine.dialect.name, len(Base.metadata.tables))


if __name__ == "__main__":
    main()
