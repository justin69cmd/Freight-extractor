"""Phase 5 — route expansion, unit parsing, adapters, zone resolution (pure)."""
from app.core.enums import PricingPattern, RateBasis, TransportMode
from app.metadata.clause_extractor import extract_clauses
from app.metadata.metadata_extractor import extract_metadata, parse_date
from app.normalization.normalizer import TableInput, normalize_agreement
from app.normalization.route_expander import expand_routes, split_places
from app.normalization.unit_normalizer import parse_amount, parse_weight_slab


# --- route expansion (the critical business rule) -------------------------- #
def test_cartesian_expansion():
    lanes = expand_routes("Hapur/Meerut/FRK", "Kolkata/Delhi")
    assert set(lanes) == {
        ("Hapur", "Kolkata"), ("Meerut", "Kolkata"), ("FRK", "Kolkata"),
        ("Hapur", "Delhi"), ("Meerut", "Delhi"), ("FRK", "Delhi"),
    }
    assert len(lanes) == 6


def test_alias_resolution_and_dedupe():
    assert split_places("FRK / Faridabad", {"FRK": "Faridabad"}) == ["Faridabad"]


# --- unit parsing ---------------------------------------------------------- #
def test_parse_amount():
    assert parse_amount("Rs. 12,500/-") == 12500.0
    assert parse_amount("₹ 9800.50") == 9800.50
    assert parse_amount("N/A") is None
    assert parse_amount("-50") is None  # negative rejected


def test_parse_weight_slab():
    assert parse_weight_slab("0-50 kg") == (0.0, 50.0)
    assert parse_weight_slab("upto 100") == (None, 100.0)
    assert parse_weight_slab("above 1000 kgs") == (1000.0, None)


# --- adapters via the dispatcher ------------------------------------------- #
def test_route_table_adapter_expands():
    t = TableInput(
        pattern=PricingPattern.ROUTE_TABLE,
        grid=[["Origin", "Destination", "Rate"], ["Hapur/Meerut", "Kolkata/Delhi", "9800"]],
        column_mapping={"origin": 0, "destination": 1, "rate": 2},
    )
    out = normalize_agreement([t])
    assert len(out.rows) == 4
    assert all(r.rate_value == 9800.0 for r in out.rows)
    assert all(r.transport_mode is TransportMode.ROAD for r in out.rows)
    assert {(r.origin, r.destination) for r in out.rows} == {
        ("Hapur", "Kolkata"), ("Meerut", "Kolkata"), ("Hapur", "Delhi"), ("Meerut", "Delhi"),
    }


def test_vehicle_matrix_adapter():
    t = TableInput(
        pattern=PricingPattern.VEHICLE_MATRIX,
        grid=[["Lane", "Tata 407", "32ft"], ["Delhi-Mumbai", "18000", "42000"]],
        column_mapping={},
    )
    out = normalize_agreement([t])
    assert {(r.vehicle_type, r.rate_value) for r in out.rows} == {("Tata 407", 18000.0), ("32ft", 42000.0)}
    assert all(r.origin == "Delhi" and r.destination == "Mumbai" for r in out.rows)


def test_zone_resolution_joins_state_map():
    rate_table = TableInput(
        pattern=PricingPattern.ZONE_MATRIX,
        grid=[["From", "Zone A", "Zone B"], ["Delhi", "10", "15"]],
        column_mapping={},
    )
    zone_map = TableInput(
        pattern=PricingPattern.STATE_ZONE_MAPPING,
        grid=[["State", "Zone"], ["Maharashtra", "A"], ["Gujarat", "A"], ["Kerala", "B"]],
        column_mapping={},
    )
    out = normalize_agreement([rate_table, zone_map])
    # Zone A rate (10) resolves to Maharashtra + Gujarat; Zone B (15) -> Kerala
    resolved = {(r.destination_state, r.rate_value) for r in out.rows if r.destination_state}
    assert resolved == {("Maharashtra", 10.0), ("Gujarat", 10.0), ("Kerala", 15.0)}
    assert len(out.zone_maps) == 3


# --- metadata + clauses (Enhancement #1) ----------------------------------- #
def test_parse_date_formats():
    from datetime import date
    assert parse_date("01/04/2024") == date(2024, 4, 1)
    assert parse_date("1st April 2024") == date(2024, 4, 1)


def test_clause_extraction():
    text = (
        "5. Fuel Surcharge: A fuel surcharge of 3% shall apply on all shipments.\n\n"
        "6. Insurance: Transit insurance is the responsibility of the transporter.\n\n"
        "7. Penalty: A penalty of Rs 500 per day applies for delayed delivery."
    )
    clauses = extract_clauses(2, text)
    types = {c.clause_type.value for c in clauses}
    assert {"FUEL", "INSURANCE", "PENALTY"} <= types


def test_metadata_extraction():
    pages = [(1, "This Agreement is made between M/s SafeExpress Logistics. "
                "Effective from 01/04/2024 valid until 31/03/2025. "
                "Payment terms: payable within 30 days of invoice.")]
    meta = extract_metadata(pages)
    assert meta.effective_date is not None and meta.expiry_date is not None
    assert "30 days" in (meta.payment_terms or "")
