"""Zone indirection (STATE_ZONE_MAPPING + ZONE_MATRIX resolution).

Two jobs:
  1. parse_state_zone(): turn a STATE_ZONE_MAPPING table into (state, zone) rows.
  2. resolve_zone_rates(): expand a ZONE_MATRIX rate (which only knows a zone)
     into concrete per-state destination rows by joining the vendor's zone map.

A ZONE_MATRIX rate whose zone has no mapping is NOT dropped — it is kept with
destination_zone set and destination_state None, and flagged so review can
supply the mapping (AI gate G4 / human review). Never silently lose a rate.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.normalization.adapters.base import NormContext
from app.normalization.canonical_row import CanonicalRow

_ZONE_HEADER = re.compile(r"zone", re.I)
_STATE_HEADER = re.compile(r"state", re.I)


class ZoneMapRow(BaseModel):
    state: str
    zone: str
    source_page: int | None = None
    source_cell: dict | None = None
    extraction_confidence: float = 1.0


def parse_state_zone(ctx: NormContext) -> list[ZoneMapRow]:
    """Extract (state, zone) pairs from a STATE_ZONE_MAPPING table."""
    header = ctx.header
    state_i = _find(header, _STATE_HEADER, 0)
    zone_i = _find(header, _ZONE_HEADER, 1)
    out: list[ZoneMapRow] = []
    for r, body_row in enumerate(ctx.body, start=1):
        state = (body_row[state_i] if state_i < len(body_row) else "").strip()
        zone = (body_row[zone_i] if zone_i < len(body_row) else "").strip()
        if not state or not zone:
            continue
        out.append(
            ZoneMapRow(
                state=state, zone=_norm_zone(zone),
                source_page=ctx.page_number,
                source_cell={"row": r, "col": zone_i},
                extraction_confidence=ctx.extraction_confidence,
            )
        )
    return out


def resolve_zone_rates(
    rows: list[CanonicalRow], zone_to_states: dict[str, list[str]]
) -> list[CanonicalRow]:
    """Expand ZONE_MATRIX rows (destination_zone) into per-state destination rows."""
    resolved: list[CanonicalRow] = []
    for row in rows:
        if not row.destination_zone:
            resolved.append(row)
            continue
        states = zone_to_states.get(_norm_zone(row.destination_zone))
        if not states:
            resolved.append(row)  # keep unresolved; flagged downstream (G4)
            continue
        for state in states:
            clone = row.model_copy()
            clone.destination_state = state
            resolved.append(clone)
    return resolved


def build_zone_index(zone_rows: list[ZoneMapRow]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for z in zone_rows:
        index.setdefault(z.zone, []).append(z.state)
    return index


def _norm_zone(z: str) -> str:
    z = re.sub(r"(?i)\bzone\b", "", z).strip().upper()
    return z


def _find(header: list[str], pattern: re.Pattern, default: int) -> int:
    for i, h in enumerate(header):
        if pattern.search(h or ""):
            return i
    return default
