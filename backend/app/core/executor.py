"""Pipeline dispatch — abstracts away how a job runs.

  thread  : run in-process on a background thread (local mode; no Redis/Celery)
  celery  : dispatch to a Celery worker (Docker/production)

Selected by `settings.job_executor`, so the upload endpoint never knows which.
Celery is imported lazily so local mode doesn't need it installed.
"""
from __future__ import annotations

import logging
import threading
import uuid

from app.config import settings

log = logging.getLogger("freight.executor")


def dispatch_pipeline(job_id: uuid.UUID) -> None:
    if settings.job_executor == "celery":
        from app.core.tasks import process_agreement  # lazy: needs celery installed

        process_agreement.delay(str(job_id))
        return
    # thread mode (default)
    threading.Thread(target=_run_thread, args=(str(job_id),), daemon=True).start()


def _run_thread(job_id: str) -> None:
    from app.core.pipeline import run_pipeline
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        run_pipeline(db, uuid.UUID(job_id))
    except Exception:  # noqa: BLE001 — pipeline already records failure on the job
        log.exception("threaded pipeline failed for job %s", job_id)
    finally:
        db.close()
