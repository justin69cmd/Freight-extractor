"""PER_KG_RATE — weight-slab pricing. Each row is a slab with a per-kg rate.

Optional origin/destination columns are honoured if the classifier mapped them;
otherwise the slab rate applies lane-agnostically (origin/destination None).
"""
from __future__ import annotations

import re

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext
from app.normalization.canonical_row import CanonicalRow
from app.normalization.route_expander import expand_routes
from app.normalization.unit_normalizer import parse_amount, parse_weight_slab

_SLAB_HEADER = re.compile(r"slab|weight|kg|grammage", re.I)
_RATE_HEADER = re.compile(r"rate|amount|charge|freight|per\s*kg|rs|inr", re.I)


class PerKgAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        cm = ctx.column_mapping
        slab_i = _find(header, _SLAB_HEADER, default=0)
        rate_i = cm.get("rate", _find(header, _RATE_HEADER, default=len(header) - 1))
        oi, di = cm.get("origin"), cm.get("destination")

        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            lo, hi = parse_weight_slab(body_row[slab_i] if slab_i < len(body_row) else None)
            rate = parse_amount(body_row[rate_i] if rate_i < len(body_row) else None)
            origin_cell = body_row[oi] if oi is not None and oi < len(body_row) else None
            dest_cell = body_row[di] if di is not None and di < len(body_row) else None
            lanes = expand_routes(origin_cell, dest_cell, ctx.aliases) or [(None, None)]
            for origin, dest in lanes:
                rows.append(
                    CanonicalRow(
                        transport_mode=TransportMode.ROAD,
                        source_pattern=PricingPattern.PER_KG_RATE,
                        origin=origin or None,
                        destination=dest or None,
                        rate_basis=RateBasis.PER_KG,
                        rate_value=rate,
                        weight_slab_min_kg=lo,
                        weight_slab_max_kg=hi,
                        source_page=ctx.page_number,
                        source_cell=ctx.cell_provenance(r, rate_i),
                        source_bbox=ctx.bbox,
                        extraction_confidence=ctx.extraction_confidence,
                    )
                )
        return rows


def _find(header: list[str], pattern: re.Pattern, default: int) -> int:
    for i, h in enumerate(header):
        if pattern.search(h or ""):
            return i
    return default
