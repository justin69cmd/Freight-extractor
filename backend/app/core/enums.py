"""Shared enumerations — the controlled vocabulary of the entire platform.

Kept in one place so the API, DB models, pipeline and tests all agree.
"""
from __future__ import annotations

import enum


class PricingPattern(str, enum.Enum):
    """The 9 structurally-distinct pricing grammars vendors use (Requirement 4)."""
    ROUTE_TABLE = "ROUTE_TABLE"
    VEHICLE_MATRIX = "VEHICLE_MATRIX"
    LANE_MATRIX = "LANE_MATRIX"
    PER_KG_RATE = "PER_KG_RATE"
    AIR_RATE = "AIR_RATE"
    COURIER_RATE = "COURIER_RATE"
    ZONE_MATRIX = "ZONE_MATRIX"
    COLD_CHAIN_RATE = "COLD_CHAIN_RATE"
    STATE_ZONE_MAPPING = "STATE_ZONE_MAPPING"
    UNKNOWN = "UNKNOWN"  # classifier could not decide -> review


class TransportMode(str, enum.Enum):
    ROAD = "ROAD"
    AIR = "AIR"
    COURIER = "COURIER"
    COLD_CHAIN = "COLD_CHAIN"


class RateBasis(str, enum.Enum):
    """How `rate_value` should be interpreted — prevents silent unit mixing."""
    PER_KG = "PER_KG"
    PER_BOX = "PER_BOX"
    PER_TRIP = "PER_TRIP"
    PER_SHIPMENT = "PER_SHIPMENT"
    PER_CFT = "PER_CFT"
    SLAB = "SLAB"
    FLAT_ZONE = "FLAT_ZONE"


class ConfidenceBand(str, enum.Enum):
    """Enhancement #4 — categorical trust level derived from numeric confidence."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ValidationStatus(str, enum.Enum):
    AUTO = "AUTO"                    # deterministic, high confidence, untouched
    AI_VALIDATED = "AI_VALIDATED"    # AI gate repaired/confirmed it
    HUMAN_VERIFIED = "HUMAN_VERIFIED"  # a reviewer approved it
    FLAGGED = "FLAGGED"              # cannot be trusted; excluded from export


class ClauseType(str, enum.Enum):
    """Enhancement #1 — agreement metadata clauses, stored separate from rates."""
    FUEL = "FUEL"
    INSURANCE = "INSURANCE"
    PENALTY = "PENALTY"
    PAYMENT_TERMS = "PAYMENT_TERMS"
    OTHER = "OTHER"


class PageKind(str, enum.Enum):
    LEGAL = "LEGAL"
    ANNEXURE = "ANNEXURE"
    RATE_CARD = "RATE_CARD"
    ZONE_MAP = "ZONE_MAP"
    MIXED = "MIXED"
    OTHER = "OTHER"


class JobStatus(str, enum.Enum):
    """Pipeline state machine. REVIEW_PENDING hard-gates export (Enhancement #2)."""
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    EXTRACTING = "EXTRACTING"
    CLASSIFYING = "CLASSIFYING"
    VALIDATING = "VALIDATING"
    NORMALIZING = "NORMALIZING"
    REVIEW_PENDING = "REVIEW_PENDING"   # <-- export blocked here
    REVIEW_APPROVED = "REVIEW_APPROVED"
    EXPORTING = "EXPORTING"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_FLAGS = "SUCCEEDED_WITH_FLAGS"
    FAILED = "FAILED"


class ReviewItemKind(str, enum.Enum):
    RATE = "RATE"
    CLAUSE = "CLAUSE"
    METADATA = "METADATA"


class SearchIntent(str, enum.Enum):
    """Enhancement #3 — RAG router intents."""
    FREIGHT_SEARCH = "FREIGHT_SEARCH"
    CLAUSE_SEARCH = "CLAUSE_SEARCH"
    VENDOR_COMPARISON = "VENDOR_COMPARISON"
    AGREEMENT_ANALYTICS = "AGREEMENT_ANALYTICS"
