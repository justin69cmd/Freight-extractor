"""Mankind Excel export endpoints (Requirement 6).

Guarded by the review gate (Enhancement #2): raises ReviewBlockedError if the
job has unresolved review tasks.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.canonical.schemas import ExportRequest, ExportResponse
from app.db import get_db
from app.export.export_service import build_export_bytes, generate_and_store

router = APIRouter(prefix="/api/agreements", tags=["export"])

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/{agreement_id}/export", response_model=ExportResponse)
async def export_excel(
    agreement_id: uuid.UUID, body: ExportRequest, db: Session = Depends(get_db)
):
    """Generate + store the Mankind Excel server-side (saved copy).

    Raises 409 (ReviewBlockedError) if the job has not cleared human review.
    """
    return generate_and_store(
        db,
        agreement_id=agreement_id,
        template=body.template,
        include_flagged=body.include_flagged,
    )


@router.get("/{agreement_id}/export/download")
async def download_excel(
    agreement_id: uuid.UUID,
    template: str = Query(default="mankind_default_v2"),
    include_flagged: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Stream the Excel to the browser so the user chooses where to save it.

    Same review gate as the stored export (409 if unresolved). The browser's
    Save dialog / File System Access picker determines the save location.
    """
    data, filename = build_export_bytes(
        db, agreement_id=agreement_id, template=template, include_flagged=include_flagged
    )
    return Response(
        content=data,
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
