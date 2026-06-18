"""Celery task wrappers around the pipeline.

The task owns its own DB session (workers are separate processes from the API).
"""
from __future__ import annotations

import uuid

from app.core.celery_app import celery_app
from app.core.pipeline import run_pipeline
from app.db import SessionLocal


@celery_app.task(name="freight.process_agreement", bind=True, max_retries=2)
def process_agreement(self, job_id: str) -> str:
    """Entry point enqueued on upload. Retries transient failures with backoff."""
    db = SessionLocal()
    try:
        run_pipeline(db, uuid.UUID(job_id))
        return job_id
    except Exception as exc:  # noqa: BLE001 — Celery retry on transient errors
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()
