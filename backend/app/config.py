"""Application settings, loaded from environment / .env.

All tunables (confidence-band thresholds, AI provider, storage) live here so that
behaviour can change without code edits — a core requirement of the platform.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="FREIGHT_", extra="ignore"
    )

    # --- core ---
    app_name: str = "Freight Agreement Intelligence Platform"
    environment: str = "development"
    debug: bool = True

    # --- persistence ---
    # Default = zero-install local mode (SQLite). Docker/production overrides this
    # with a Postgres+pgvector URL via the compose `environment` block.
    database_url: str = "sqlite:///./freight.db"
    redis_url: str = "redis://localhost:6379/0"

    # --- job execution -------------------------------------------------------
    # "thread" runs the pipeline in-process (no Redis/Celery needed) — used for
    # native local mode. "celery" dispatches to a worker — used in Docker/prod.
    job_executor: str = "thread"

    # --- object storage (PDFs, table crops, generated xlsx) ---
    storage_backend: str = "local"  # local | s3 | minio
    storage_root: str = "./_storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None

    # --- confidence bands (Enhancement #4) -----------------------------------
    # Numeric confidence -> band. Thresholds are configurable, never hardcoded
    # in business logic. A band drives pipeline routing (see core/confidence.py).
    band_high_min: float = 0.90   # >= this  -> HIGH  (auto-accept)
    band_medium_min: float = 0.75  # >= this  -> MEDIUM (AI validation gate)
    #                              # below    -> LOW    (forced human review)

    # --- AI validation gate (Enhancement #6 / Layer 3) -----------------------
    ai_provider: str = "anthropic"  # anthropic | openai
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ai_model_validation: str = "claude-opus-4-8"      # hard repair / zone inference
    ai_model_classify: str = "claude-haiku-4-5-20251001"  # cheap tiebreaks
    ai_per_job_call_budget: int = 50  # hard cap on LLM calls per agreement

    # --- RAG / embeddings (Enhancement #3) -----------------------------------
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # --- route expansion guardrail -------------------------------------------
    max_lanes_per_cell: int = 200  # explosion guard (likely a parse error beyond this)

    # --- review workflow (Enhancement #2) ------------------------------------
    # Rows in these bands cannot reach Excel export without human approval.
    review_required_bands: tuple[str, ...] = ("LOW",)
    review_required_if_ai_touched: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
