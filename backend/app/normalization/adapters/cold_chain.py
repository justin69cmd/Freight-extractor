"""COLD_CHAIN_RATE — temperature-banded freight (lane + temperature + rate)."""
from __future__ import annotations

import re

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext, split_lane
from app.normalization.canonical_row import CanonicalRow
from app.normalization.route_expander import expand_routes
from app.normalization.unit_normalizer import parse_amount

_TEMP_HEADER = re.compile(r"temp|°c|cold|band|reefer", re.I)
_RATE_HEADER = re.compile(r"rate|amount|charge|freight|per", re.I)
_LANE_HEADER = re.compile(r"lane|route|sector|origin|destination|from|to", re.I)
_TEMP_VALUE = re.compile(r"(-?\d{1,2}\s*[-–]\s*-?\d{1,2}\s*°?\s*c|-?\d{1,2}\s*°?\s*c|frozen|ambient|chiller)", re.I)


class ColdChainAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        lane_i = _find(header, _LANE_HEADER, 0)
        temp_i = _find(header, _TEMP_HEADER, 1)
        rate_i = ctx.column_mapping.get("rate", _find(header, _RATE_HEADER, len(header) - 1))

        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            o, d = split_lane(body_row[lane_i] if lane_i < len(body_row) else "")
            temp_raw = body_row[temp_i] if temp_i < len(body_row) else ""
            tm = _TEMP_VALUE.search(temp_raw or "")
            temperature = tm.group(0).strip() if tm else (temp_raw or None)
            rate = parse_amount(body_row[rate_i] if rate_i < len(body_row) else None)
            for origin, dest in expand_routes(o, d, ctx.aliases) or [(o, d)]:
                rows.append(
                    CanonicalRow(
                        transport_mode=TransportMode.COLD_CHAIN,
                        source_pattern=PricingPattern.COLD_CHAIN_RATE,
                        origin=origin or None,
                        destination=dest or None,
                        rate_basis=RateBasis.PER_TRIP,
                        rate_value=rate,
                        temperature_band=temperature,
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
