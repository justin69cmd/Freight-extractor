"""CanonicalRow — the pure, DB-free output of a normalization adapter.

Adapters produce these; the repository maps them onto the CanonicalRate ORM row
(adding agreement/vendor ids). Keeping adapters DB-free makes them unit-testable
in isolation. Every row carries its source cell + confidence so traceability
(Enhancement #6) survives normalization.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.core.enums import PricingPattern, RateBasis, TransportMode


class CanonicalRow(BaseModel):
    transport_mode: TransportMode
    source_pattern: PricingPattern

    # lane
    origin: str | None = None
    destination: str | None = None
    origin_zone: str | None = None
    destination_zone: str | None = None
    origin_state: str | None = None
    destination_state: str | None = None

    # price
    rate_basis: RateBasis
    rate_value: float | None = None
    currency: str = "INR"
    min_charge: float | None = None
    min_weight_kg: float | None = None

    # sparse qualifiers
    vehicle_type: str | None = None
    vehicle_capacity_kg: float | None = None
    weight_slab_min_kg: float | None = None
    weight_slab_max_kg: float | None = None
    service_level: str | None = None
    temperature_band: str | None = None
    fuel_surcharge_pct: float | None = None
    docket_charge: float | None = None

    # temporal
    effective_from: date | None = None
    effective_to: date | None = None

    # provenance (Enhancement #6) — carried from the source cell
    source_page: int | None = None
    source_cell: dict | None = None       # {row, col}
    source_bbox: dict | None = None
    extraction_confidence: float = 1.0
    raw_snapshot: dict | None = Field(default=None)

    # AI validation provenance (Enhancement #6 / Layer 3) — set when L3 repaired
    # the source table. Carried so the persisted rate records who touched it.
    ai_touched: bool = False
    ai_explanation: str | None = None
