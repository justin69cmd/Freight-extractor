"""Adapter base — shared context, helpers, and the Adapter protocol."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.normalization.canonical_row import CanonicalRow

# "Delhi-Mumbai", "Delhi to Mumbai", "Delhi > Mumbai" -> (Delhi, Mumbai)
_LANE_SPLIT = re.compile(r"\s*(?:-|–|to|>|→|\bvia\b)\s*", re.I)


@dataclass
class NormContext:
    """Everything an adapter needs to normalize one table, DB-free."""
    grid: list[list[str]]
    column_mapping: dict
    page_number: int = 0
    extraction_confidence: float = 1.0
    bbox: dict | None = None
    aliases: dict[str, str] = field(default_factory=dict)

    @property
    def header(self) -> list[str]:
        return self.grid[0] if self.grid else []

    @property
    def body(self) -> list[list[str]]:
        return self.grid[1:] if len(self.grid) > 1 else []

    def cell_provenance(self, row: int, col: int) -> dict:
        """Source cell coords for traceability (Enhancement #6). row is body-relative+1."""
        return {"row": row, "col": col}


def split_lane(label: str) -> tuple[str | None, str | None]:
    """Split a combined lane label into (origin, destination); single -> (label, None)."""
    if not label:
        return (None, None)
    parts = [p.strip() for p in _LANE_SPLIT.split(label) if p.strip()]
    if len(parts) >= 2:
        return (parts[0], parts[1])
    if len(parts) == 1:
        return (parts[0], None)
    return (None, None)


class Adapter:
    """Adapter contract: pattern -> CanonicalRow[]."""

    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:  # pragma: no cover
        raise NotImplementedError
