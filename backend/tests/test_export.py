"""Phase 6 — Excel workbook building + review-gate logic.

Uses lightweight stand-in objects (the writer is duck-typed and DB-free), so no
database is required. openpyxl is exercised for real.
"""
from types import SimpleNamespace

from app.core.enums import (
    ConfidenceBand,
    PricingPattern,
    RateBasis,
    TransportMode,
    ValidationStatus,
)
from app.export.excel_writer import build_workbook


def _rate(**kw):
    base = dict(
        transport_mode=TransportMode.ROAD,
        source_pattern=PricingPattern.ROUTE_TABLE,
        origin="Meerut", destination="Bangalore",
        origin_state=None, destination_state=None, destination_zone=None,
        vehicle_type=None, rate_basis=RateBasis.PER_TRIP, rate_value=12500.0,
        min_charge=None, weight_slab_min_kg=None, weight_slab_max_kg=None,
        docket_charge=None, service_level=None, temperature_band=None,
        min_weight_kg=None, effective_from=None,
        source_page=3, table_id=__import__("uuid").uuid4(), source_cell={"row": 2, "col": 2},
        extraction_confidence=0.95, confidence_band=ConfidenceBand.HIGH,
        validation_status=ValidationStatus.AUTO, ai_touched=False, rate_value_ok=True,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_workbook_has_mode_tabs_and_summary():
    rows = [
        _rate(),
        _rate(transport_mode=TransportMode.AIR, source_pattern=PricingPattern.AIR_RATE,
              rate_basis=RateBasis.PER_KG, rate_value=85.0, docket_charge=150.0),
        _rate(transport_mode=TransportMode.COURIER, rate_basis=RateBasis.PER_KG,
              destination="Kolkata", service_level="express", rate_value=120.0),
    ]
    meta = SimpleNamespace(vendor_name="Safexpress", effective_date="2024-04-01",
                           expiry_date="2025-03-31", payment_terms="30 days")
    wb = build_workbook(rows=rows, metadata=meta, clauses=[],
                        template_name="mankind_default_v2", vendor_name="Safexpress")
    assert "Summary" in wb.sheetnames
    assert {"Road Freight", "Air Freight", "Courier Rates", "Cold Chain"} <= set(wb.sheetnames)
    road = wb["Road Freight"]
    assert road.cell(row=1, column=1).value == "Origin"
    # one data row written (header is row 1)
    assert road.cell(row=2, column=1).value == "Meerut"


def test_flagged_rows_excluded_unless_requested():
    rows = [
        _rate(),  # clean HIGH
        _rate(origin="Hapur", confidence_band=ConfidenceBand.LOW, extraction_confidence=0.4),
    ]
    wb = build_workbook(rows=rows, metadata=None, clauses=[],
                        template_name="mankind_default_v2", include_flagged=False)
    road = wb["Road Freight"]
    origins = [road.cell(row=r, column=1).value for r in (2, 3)]
    assert "Meerut" in origins and "Hapur" not in origins  # LOW excluded

    wb2 = build_workbook(rows=rows, metadata=None, clauses=[],
                         template_name="mankind_default_v2", include_flagged=True)
    road2 = wb2["Road Freight"]
    origins2 = [road2.cell(row=r, column=1).value for r in (2, 3)]
    assert "Hapur" in origins2  # included when requested


def test_enum_and_num_formatting():
    wb = build_workbook(rows=[_rate()], metadata=None, clauses=[],
                        template_name="mankind_default_v2")
    road = wb["Road Freight"]
    headers = [road.cell(row=1, column=c).value for c in range(1, 30)]
    rate_basis_col = headers.index("Rate Basis") + 1
    rate_col = headers.index("Rate (INR)") + 1
    assert road.cell(row=2, column=rate_basis_col).value == "PER_TRIP"  # enum -> .value
    assert road.cell(row=2, column=rate_col).value == 12500.0          # numeric


def test_provenance_columns_present():
    wb = build_workbook(rows=[_rate()], metadata=None, clauses=[],
                        template_name="mankind_default_v2")
    headers = [c.value for c in wb["Road Freight"][1]]
    assert "Source Page" in headers and "Confidence Band" in headers and "AI Touched" in headers
