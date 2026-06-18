"""Pydantic v2 API schemas — the typed contracts crossing the HTTP boundary.

Kept separate from ORM models so the wire format can evolve independently and
so we never leak SQLAlchemy internals to clients.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ClauseType,
    ConfidenceBand,
    JobStatus,
    PricingPattern,
    RateBasis,
    SearchIntent,
    TransportMode,
    ValidationStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- provenance (Enhancement #6) ------------------------------------------- #
class Provenance(ORMModel):
    source_page: int | None = None
    source_bbox: dict | None = None
    source_cell: dict | None = None
    extraction_confidence: float
    confidence_band: ConfidenceBand
    validation_status: ValidationStatus
    ai_touched: bool
    ai_explanation: str | None = None


# --- vendor / agreement ----------------------------------------------------- #
class VendorOut(ORMModel):
    id: uuid.UUID
    name: str
    code: str | None = None


class VendorCreate(BaseModel):
    name: str
    code: str | None = None
    profile_ref: str | None = None
    aliases: dict | None = None


class AgreementOut(ORMModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    original_filename: str
    page_count: int | None = None


# --- metadata + clauses (Enhancement #1) ----------------------------------- #
class ClauseOut(ORMModel):
    id: uuid.UUID
    clause_type: ClauseType
    text: str
    summary: str | None = None
    provenance: Provenance | None = None


class AgreementMetadataOut(ORMModel):
    vendor_name: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    payment_terms: str | None = None
    clauses: list[ClauseOut] = Field(default_factory=list)


# --- canonical rate --------------------------------------------------------- #
class RateOut(ORMModel):
    id: uuid.UUID
    transport_mode: TransportMode
    source_pattern: PricingPattern
    origin: str | None = None
    destination: str | None = None
    origin_zone: str | None = None
    destination_zone: str | None = None
    origin_state: str | None = None
    destination_state: str | None = None
    rate_basis: RateBasis
    rate_value: float | None = None
    currency: str = "INR"
    vehicle_type: str | None = None
    service_level: str | None = None
    temperature_band: str | None = None
    weight_slab_min_kg: float | None = None
    weight_slab_max_kg: float | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    confidence_band: ConfidenceBand
    extraction_confidence: float


class RateProvenanceOut(RateOut):
    """Full traceability view (Enhancement #6) — agreement→page→table→cell."""
    agreement_id: uuid.UUID
    table_id: uuid.UUID | None = None
    source_page: int | None = None
    source_bbox: dict | None = None
    source_cell: dict | None = None
    raw_snapshot: dict | None = None
    ai_explanation: str | None = None


# --- jobs + review (Enhancement #2) ---------------------------------------- #
class JobOut(ORMModel):
    id: uuid.UUID
    agreement_id: uuid.UUID
    status: JobStatus
    stage_detail: str | None = None
    progress: float
    flags_count: int
    error: str | None = None


class ReviewTaskOut(ORMModel):
    id: uuid.UUID
    item_kind: str
    item_id: uuid.UUID
    reason: str
    resolved: bool


class ReviewCorrectionIn(BaseModel):
    field: str
    new_value: str | None = None
    corrected_by: str


class ReviewApproveIn(BaseModel):
    approved_by: str
    notes: str | None = None


# --- search / RAG (Enhancement #3) ----------------------------------------- #
class SearchRequest(BaseModel):
    query: str
    intent: SearchIntent | None = None  # auto-detected if omitted
    top_k: int = 10


class SearchHit(BaseModel):
    kind: str                # RATE | CLAUSE | METADATA
    score: float
    vendor: str | None = None
    snippet: str
    ref_id: uuid.UUID
    provenance: Provenance | None = None


class SearchResponse(BaseModel):
    intent: SearchIntent
    answer: str | None = None     # LLM-synthesized answer for clause/analytics
    hits: list[SearchHit]


class ExtractedTableOut(ORMModel):
    """A raw extracted table grid — the source the rates were normalized from."""
    id: uuid.UUID
    page_number: int
    pattern: PricingPattern
    classification_confidence: float
    confidence_band: ConfidenceBand
    cells: list[list[str]]


class UploadResponse(BaseModel):
    job_id: uuid.UUID
    agreement_id: uuid.UUID
    status: JobStatus


class ExportRequest(BaseModel):
    template: str = "mankind_default_v2"
    include_flagged: bool = False


class ExportResponse(BaseModel):
    download_uri: str
    generated_at: datetime
