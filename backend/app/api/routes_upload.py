"""Upload + agreement endpoints (Requirement 1)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.canonical.schemas import AgreementMetadataOut, ExtractedTableOut, UploadResponse
from app.core.tasks import process_agreement
from app.db import get_db
from app.storage import storage

router = APIRouter(prefix="/api/agreements", tags=["agreements"])


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_agreement(
    file: UploadFile = File(...),
    vendor_name: str = Form(default="Unknown Vendor"),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Accept a PDF, persist it, create job rows, and dispatch the pipeline (L0..L6)."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="only PDF uploads are supported")

    data = await file.read()
    storage_uri, sha = storage.save_bytes(data, suffix=".pdf", prefix="agreement_")

    vendor = repo.get_or_create_vendor(db, vendor_name)
    agreement = repo.create_agreement(
        db, vendor=vendor, filename=file.filename, storage_uri=storage_uri, sha256=sha
    )
    job = repo.create_job(db, agreement)
    db.commit()

    # Hand off to the worker; the API thread never does heavy PDF work.
    process_agreement.delay(str(job.id))

    return UploadResponse(job_id=job.id, agreement_id=agreement.id, status=job.status)


@router.get("/{agreement_id}/metadata", response_model=AgreementMetadataOut)
async def get_metadata(agreement_id: uuid.UUID, db: Session = Depends(get_db)):
    """Enhancement #1 — agreement metadata + clauses, stored separate from rates."""
    from sqlalchemy import select

    from app.canonical.models import AgreementMetadata, Clause

    meta = db.scalar(
        select(AgreementMetadata).where(AgreementMetadata.agreement_id == agreement_id)
    )
    if meta is None:
        raise HTTPException(status_code=404, detail="metadata not found (job may still be running)")
    clauses = db.scalars(select(Clause).where(Clause.agreement_id == agreement_id)).all()
    return AgreementMetadataOut(
        vendor_name=meta.vendor_name,
        effective_date=meta.effective_date,
        expiry_date=meta.expiry_date,
        payment_terms=meta.payment_terms,
        clauses=clauses,
    )


@router.get("/{agreement_id}/tables", response_model=list[ExtractedTableOut])
async def get_tables(agreement_id: uuid.UUID, db: Session = Depends(get_db)):
    """The raw extracted table grids — the source the rates were normalized from."""
    return repo.get_tables_for_agreement(db, agreement_id)
