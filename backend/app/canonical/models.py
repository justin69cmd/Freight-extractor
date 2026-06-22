"""SQLAlchemy ORM models — the canonical database schema.

Entity map
----------
Vendor ─< Agreement ─┬─< ExtractedTable ─< CanonicalRate          (freight rates)
                     ├─1 AgreementMetadata ─< Clause              (Enhancement #1)
                     ├─< ZoneMapping                              (zone indirection)
                     ├─< DocumentChunk                            (RAG, Enhancement #3)
                     └─1 Job ─< ReviewTask ─< ReviewCorrection    (Enhancement #2)
TableFingerprint  (vendor-scoped pattern learning, Enhancement #5)

Design notes
------------
* `ProvenanceMixin` is mixed into every trust-bearing row so traceability
  (Enhancement #6) is structural, not optional.
* `CanonicalRate` is one wide, sparse fact table so cross-vendor / cross-mode
  comparison is a single SQL query.
* Embeddings live in Postgres via pgvector (DocumentChunk.embedding).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.core.enums import (
    ClauseType,
    ConfidenceBand,
    JobStatus,
    PageKind,
    PricingPattern,
    RateBasis,
    ReviewItemKind,
    TransportMode,
    ValidationStatus,
)
from app.db import Base
from app.types import GUID, Embedding


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# --------------------------------------------------------------------------- #
# Reusable mixins
# --------------------------------------------------------------------------- #
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProvenanceMixin:
    """Enhancement #6 — full traceability for every extracted fact.

    Any row carrying this mixin can be traced agreement -> page -> table -> cell,
    with both a numeric confidence and a derived band, plus an AI explanation.
    """
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_bbox: Mapped[dict | None] = mapped_column(JSON)  # {x0,y0,x1,y1}
    source_cell: Mapped[dict | None] = mapped_column(JSON)  # {row, col}
    extraction_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confidence_band: Mapped[ConfidenceBand] = mapped_column(
        Enum(ConfidenceBand), default=ConfidenceBand.HIGH
    )
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus), default=ValidationStatus.AUTO
    )
    ai_touched: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_explanation: Mapped[str | None] = mapped_column(Text)  # why AI changed it
    raw_snapshot: Mapped[dict | None] = mapped_column(JSON)   # original cells, audit


# --------------------------------------------------------------------------- #
# Vendor / Agreement
# --------------------------------------------------------------------------- #
class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    code: Mapped[str | None] = mapped_column(String(64), unique=True)
    profile_ref: Mapped[str | None] = mapped_column(String(255))  # vendor_profiles/*.yaml
    aliases: Mapped[dict | None] = mapped_column(JSON)  # {FRK: Faridabad, ...}

    agreements: Mapped[list["Agreement"]] = relationship(back_populates="vendor")


class Agreement(Base, TimestampMixin):
    __tablename__ = "agreements"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_uri: Mapped[str] = mapped_column(String(1024))  # where the PDF lives
    page_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)  # dedupe uploads

    vendor: Mapped[Vendor] = relationship(back_populates="agreements")
    metadata_row: Mapped["AgreementMetadata"] = relationship(
        back_populates="agreement", uselist=False
    )
    tables: Mapped[list["ExtractedTable"]] = relationship(back_populates="agreement")
    rates: Mapped[list["CanonicalRate"]] = relationship(back_populates="agreement")
    clauses: Mapped[list["Clause"]] = relationship(back_populates="agreement")
    zone_mappings: Mapped[list["ZoneMapping"]] = relationship(back_populates="agreement")
    job: Mapped["Job"] = relationship(back_populates="agreement", uselist=False)


# --------------------------------------------------------------------------- #
# Enhancement #1 — Agreement metadata + clauses (stored separate from rates)
# --------------------------------------------------------------------------- #
class AgreementMetadata(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "agreement_metadata"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agreements.id"), unique=True, index=True
    )
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    payment_terms: Mapped[str | None] = mapped_column(Text)  # quick-access summary

    agreement: Mapped[Agreement] = relationship(back_populates="metadata_row")


class Clause(Base, TimestampMixin, ProvenanceMixin):
    """Fuel / Insurance / Penalty / Payment-terms clauses, individually traceable."""
    __tablename__ = "clauses"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agreements.id"), index=True)
    clause_type: Mapped[ClauseType] = mapped_column(Enum(ClauseType), index=True)
    text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)  # AI one-line summary for search

    agreement: Mapped[Agreement] = relationship(back_populates="clauses")


# --------------------------------------------------------------------------- #
# Extraction + Enhancement #5 (fingerprint / pattern learning)
# --------------------------------------------------------------------------- #
class ExtractedTable(Base, TimestampMixin):
    __tablename__ = "extracted_tables"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agreements.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    page_kind: Mapped[PageKind] = mapped_column(Enum(PageKind), default=PageKind.RATE_CARD)
    bbox: Mapped[dict | None] = mapped_column(JSON)
    cells: Mapped[list] = mapped_column(JSON)  # raw cell grid [[...],[...]]
    extraction_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confidence_band: Mapped[ConfidenceBand] = mapped_column(
        Enum(ConfidenceBand), default=ConfidenceBand.HIGH
    )
    # classification result
    pattern: Mapped[PricingPattern] = mapped_column(
        Enum(PricingPattern), default=PricingPattern.UNKNOWN
    )
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)  # links to learning

    agreement: Mapped[Agreement] = relationship(back_populates="tables")
    rates: Mapped[list["CanonicalRate"]] = relationship(back_populates="table")


class TableFingerprint(Base, TimestampMixin):
    """Enhancement #5 — learned mapping fingerprint -> (vendor, pattern, columns).

    On future uploads a fingerprint hit reuses this mapping and skips
    classification + AI entirely. Human corrections increment hit_count and can
    overwrite the learned column_mapping, so the system improves with use.
    """
    __tablename__ = "table_fingerprints"
    __table_args__ = (UniqueConstraint("vendor_id", "fingerprint", name="uq_vendor_fingerprint"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    pattern: Mapped[PricingPattern] = mapped_column(Enum(PricingPattern))
    column_mapping: Mapped[dict] = mapped_column(JSON)  # logical field -> column index
    header_signature: Mapped[list | None] = mapped_column(JSON)
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- #
# Canonical freight rate — one wide sparse fact table
# --------------------------------------------------------------------------- #
class CanonicalRate(Base, TimestampMixin, ProvenanceMixin):
    __tablename__ = "canonical_rates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agreements.id"), index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    table_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extracted_tables.id"))

    transport_mode: Mapped[TransportMode] = mapped_column(Enum(TransportMode), index=True)
    source_pattern: Mapped[PricingPattern] = mapped_column(Enum(PricingPattern))

    # --- lane (geography) ---
    origin: Mapped[str | None] = mapped_column(String(255), index=True)
    destination: Mapped[str | None] = mapped_column(String(255), index=True)
    origin_zone: Mapped[str | None] = mapped_column(String(64))
    destination_zone: Mapped[str | None] = mapped_column(String(64))
    origin_state: Mapped[str | None] = mapped_column(String(128))
    destination_state: Mapped[str | None] = mapped_column(String(128))

    # --- price ---
    rate_basis: Mapped[RateBasis] = mapped_column(Enum(RateBasis))
    rate_value: Mapped[float | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    min_charge: Mapped[float | None] = mapped_column(Numeric(14, 4))
    min_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))

    # --- sparse dimensional qualifiers ---
    vehicle_type: Mapped[str | None] = mapped_column(String(128))
    vehicle_capacity_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))
    weight_slab_min_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))
    weight_slab_max_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))
    service_level: Mapped[str | None] = mapped_column(String(64))   # express/surface
    temperature_band: Mapped[str | None] = mapped_column(String(64))  # 2-8C / -20C
    fuel_surcharge_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    docket_charge: Mapped[float | None] = mapped_column(Numeric(12, 4))

    # --- temporal ---
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)

    agreement: Mapped[Agreement] = relationship(back_populates="rates")
    table: Mapped[ExtractedTable | None] = relationship(back_populates="rates")


class ZoneMapping(Base, TimestampMixin, ProvenanceMixin):
    """STATE_ZONE_MAPPING rows — resolve zone-based rates to states (vendor-scoped)."""
    __tablename__ = "zone_mappings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agreements.id"), index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    state: Mapped[str] = mapped_column(String(128), index=True)
    zone: Mapped[str] = mapped_column(String(64), index=True)

    agreement: Mapped[Agreement] = relationship(back_populates="zone_mappings")


# --------------------------------------------------------------------------- #
# Enhancement #3 — RAG document chunks (rates + clauses + metadata, one space)
# --------------------------------------------------------------------------- #
class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agreements.id"), index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    kind: Mapped[ReviewItemKind] = mapped_column(Enum(ReviewItemKind))  # RATE/CLAUSE/METADATA
    ref_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True)  # source row id
    content: Mapped[str] = mapped_column(Text)  # denormalized searchable text
    embedding: Mapped[list[float]] = mapped_column(Embedding(settings.embedding_dim))


# --------------------------------------------------------------------------- #
# Job + Enhancement #2 (human review workflow)
# --------------------------------------------------------------------------- #
class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    agreement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agreements.id"), unique=True, index=True
    )
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, index=True)
    stage_detail: Mapped[str | None] = mapped_column(String(255))
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    error: Mapped[str | None] = mapped_column(Text)
    flags_count: Mapped[int] = mapped_column(Integer, default=0)

    agreement: Mapped[Agreement] = relationship(back_populates="job")
    review_tasks: Mapped[list["ReviewTask"]] = relationship(back_populates="job")


class ReviewTask(Base, TimestampMixin):
    """A unit awaiting human verification before export is allowed."""
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), index=True)
    item_kind: Mapped[ReviewItemKind] = mapped_column(Enum(ReviewItemKind))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True)
    reason: Mapped[str] = mapped_column(String(255))  # e.g. "LOW band", "ai_touched"
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[Job] = relationship(back_populates="review_tasks")
    corrections: Mapped[list["ReviewCorrection"]] = relationship(back_populates="task")


class ReviewCorrection(Base, TimestampMixin):
    """A human edit. Feeds the pattern-learning store (Enhancement #5)."""
    __tablename__ = "review_corrections"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_tasks.id"), index=True)
    field: Mapped[str] = mapped_column(String(128))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    corrected_by: Mapped[str] = mapped_column(String(255))

    task: Mapped[ReviewTask] = relationship(back_populates="corrections")
