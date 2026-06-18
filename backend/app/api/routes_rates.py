"""Rate query + provenance endpoints (Enhancement #6 traceability)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.canonical.schemas import RateOut, RateProvenanceOut
from app.core.enums import TransportMode
from app.db import get_db

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("", response_model=list[RateOut])
async def list_rates(
    origin: str | None = Query(default=None),
    destination: str | None = Query(default=None),
    mode: TransportMode | None = Query(default=None),
    vendor_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Structured (non-AI) filter query over canonical rates."""
    return repo.query_rates(
        db, origin=origin, destination=destination, mode=mode, vendor_id=vendor_id
    )


@router.get("/{rate_id}/provenance", response_model=RateProvenanceOut)
async def get_rate_provenance(rate_id: uuid.UUID, db: Session = Depends(get_db)):
    """Enhancement #6 — full trace: agreement -> page -> table -> cell -> confidence."""
    rate = repo.get_rate(db, rate_id)
    if rate is None:
        raise HTTPException(status_code=404, detail="rate not found")
    return rate
