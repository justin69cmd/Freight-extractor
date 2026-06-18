"""ZONE_MATRIX — row label is origin, column headers are zones, cell is a flat zone rate.

The destination_zone is resolved to concrete states later by the zone_resolver
(joins STATE_ZONE_MAPPING for the same vendor).
"""
from __future__ import annotations

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext
from app.normalization.canonical_row import CanonicalRow
from app.normalization.unit_normalizer import parse_amount


class ZoneMatrixAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            origin = (body_row[0] if body_row else "").strip()
            origin = ctx.aliases.get(origin.lower(), origin)
            for c in range(1, len(header)):
                zone = (header[c] or "").strip()
                rate = parse_amount(body_row[c] if c < len(body_row) else None)
                if not zone:
                    continue
                rows.append(
                    CanonicalRow(
                        transport_mode=TransportMode.ROAD,
                        source_pattern=PricingPattern.ZONE_MATRIX,
                        origin=origin or None,
                        destination_zone=zone,
                        rate_basis=RateBasis.FLAT_ZONE,
                        rate_value=rate,
                        source_page=ctx.page_number,
                        source_cell=ctx.cell_provenance(r, c),
                        source_bbox=ctx.bbox,
                        extraction_confidence=ctx.extraction_confidence,
                    )
                )
        return rows
