"""Celery application — async pipeline execution.

Heavy PDF/OCR/AI work runs here, never in the request thread. Pipeline tasks
(L0–L6) are registered in later phases; the app + config live here from Phase 2.
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "freight",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.core.tasks"],  # register pipeline tasks with the worker
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,           # resume-safe: re-deliver if a worker dies
    worker_prefetch_multiplier=1,  # long jobs -> don't hoard tasks
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
