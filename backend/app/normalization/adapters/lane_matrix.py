"""LANE_MATRIX — row label is origin, column header is destination, cell is rate."""
from __future__ import annotations

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext
from app.normalization.canonical_row import CanonicalRow
from app.normalization.unit_normalizer import parse_amount


class LaneMatrixAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            origin = (body_row[0] if body_row else "").strip()
            origin = ctx.aliases.get(origin.lower(), origin)
            for c in range(1, len(header)):
                dest = (header[c] or "").strip()
                dest = ctx.aliases.get(dest.lower(), dest)
                rate = parse_amount(body_row[c] if c < len(body_row) else None)
                if not dest or origin.lower() == dest.lower():
                    continue  # skip diagonal / empty
                rows.append(
                    CanonicalRow(
                        transport_mode=TransportMode.ROAD,
                        source_pattern=PricingPattern.LANE_MATRIX,
                        origin=origin or None,
                        destination=dest or None,
                        rate_basis=RateBasis.PER_TRIP,
                        rate_value=rate,
                        source_page=ctx.page_number,
                        source_cell=ctx.cell_provenance(r, c),
                        source_bbox=ctx.bbox,
                        extraction_confidence=ctx.extraction_confidence,
                    )
                )
        return rows
