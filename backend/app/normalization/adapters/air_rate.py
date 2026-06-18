"""AIR_RATE — air freight, typically per-kg with an AWB/docket charge."""
from __future__ import annotations

import re

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext, split_lane
from app.normalization.canonical_row import CanonicalRow
from app.normalization.route_expander import expand_routes
from app.normalization.unit_normalizer import parse_amount

_RATE_HEADER = re.compile(r"rate|per\s*kg|amount|freight|charge", re.I)
_AWB_HEADER = re.compile(r"awb|docket|min", re.I)
_LANE_HEADER = re.compile(r"airport|sector|lane|route|station|origin|destination|from|to", re.I)


class AirRateAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        cm = ctx.column_mapping
        lane_i = _find(header, _LANE_HEADER, 0)
        rate_i = cm.get("rate", _find(header, _RATE_HEADER, len(header) - 1))
        awb_i = _find(header, _AWB_HEADER, -1)
        oi, di = cm.get("origin"), cm.get("destination")

        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            rate = parse_amount(body_row[rate_i] if rate_i < len(body_row) else None)
            awb = parse_amount(body_row[awb_i]) if 0 <= awb_i < len(body_row) else None
            if oi is not None or di is not None:
                ocell = body_row[oi] if oi is not None and oi < len(body_row) else None
                dcell = body_row[di] if di is not None and di < len(body_row) else None
                lanes = expand_routes(ocell, dcell, ctx.aliases)
            else:
                o, d = split_lane(body_row[lane_i] if lane_i < len(body_row) else "")
                lanes = expand_routes(o, d, ctx.aliases) or [(o, d)]
            for origin, dest in lanes:
                rows.append(
                    CanonicalRow(
                        transport_mode=TransportMode.AIR,
                        source_pattern=PricingPattern.AIR_RATE,
                        origin=origin or None,
                        destination=dest or None,
                        rate_basis=RateBasis.PER_KG,
                        rate_value=rate,
                        docket_charge=awb,
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
