"""Vendor registry endpoints — config-driven onboarding (Requirement: no-code vendors)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.canonical.schemas import VendorCreate, VendorOut
from app.db import get_db

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get("", response_model=list[VendorOut])
async def list_vendors(db: Session = Depends(get_db)):
    return repo.list_vendors(db)


@router.post("", response_model=VendorOut, status_code=201)
async def create_vendor(body: VendorCreate, db: Session = Depends(get_db)):
    """Register a vendor; a YAML profile under vendor_profiles/ supplies extraction hints."""
    try:
        vendor = repo.create_vendor(
            db, name=body.name, code=body.code,
            profile_ref=body.profile_ref, aliases=body.aliases,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"vendor {body.name!r} already exists")
    return vendor
