"""L6 — export orchestration with the human-review gate (Enhancement #2).

The gate is hard: export is refused while the job is not REVIEW_APPROVED, or
while any review task is unresolved. This is the structural guarantee that no
un-reviewed freight number reaches a Mankind output that finance pays against.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.canonical.schemas import ExportResponse
from app.core.enums import JobStatus
from app.core.exceptions import ExportError, ReviewBlockedError
from app.export.excel_writer import build_workbook
from app.storage import storage

# Statuses from which export is permitted (review already signed off).
_EXPORTABLE = {JobStatus.REVIEW_APPROVED, JobStatus.EXPORTING,
               JobStatus.SUCCEEDED, JobStatus.SUCCEEDED_WITH_FLAGS}


def enforce_review_gate(db: Session, job) -> None:
    """Raise ReviewBlockedError unless the job has cleared human review."""
    unresolved = repo.count_unresolved_review_tasks(db, job)
    if unresolved > 0:
        raise ReviewBlockedError(
            f"{unresolved} review task(s) unresolved — approve them before exporting"
        )
    if job.status not in _EXPORTABLE:
        raise ReviewBlockedError(
            f"job is {job.status.value}; export requires review approval (REVIEW_APPROVED)"
        )


def _build_bytes(db: Session, *, agreement_id, template: str, include_flagged: bool):
    """Gate-checked workbook build. Returns (xlsx_bytes, filename, job)."""
    agreement = repo.get_agreement(db, agreement_id)
    if agreement is None:
        raise ExportError("agreement not found")
    job = repo.get_job_by_agreement(db, agreement_id)
    if job is None:
        raise ExportError("no job for agreement")

    enforce_review_gate(db, job)

    rows = repo.get_rates_for_agreement(db, agreement_id)
    metadata = repo.get_metadata_for_agreement(db, agreement_id)
    clauses = repo.get_clauses_for_agreement(db, agreement_id)
    vendor_name = agreement.vendor.name if agreement.vendor else None

    wb = build_workbook(
        rows=rows, metadata=metadata, clauses=clauses,
        template_name=template, vendor_name=vendor_name, include_flagged=include_flagged,
    )
    buf = io.BytesIO()
    wb.save(buf)
    safe = "".join(c for c in (vendor_name or "vendor") if c.isalnum() or c in "-_") or "vendor"
    filename = f"Mankind_{safe}_{datetime.now(timezone.utc):%Y%m%d}.xlsx"
    return buf.getvalue(), filename, job


def build_export_bytes(
    db: Session, *, agreement_id, template: str, include_flagged: bool
) -> tuple[bytes, str]:
    """For direct browser download — the client picks where to save the file."""
    data, filename, _job = _build_bytes(
        db, agreement_id=agreement_id, template=template, include_flagged=include_flagged
    )
    return data, filename


def generate_and_store(
    db: Session, *, agreement_id, template: str, include_flagged: bool
) -> ExportResponse:
    """Generate + persist a copy server-side (object store)."""
    job0 = repo.get_job_by_agreement(db, agreement_id)
    if job0 is not None:
        repo.update_job(db, job0, status=JobStatus.EXPORTING, stage_detail="generating Excel", progress=0.95)
        db.commit()

    data, _filename, job = _build_bytes(
        db, agreement_id=agreement_id, template=template, include_flagged=include_flagged
    )
    storage_uri, _ = storage.save_bytes(data, suffix=".xlsx", prefix="mankind_")

    final = JobStatus.SUCCEEDED_WITH_FLAGS if job.flags_count else JobStatus.SUCCEEDED
    repo.update_job(db, job, status=final, stage_detail="export complete", progress=1.0)
    db.commit()

    return ExportResponse(download_uri=storage_uri, generated_at=datetime.now(timezone.utc))
