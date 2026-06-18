"""Phase 4 — rule classifier across the 9 patterns (pure, no DB / no AI)."""
from app.classification.rule_classifier import classify_rules
from app.core.enums import PricingPattern
from app.extraction.raw_table import RawCell, RawTable


def _table(rows: list[list[str]], source: str = "digital") -> RawTable:
    cells = [
        RawCell(row=r, col=c, text=val)
        for r, row in enumerate(rows)
        for c, val in enumerate(row)
    ]
    n_rows = len(rows)
    n_cols = max((len(r) for r in rows), default=0)
    return RawTable(page_number=1, cells=cells, n_rows=n_rows, n_cols=n_cols, source=source)


def test_route_table():
    t = _table([
        ["Origin", "Destination", "Freight Rate"],
        ["Meerut", "Bangalore", "12500"],
        ["Hapur", "Kolkata", "9800"],
    ])
    r = classify_rules(t)
    assert r.pattern is PricingPattern.ROUTE_TABLE
    assert r.column_mapping.get("origin") == 0 and r.column_mapping.get("rate") == 2


def test_vehicle_matrix():
    t = _table([
        ["Lane", "Tata 407", "Eicher 32ft", "Trailer"],
        ["Delhi-Mumbai", "18000", "42000", "65000"],
        ["Delhi-Chennai", "26000", "55000", "82000"],
    ])
    assert classify_rules(t).pattern is PricingPattern.VEHICLE_MATRIX


def test_zone_matrix():
    t = _table([
        ["From/To", "Zone A", "Zone B", "Zone C", "Zone D"],
        ["Delhi", "10", "14", "18", "22"],
        ["Mumbai", "12", "16", "20", "26"],
    ])
    assert classify_rules(t).pattern is PricingPattern.ZONE_MATRIX


def test_state_zone_mapping():
    t = _table([
        ["State", "Zone"],
        ["Maharashtra", "A"],
        ["Kerala", "C"],
        ["West Bengal", "D"],
    ])
    assert classify_rules(t).pattern is PricingPattern.STATE_ZONE_MAPPING


def test_per_kg_rate():
    t = _table([
        ["Weight Slab", "Rate per kg"],
        ["0-50 kg", "14.50"],
        ["upto 100 kg", "12.00"],
    ])
    assert classify_rules(t).pattern is PricingPattern.PER_KG_RATE


def test_air_rate():
    t = _table([
        ["Airport", "AWB Charge", "Rate per kg"],
        ["DEL-BLR", "150", "85"],
    ])
    assert classify_rules(t).pattern is PricingPattern.AIR_RATE


def test_courier_rate():
    t = _table([
        ["Destination", "Docket Charge", "Express Rate"],
        ["Bangalore", "60", "120"],
    ])
    assert classify_rules(t).pattern is PricingPattern.COURIER_RATE


def test_cold_chain_rate():
    t = _table([
        ["Lane", "Temperature", "Rate"],
        ["Delhi-Pune", "2-8 °C", "45000"],
        ["Delhi-Goa", "-20 °C frozen reefer", "62000"],
    ])
    assert classify_rules(t).pattern is PricingPattern.COLD_CHAIN_RATE


def test_lane_matrix_symmetry():
    t = _table([
        ["", "Delhi", "Mumbai", "Chennai"],
        ["Delhi", "0", "18000", "26000"],
        ["Mumbai", "18000", "0", "22000"],
        ["Chennai", "26000", "22000", "0"],
    ])
    assert classify_rules(t).pattern is PricingPattern.LANE_MATRIX


def test_unknown_when_no_signal():
    t = _table([["foo", "bar"], ["lorem", "ipsum"]])
    assert classify_rules(t).pattern is PricingPattern.UNKNOWN
