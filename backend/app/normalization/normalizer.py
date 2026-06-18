"""L4 — normalization dispatcher.

Agreement-level flow:
  1. Parse all STATE_ZONE_MAPPING tables first -> vendor zone index.
  2. Normalize every rate table via its pattern adapter -> CanonicalRow[].
  3. Resolve ZONE_MATRIX rows against the zone index (zone -> states).

Returns canonical rows + the parsed zone-map rows for persistence. Pure: takes
plain table descriptors, no DB — the pipeline handles persistence.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import PricingPattern
from app.normalization.adapters import REGISTRY
from app.normalization.adapters.base import NormContext
from app.normalization.canonical_row import CanonicalRow
from app.normalization.zone_resolver import (
    ZoneMapRow,
    build_zone_index,
    parse_state_zone,
    resolve_zone_rates,
)


@dataclass
class TableInput:
    """Minimal descriptor of a classified table for normalization."""
    pattern: PricingPattern
    grid: list[list[str]]
    column_mapping: dict
    page_number: int = 0
    extraction_confidence: float = 1.0
    bbox: dict | None = None


@dataclass
class NormalizationOutput:
    rows: list[CanonicalRow]
    zone_maps: list[ZoneMapRow]


def collect_zone_maps(
    tables: list[TableInput], aliases: dict[str, str]
) -> tuple[list[ZoneMapRow], dict[str, list[str]]]:
    """Pass 1 — parse all STATE_ZONE_MAPPING tables into a vendor zone index."""
    zone_rows: list[ZoneMapRow] = []
    for t in tables:
        if t.pattern is PricingPattern.STATE_ZONE_MAPPING:
            zone_rows.extend(parse_state_zone(_ctx(t, aliases)))
    return zone_rows, build_zone_index(zone_rows)


def normalize_one(
    table: TableInput, aliases: dict[str, str], zone_index: dict[str, list[str]]
) -> list[CanonicalRow]:
    """Normalize a single table and resolve any zone references. Keeps table_id
    linkage at the call site (the pipeline maps these back to the source table)."""
    adapter = REGISTRY.get(table.pattern)
    if adapter is None:
        return []
    rows = adapter.normalize(_ctx(table, aliases))
    return resolve_zone_rates(rows, zone_index)


def normalize_agreement(
    tables: list[TableInput], *, aliases: dict[str, str] | None = None
) -> NormalizationOutput:
    aliases = aliases or {}
    zone_rows, zone_index = collect_zone_maps(tables, aliases)
    rows: list[CanonicalRow] = []
    for t in tables:
        rows.extend(normalize_one(t, aliases, zone_index))
    return NormalizationOutput(rows=rows, zone_maps=zone_rows)


def _ctx(t: TableInput, aliases: dict[str, str]) -> NormContext:
    return NormContext(
        grid=t.grid,
        column_mapping=t.column_mapping,
        page_number=t.page_number,
        extraction_confidence=t.extraction_confidence,
        bbox=t.bbox,
        aliases=aliases,
    )
