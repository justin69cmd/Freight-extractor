"""COURIER_RATE — destination + rate, with optional docket charge & service level."""
from __future__ import annotations

import re

from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.normalization.adapters.base import Adapter, NormContext
from app.normalization.canonical_row import CanonicalRow
from app.normalization.route_expander import expand_routes
from app.normalization.unit_normalizer import parse_amount

_DEST_HEADER = re.compile(r"destination|to|city|location|station", re.I)
_RATE_HEADER = re.compile(r"rate|amount|charge|freight|express|surface|per\s*kg", re.I)
_DOCKET_HEADER = re.compile(r"docket|min|booking", re.I)
_SERVICE_RE = re.compile(r"express|surface|priority|premium|standard", re.I)


class CourierRateAdapter(Adapter):
    def normalize(self, ctx: NormContext) -> list[CanonicalRow]:
        header = ctx.header
        cm = ctx.column_mapping
        di = cm.get("destination", _find(header, _DEST_HEADER, 0))
        rate_i = cm.get("rate", _find(header, _RATE_HEADER, len(header) - 1))
        dk_i = _find(header, _DOCKET_HEADER, -1)
        svc_match = _SERVICE_RE.search(header[rate_i] if rate_i < len(header) else "")
        service = svc_match.group(0).lower() if svc_match else None

        rows: list[CanonicalRow] = []
        for r, body_row in enumerate(ctx.body, start=1):
            dest_cell = body_row[di] if di < len(body_row) else None
            rate = parse_amount(body_row[rate_i] if rate_i < len(body_row) else None)
            docket = parse_amount(body_row[dk_i]) if 0 <= dk_i < len(body_row) else None
            for _, dest in expand_routes(None, dest_cell, ctx.aliases) or [(None, None)]:
                rows.append(
                    CanonicalRow(
                        transport_mode=TransportMode.COURIER,
                        source_pattern=PricingPattern.COURIER_RATE,
                        destination=dest or None,
                        rate_basis=RateBasis.PER_KG,
                        rate_value=rate,
                        docket_charge=docket,
                        service_level=service,
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
