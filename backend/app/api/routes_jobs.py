"""Job status + progress endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.canonical.schemas import JobOut
from app.db import get_db

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Poll pipeline status. (WebSocket stream added in Phase 9.)"""
    job = repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
