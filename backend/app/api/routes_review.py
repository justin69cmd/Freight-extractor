"""Human review workflow endpoints (Enhancement #2).

Export is hard-gated: a job cannot leave REVIEW_PENDING until every ReviewTask
is resolved and an approver signs off.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.canonical.schemas import (
    ReviewApproveIn,
    ReviewCorrectionIn,
    ReviewTaskOut,
)
from app.db import get_db

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/jobs/{job_id}/tasks", response_model=list[ReviewTaskOut])
async def list_review_tasks(
    job_id: uuid.UUID, only_open: bool = True, db: Session = Depends(get_db)
):
    """Items (rates/clauses/metadata) flagged for human verification."""
    return repo.list_review_tasks_for_job(db, job_id, only_open=only_open)


@router.patch("/tasks/{task_id}", response_model=ReviewTaskOut)
async def correct_item(
    task_id: uuid.UUID, body: ReviewCorrectionIn, db: Session = Depends(get_db)
):
    """Apply a human correction; feeds the pattern-learning store (Enhancement #5)."""
    task = repo.get_review_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="review task not found")
    if task.resolved:
        raise HTTPException(status_code=409, detail="task already resolved")
    task = repo.apply_review_correction(
        db, task=task, field=body.field, new_value=body.new_value, corrected_by=body.corrected_by
    )
    db.commit()
    return task


@router.post("/jobs/{job_id}/approve")
async def approve_job(
    job_id: uuid.UUID, body: ReviewApproveIn, db: Session = Depends(get_db)
):
    """Sign off review -> REVIEW_PENDING to REVIEW_APPROVED, unblocking export."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    job = repo.approve_job(db, job=job, approved_by=body.approved_by)
    db.commit()
    return {"job_id": str(job.id), "status": job.status.value, "approved_by": body.approved_by}
