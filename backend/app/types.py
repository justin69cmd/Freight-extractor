"""Database-portable column types.

Lets the same models run on Postgres+pgvector (production / Docker) and on
SQLite (zero-install local mode) without changes:

  GUID      -> native UUID on Postgres, CHAR(36) elsewhere
  Embedding -> pgvector Vector on Postgres, JSON list[float] elsewhere
              (SQLite has no vector index, so search falls back to Python cosine)
"""
from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, JSON, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID, always presented to Python as uuid.UUID."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class Embedding(TypeDecorator):
    """Vector column: pgvector on Postgres, JSON array elsewhere."""
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int, **kw):
        self.dim = dim
        super().__init__(**kw)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector  # imported only on Postgres
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        # list[float] works for both pgvector and JSON
        return list(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return list(value) if value is not None else None
