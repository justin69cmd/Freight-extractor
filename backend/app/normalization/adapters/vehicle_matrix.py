"""VEHICLE_MATRIX — first column is the lane, remaining headers are vehicle types.

Each body cell is the rate for (lane, vehicle), exploded into one row per cell.
"""
from __future__ import annotations

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext, split_lane
from app.normalization.canonical_row import CanonicalRow
from app.normalization.route_expander import expand_routes
from app.normalization.unit_normalizer import parse_amount


class VehicleMatrixAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            lane_label = body_row[0] if body_row else None
            origin0, dest0 = split_lane(lane_label or "")

            for c in range(1, len(header)):
                vehicle = (header[c] or "").strip()
                rate = parse_amount(body_row[c] if c < len(body_row) else None)
                if not vehicle:
                    continue
                # a lane label may itself be multi-value -> expand
                lanes = expand_routes(origin0, dest0, ctx.aliases) or [(origin0, dest0)]
                for origin, dest in lanes:
                    rows.append(
                        CanonicalRow(
                            transport_mode=TransportMode.ROAD,
                            source_pattern=PricingPattern.VEHICLE_MATRIX,
                            origin=origin or None,
                            destination=dest or None,
                            rate_basis=RateBasis.PER_TRIP,
                            rate_value=rate,
                            vehicle_type=vehicle,
                            source_page=ctx.page_number,
                            source_cell=ctx.cell_provenance(r, c),
                            source_bbox=ctx.bbox,
                            extraction_confidence=ctx.extraction_confidence,
                        )
                    )
        return rows
