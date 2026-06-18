"""Data-access helpers — keep ORM queries out of routes and the pipeline."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import date, datetime, timezone

from app.canonical.models import (
    Agreement,
    AgreementMetadata,
    CanonicalRate,
    Clause,
    ExtractedTable,
    Job,
    ReviewCorrection,
    ReviewTask,
    Vendor,
    ZoneMapping,
)
from app.core.confidence import needs_human_review, to_band
from app.core.enums import (
    JobStatus,
    PageKind,
    PricingPattern,
    ReviewItemKind,
    ValidationStatus,
)
from app.extraction.raw_table import RawTable
from app.metadata.metadata_extractor import MetadataResult
from app.normalization.canonical_row import CanonicalRow
from app.normalization.zone_resolver import ZoneMapRow


def get_or_create_vendor(db: Session, name: str) -> Vendor:
    vendor = db.scalar(select(Vendor).where(Vendor.name == name))
    if vendor is None:
        vendor = Vendor(name=name)
        db.add(vendor)
        db.flush()
    return vendor


def list_vendors(db: Session) -> list[Vendor]:
    return list(db.scalars(select(Vendor).order_by(Vendor.name)))


def create_vendor(
    db: Session, *, name: str, code: str | None = None,
    profile_ref: str | None = None, aliases: dict | None = None,
) -> Vendor:
    vendor = Vendor(name=name, code=code, profile_ref=profile_ref, aliases=aliases)
    db.add(vendor)
    db.flush()
    return vendor


def create_agreement(
    db: Session, *, vendor: Vendor, filename: str, storage_uri: str, sha256: str
) -> Agreement:
    agreement = Agreement(
        vendor_id=vendor.id,
        original_filename=filename,
        storage_uri=storage_uri,
        sha256=sha256,
    )
    db.add(agreement)
    db.flush()
    return agreement


def create_job(db: Session, agreement: Agreement) -> Job:
    job = Job(agreement_id=agreement.id, status=JobStatus.QUEUED)
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: uuid.UUID) -> Job | None:
    return db.get(Job, job_id)


def update_job(
    db: Session,
    job: Job,
    *,
    status: JobStatus | None = None,
    stage_detail: str | None = None,
    progress: float | None = None,
    error: str | None = None,
) -> Job:
    if status is not None:
        job.status = status
    if stage_detail is not None:
        job.stage_detail = stage_detail
    if progress is not None:
        job.progress = progress
    if error is not None:
        job.error = error
    db.add(job)
    db.flush()
    return job


def persist_extracted_table(
    db: Session, agreement: Agreement, table: RawTable
) -> ExtractedTable:
    """Store a RawTable + its provenance/fingerprint. Classification fills pattern later."""
    row = ExtractedTable(
        agreement_id=agreement.id,
        page_number=table.page_number,
        page_kind=PageKind(table.page_kind),
        bbox=table.bbox.model_dump() if table.bbox else None,
        cells=table.grid(),
        extraction_confidence=table.extraction_confidence,
        confidence_band=table.confidence_band,
        pattern=PricingPattern.UNKNOWN,
        fingerprint=table.fingerprint(),
    )
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Phase 5 — canonical rates, zone maps, metadata, clauses, review tasks
# --------------------------------------------------------------------------- #
def persist_canonical_rate(
    db: Session,
    *,
    agreement: Agreement,
    table_id,
    row: CanonicalRow,
) -> CanonicalRate:
    """Map a DB-free CanonicalRow onto the ORM, deriving its band + review status."""
    band = to_band(row.extraction_confidence)
    rate = CanonicalRate(
        agreement_id=agreement.id,
        vendor_id=agreement.vendor_id,
        table_id=table_id,
        transport_mode=row.transport_mode,
        source_pattern=row.source_pattern,
        origin=row.origin,
        destination=row.destination,
        origin_zone=row.origin_zone,
        destination_zone=row.destination_zone,
        origin_state=row.origin_state,
        destination_state=row.destination_state,
        rate_basis=row.rate_basis,
        rate_value=row.rate_value,
        currency=row.currency,
        min_charge=row.min_charge,
        min_weight_kg=row.min_weight_kg,
        vehicle_type=row.vehicle_type,
        vehicle_capacity_kg=row.vehicle_capacity_kg,
        weight_slab_min_kg=row.weight_slab_min_kg,
        weight_slab_max_kg=row.weight_slab_max_kg,
        service_level=row.service_level,
        temperature_band=row.temperature_band,
        fuel_surcharge_pct=row.fuel_surcharge_pct,
        docket_charge=row.docket_charge,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        source_page=row.source_page,
        source_bbox=row.source_bbox,
        source_cell=row.source_cell,
        extraction_confidence=row.extraction_confidence,
        confidence_band=band,
        validation_status=ValidationStatus.AI_VALIDATED if row.ai_touched else ValidationStatus.AUTO,
        ai_touched=row.ai_touched,
        ai_explanation=row.ai_explanation,
        raw_snapshot=row.raw_snapshot,
    )
    db.add(rate)
    db.flush()
    return rate


def persist_zone_mapping(
    db: Session, *, agreement: Agreement, zmap: ZoneMapRow
) -> ZoneMapping:
    row = ZoneMapping(
        agreement_id=agreement.id,
        vendor_id=agreement.vendor_id,
        state=zmap.state,
        zone=zmap.zone,
        source_page=zmap.source_page,
        source_cell=zmap.source_cell,
        extraction_confidence=zmap.extraction_confidence,
        confidence_band=to_band(zmap.extraction_confidence),
    )
    db.add(row)
    db.flush()
    return row


def persist_metadata(
    db: Session, *, agreement: Agreement, meta: MetadataResult
) -> AgreementMetadata:
    row = AgreementMetadata(
        agreement_id=agreement.id,
        vendor_name=meta.vendor_name,
        effective_date=meta.effective_date,
        expiry_date=meta.expiry_date,
        payment_terms=meta.payment_terms,
        source_page=meta.source_page,
        extraction_confidence=meta.extraction_confidence,
        confidence_band=to_band(meta.extraction_confidence),
    )
    db.add(row)
    db.flush()
    for clause in meta.clauses:
        db.add(
            Clause(
                agreement_id=agreement.id,
                clause_type=clause.clause_type,
                text=clause.text,
                summary=clause.summary,
                source_page=clause.source_page,
                extraction_confidence=clause.extraction_confidence,
                confidence_band=to_band(clause.extraction_confidence),
            )
        )
    db.flush()
    return row


def get_agreement(db: Session, agreement_id) -> Agreement | None:
    return db.get(Agreement, agreement_id)


def get_job_by_agreement(db: Session, agreement_id) -> Job | None:
    return db.scalar(select(Job).where(Job.agreement_id == agreement_id))


def get_rates_for_agreement(db: Session, agreement_id) -> list[CanonicalRate]:
    return list(db.scalars(select(CanonicalRate).where(CanonicalRate.agreement_id == agreement_id)))


def get_rate(db: Session, rate_id) -> CanonicalRate | None:
    return db.get(CanonicalRate, rate_id)


def query_rates(
    db: Session, *, origin=None, destination=None, mode=None, vendor_id=None, limit=200
) -> list[CanonicalRate]:
    """Structured (non-AI) filter query over canonical rates."""
    stmt = select(CanonicalRate)
    if origin:
        stmt = stmt.where(CanonicalRate.origin.ilike(f"%{origin}%"))
    if destination:
        stmt = stmt.where(CanonicalRate.destination.ilike(f"%{destination}%"))
    if mode:
        stmt = stmt.where(CanonicalRate.transport_mode == mode)
    if vendor_id:
        stmt = stmt.where(CanonicalRate.vendor_id == vendor_id)
    stmt = stmt.order_by(CanonicalRate.rate_value.asc()).limit(limit)
    return list(db.scalars(stmt))


def get_metadata_for_agreement(db: Session, agreement_id) -> AgreementMetadata | None:
    return db.scalar(select(AgreementMetadata).where(AgreementMetadata.agreement_id == agreement_id))


def get_tables_for_agreement(db: Session, agreement_id) -> list[ExtractedTable]:
    return list(
        db.scalars(
            select(ExtractedTable)
            .where(ExtractedTable.agreement_id == agreement_id)
            .order_by(ExtractedTable.page_number)
        )
    )


def get_clauses_for_agreement(db: Session, agreement_id) -> list[Clause]:
    return list(db.scalars(select(Clause).where(Clause.agreement_id == agreement_id)))


def count_unresolved_review_tasks(db: Session, job: Job) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(ReviewTask)
            .where(ReviewTask.job_id == job.id, ReviewTask.resolved.is_(False))
        )
        or 0
    )


def create_review_task(
    db: Session, *, job: Job, kind: ReviewItemKind, item_id, reason: str
) -> ReviewTask:
    task = ReviewTask(job_id=job.id, item_kind=kind, item_id=item_id, reason=reason)
    db.add(task)
    db.flush()
    return task


def maybe_flag_for_review(
    db: Session, *, job: Job, kind: ReviewItemKind, item_id, confidence: float, ai_touched: bool = False
) -> bool:
    """Create a review task if the item's band/ai-status requires it (Enh #2/#4)."""
    band = to_band(confidence)
    if needs_human_review(band, ai_touched):
        reason = "LOW confidence" if band.value == "LOW" else "AI-touched"
        create_review_task(db, job=job, kind=kind, item_id=item_id, reason=reason)
        return True
    return False


# --------------------------------------------------------------------------- #
# Phase 7 — review workflow (corrections, learning loop, approval gate)
# --------------------------------------------------------------------------- #
_ITEM_MODELS = {
    ReviewItemKind.RATE: CanonicalRate,
    ReviewItemKind.CLAUSE: Clause,
    ReviewItemKind.METADATA: AgreementMetadata,
}


def get_review_task(db: Session, task_id) -> ReviewTask | None:
    return db.get(ReviewTask, task_id)


def list_review_tasks_for_job(db: Session, job_id, *, only_open: bool = True) -> list[ReviewTask]:
    stmt = select(ReviewTask).where(ReviewTask.job_id == job_id)
    if only_open:
        stmt = stmt.where(ReviewTask.resolved.is_(False))
    return list(db.scalars(stmt))


def apply_review_correction(
    db: Session, *, task: ReviewTask, field: str, new_value, corrected_by: str
) -> ReviewTask:
    """Apply a human edit to the underlying item, resolve the task, and feed the
    pattern-learning store (Enhancement #5) when a RATE layout is verified."""
    model = _ITEM_MODELS.get(task.item_kind)
    old_value = None
    if model is not None and field:
        item = db.get(model, task.item_id)
        if item is not None and hasattr(item, field):
            old_value = getattr(item, field)
            setattr(item, field, _coerce(item, field, new_value))
            if hasattr(item, "validation_status"):
                item.validation_status = ValidationStatus.HUMAN_VERIFIED
            db.add(item)
            if task.item_kind is ReviewItemKind.RATE:
                _learn_from_rate(db, item)

    db.add(
        ReviewCorrection(
            task_id=task.id, field=field,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            corrected_by=corrected_by,
        )
    )
    task.resolved = True
    task.resolved_by = corrected_by
    task.resolved_at = datetime.now(timezone.utc)
    db.add(task)
    db.flush()
    return task


def approve_job(db: Session, *, job: Job, approved_by: str) -> Job:
    """Sign off review -> REVIEW_APPROVED, unblocking export. Refuses if any task open."""
    from app.core.exceptions import ReviewBlockedError

    open_tasks = count_unresolved_review_tasks(db, job)
    if open_tasks > 0:
        raise ReviewBlockedError(f"{open_tasks} review task(s) still open")
    job.status = JobStatus.REVIEW_APPROVED
    job.stage_detail = f"review approved by {approved_by}"
    db.add(job)
    db.flush()
    return job


def _coerce(item, field: str, value):
    """Best-effort coercion to the current attribute's type."""
    current = getattr(item, field, None)
    if value is None:
        return None
    if isinstance(current, bool):
        return str(value).lower() in {"1", "true", "yes"}
    if isinstance(current, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return current
    if isinstance(current, date):
        from app.metadata.metadata_extractor import parse_date
        return parse_date(str(value)) or current
    return value


def _learn_from_rate(db: Session, rate: CanonicalRate) -> None:
    """Promote the source table's fingerprint to human-verified (Enhancement #5)."""
    from app.classification import fingerprint_store as fp
    from app.classification.result import ClassificationResult

    if rate.table_id is None:
        return
    table = db.get(ExtractedTable, rate.table_id)
    if table is None or not table.fingerprint:
        return
    result = ClassificationResult(
        pattern=table.pattern, confidence=1.0, tier="human", column_mapping={}
    )
    fp.learn(
        db, vendor_id=rate.vendor_id, fingerprint=table.fingerprint,
        result=result, human_verified=True,
    )
