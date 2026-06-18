"""L2 — structural feature extraction from a RawTable.

Turns a cell grid into the signals the rule classifier scores on: header/row
tokens, shape, numeric density, matrix-symmetry, and per-category keyword hits.
Pure and deterministic — the same table always yields the same features, which
keeps classification explainable and testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.extraction.raw_table import RawTable

# --- keyword vocabularies per signal -------------------------------------- #
_VEHICLE_KW = re.compile(
    r"\b(407|709|1109|tata|ace|eicher|32\s?ft|24\s?ft|20\s?ft|14\s?ft|"
    r"vehicle|truck|lorry|lcv|hcv|trailer|container|ton(?:ne)?s?|mt)\b"
)
_ZONE_KW = re.compile(r"\bzone\b|\bzone\s*[a-f]\b|\b[a-f]\s*zone\b")
_ZONE_LABEL = re.compile(r"^(zone\s*)?[a-f]\d?$", re.I)
_PER_KG_KW = re.compile(r"\b(per\s*kg|/\s*kg|kg|slab|upto|up to|weight|grammage|chargeable)\b")
_AIR_KW = re.compile(r"\b(air|awb|airway|airport|flight|iata|cargo terminal)\b")
_COURIER_KW = re.compile(r"\b(courier|docket|express|surface|consignment|pod|e-?com)\b")
_COLD_KW = re.compile(r"(\b\d{1,2}\s*[-–]\s*\d{1,2}\s*°?\s*c\b|°c|frozen|reefer|cold\s*chain|"
                      r"refriger|temperature|ambient|chiller)")
_STATE_KW = re.compile(r"\bstate\b")
_RATE_KW = re.compile(r"\b(rate|freight|amount|charge|charges|tariff|rs\.?|inr|price|cost)\b")
_ORIGIN_KW = re.compile(r"\b(origin|from|source|ex[- ]?|pickup|loading)\b")
_DEST_KW = re.compile(r"\b(destination|to|dest|delivery|drop|unloading)\b")

_NUMERIC_RE = re.compile(r"^\s*[₹rs.\s]*[\d]+[\d,./\s-]*\s*$", re.I)

# A small set of Indian state names — enough to detect STATE_ZONE_MAPPING.
_INDIAN_STATES = {
    "andhra pradesh", "assam", "bihar", "chhattisgarh", "delhi", "goa", "gujarat",
    "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh",
    "maharashtra", "manipur", "meghalaya", "odisha", "orissa", "punjab", "rajasthan",
    "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "jammu and kashmir", "uttaranchal", "pondicherry", "chandigarh",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _is_numeric(s: str) -> bool:
    s = (s or "").strip()
    return bool(s) and bool(_NUMERIC_RE.match(s)) and any(ch.isdigit() for ch in s)


@dataclass
class Features:
    n_rows: int
    n_cols: int
    source: str
    header_tokens: list[str] = field(default_factory=list)   # first row
    row_labels: list[str] = field(default_factory=list)      # first column
    all_text: str = ""
    numeric_ratio: float = 0.0          # fraction of body cells that are numeric
    matrix_symmetry: float = 0.0        # overlap of row labels and header tokens [0,1]
    keyword_hits: dict[str, int] = field(default_factory=dict)
    zone_header_count: int = 0          # headers that look like Zone A/B/C
    state_label_count: int = 0          # row labels that are Indian states


def extract_features(table: RawTable) -> Features:
    grid = table.grid()
    header = [_norm(c) for c in (grid[0] if grid else [])]
    row_labels = [_norm(r[0]) for r in grid[1:] if r]
    all_text = _norm(" ".join(cell for row in grid for cell in row))

    # numeric density over the body (exclude header row & label col)
    body = [cell for row in grid[1:] for cell in row[1:]] if len(grid) > 1 else []
    numeric_ratio = (sum(1 for c in body if _is_numeric(c)) / len(body)) if body else 0.0

    # matrix symmetry: do row labels reappear as column headers? (LANE_MATRIX)
    hset, rset = set(h for h in header if h), set(r for r in row_labels if r)
    overlap = len(hset & rset)
    matrix_symmetry = overlap / max(len(hset | rset), 1)

    zone_header_count = sum(1 for h in header if _ZONE_LABEL.match(h))
    state_label_count = sum(1 for r in row_labels if r in _INDIAN_STATES)

    keyword_hits = {
        "vehicle": len(_VEHICLE_KW.findall(all_text)),
        "zone": len(_ZONE_KW.findall(all_text)),
        "per_kg": len(_PER_KG_KW.findall(all_text)),
        "air": len(_AIR_KW.findall(all_text)),
        "courier": len(_COURIER_KW.findall(all_text)),
        "cold": len(_COLD_KW.findall(all_text)),
        "state": len(_STATE_KW.findall(all_text)),
        "rate": len(_RATE_KW.findall(all_text)),
        "origin": len(_ORIGIN_KW.findall(" ".join(header))),
        "dest": len(_DEST_KW.findall(" ".join(header))),
    }

    return Features(
        n_rows=table.n_rows,
        n_cols=table.n_cols,
        source=table.source,
        header_tokens=header,
        row_labels=row_labels,
        all_text=all_text,
        numeric_ratio=numeric_ratio,
        matrix_symmetry=matrix_symmetry,
        keyword_hits=keyword_hits,
        zone_header_count=zone_header_count,
        state_label_count=state_label_count,
    )
