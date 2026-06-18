"""Gate G3 — deterministic schema validation of normalized rows.

Pure, no AI: catches rows that violate business invariants before they reach the
Excel. A violation flags the row for review; it does not delete it.
"""
from __future__ import annotations

from app.core.enums import PricingPattern, TransportMode
from app.normalization.canonical_row import CanonicalRow
from app.validation.result import RowViolation

# Patterns where a usable rate must name at least a destination.
_LANE_PATTERNS = {
    PricingPattern.ROUTE_TABLE,
    PricingPattern.LANE_MATRIX,
    PricingPattern.VEHICLE_MATRIX,
    PricingPattern.COLD_CHAIN_RATE,
}

# Sanity ceiling — an Indian freight line item above this is almost surely a
# mis-parse (e.g. two cells merged) and should be reviewed.
_MAX_PLAUSIBLE_RATE = 10_000_000.0


def validate_rows(rows: list[CanonicalRow]) -> list[RowViolation]:
    violations: list[RowViolation] = []
    for i, r in enumerate(rows):
        if r.rate_value is None:
            violations.append(RowViolation(index=i, field="rate_value", reason="missing/garbled rate"))
        elif r.rate_value <= 0:
            violations.append(RowViolation(index=i, field="rate_value", reason="non-positive rate"))
        elif r.rate_value > _MAX_PLAUSIBLE_RATE:
            violations.append(RowViolation(index=i, field="rate_value", reason="implausibly large rate"))

        if (r.weight_slab_min_kg is not None and r.weight_slab_max_kg is not None
                and r.weight_slab_min_kg > r.weight_slab_max_kg):
            violations.append(RowViolation(index=i, field="weight_slab", reason="min > max"))

        if (r.source_pattern in _LANE_PATTERNS and not r.destination
                and not r.destination_zone and not r.destination_state):
            violations.append(RowViolation(index=i, field="destination", reason="lane rate without destination"))

        # ZONE_MATRIX rate that never resolved to a state (gate G4 residue)
        if (r.source_pattern is PricingPattern.ZONE_MATRIX
                and r.destination_zone and not r.destination_state):
            violations.append(RowViolation(index=i, field="destination_zone", reason="zone not mapped to any state"))
    return violations
