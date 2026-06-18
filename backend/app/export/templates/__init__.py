"""Mankind output templates — column mapping config (Requirement 10 / §10).

The Excel layout is DATA, not code: each template maps canonical fields to Mankind
column headers per transport mode. Changing Mankind's output format means editing
a template here, never touching the writer. Add a vendor- or division-specific
template by adding a key — the writer stays the same.

A column is (header, field) where `field` is a CanonicalRate attribute name or a
("$fmt", attr) tuple for a formatter. Provenance columns (Enhancement #6) are
appended per template flag.
"""
from __future__ import annotations

# Shared provenance/confidence columns appended to every rate sheet.
_PROVENANCE_COLUMNS = [
    ("Source Page", "source_page"),
    ("Table", "table_id"),
    ("Cell", ("$cell", "source_cell")),
    ("Extraction Confidence", ("$pct", "extraction_confidence")),
    ("Confidence Band", ("$enum", "confidence_band")),
    ("Validation Status", ("$enum", "validation_status")),
    ("AI Touched", "ai_touched"),
]

MANKIND_DEFAULT_V2 = {
    "name": "mankind_default_v2",
    "include_provenance": True,
    "provenance_columns": _PROVENANCE_COLUMNS,
    "modes": {
        "ROAD": {
            "sheet": "Road Freight",
            "columns": [
                ("Origin", "origin"),
                ("Destination", "destination"),
                ("Origin State", "origin_state"),
                ("Destination State", "destination_state"),
                ("Destination Zone", "destination_zone"),
                ("Vehicle Type", "vehicle_type"),
                ("Rate Basis", ("$enum", "rate_basis")),
                ("Rate (INR)", ("$num", "rate_value")),
                ("Min Charge", ("$num", "min_charge")),
                ("Weight Slab Min (kg)", "weight_slab_min_kg"),
                ("Weight Slab Max (kg)", "weight_slab_max_kg"),
                ("Effective From", "effective_from"),
            ],
        },
        "AIR": {
            "sheet": "Air Freight",
            "columns": [
                ("Origin", "origin"),
                ("Destination", "destination"),
                ("Rate Basis", ("$enum", "rate_basis")),
                ("Rate per kg (INR)", ("$num", "rate_value")),
                ("AWB / Docket Charge", ("$num", "docket_charge")),
                ("Min Weight (kg)", "min_weight_kg"),
                ("Effective From", "effective_from"),
            ],
        },
        "COURIER": {
            "sheet": "Courier Rates",
            "columns": [
                ("Destination", "destination"),
                ("Service Level", "service_level"),
                ("Rate Basis", ("$enum", "rate_basis")),
                ("Rate (INR)", ("$num", "rate_value")),
                ("Docket Charge", ("$num", "docket_charge")),
                ("Effective From", "effective_from"),
            ],
        },
        "COLD_CHAIN": {
            "sheet": "Cold Chain",
            "columns": [
                ("Origin", "origin"),
                ("Destination", "destination"),
                ("Temperature Band", "temperature_band"),
                ("Rate Basis", ("$enum", "rate_basis")),
                ("Rate (INR)", ("$num", "rate_value")),
                ("Effective From", "effective_from"),
            ],
        },
    },
}

TEMPLATES = {MANKIND_DEFAULT_V2["name"]: MANKIND_DEFAULT_V2}


def get_template(name: str) -> dict:
    if name not in TEMPLATES:
        raise KeyError(f"unknown export template {name!r}; have {list(TEMPLATES)}")
    return TEMPLATES[name]
