"""ROUTE_TABLE — origin/destination/rate rows, with Cartesian route expansion."""
from __future__ import annotations

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext
from app.normalization.canonical_row import CanonicalRow
from app.normalization.route_expander import expand_routes
from app.normalization.unit_normalizer import parse_amount


class RouteTableAdapter(Adapter):
    transport_mode = TransportMode.ROAD
    rate_basis = RateBasis.PER_TRIP

    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        cm = ctx.column_mapping
        oi = cm.get("origin", 0)
        di = cm.get("destination", 1)
        ri = cm.get("rate", len(ctx.header) - 1)

        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            origin_cell = body_row[oi] if oi < len(body_row) else None
            dest_cell = body_row[di] if di < len(body_row) else None
            rate = parse_amount(body_row[ri] if ri < len(body_row) else None)

            for origin, dest in expand_routes(origin_cell, dest_cell, ctx.aliases):
                rows.append(
                    CanonicalRow(
                        transport_mode=self.transport_mode,
                        source_pattern=PricingPattern.ROUTE_TABLE,
                        origin=origin or None,
                        destination=dest or None,
                        rate_basis=self.rate_basis,
                        rate_value=rate,
                        source_page=ctx.page_number,
                        source_cell=ctx.cell_provenance(r, ri),
                        source_bbox=ctx.bbox,
                        extraction_confidence=ctx.extraction_confidence,
                    )
                )
        return rows
