"""Phase 7 — AI gate detection/repair + G3 schema validation (pure, mocked LLM)."""
from app.classification.result import ClassificationResult
from app.core.enums import ConfidenceBand, PricingPattern, RateBasis, TransportMode
from app.extraction.raw_table import RawCell, RawTable
from app.normalization.canonical_row import CanonicalRow
from app.validation import ai_gate
from app.validation.ai_gate import detect_gates, validate_table
from app.validation.schema_validator import validate_rows


def _table_with_low_cell() -> RawTable:
    return RawTable(
        page_number=1, source="ocr", n_rows=2, n_cols=2,
        cells=[
            RawCell(row=0, col=0, text="Origin", confidence=1.0),
            RawCell(row=0, col=1, text="Rate", confidence=1.0),
            RawCell(row=1, col=0, text="Meerut", confidence=0.99),
            RawCell(row=1, col=1, text="125OO", confidence=0.55),  # low-conf numeric
        ],
    )


def _hi(pattern=PricingPattern.ROUTE_TABLE, conf=0.95):
    return ClassificationResult(pattern=pattern, confidence=conf)


# --- gate detection (deterministic, no AI) --------------------------------- #
def test_g1_detected_for_low_numeric_cell():
    gates = detect_gates(_table_with_low_cell(), _hi())
    assert "G1" in gates


def test_g2_detected_for_non_high_classification():
    clean = RawTable(page_number=1, n_rows=1, n_cols=1,
                     cells=[RawCell(row=0, col=0, text="x", confidence=1.0)])
    assert "G2" in detect_gates(clean, _hi(conf=0.6))   # MEDIUM band trips G2
    assert "G2" not in detect_gates(clean, _hi(conf=0.95))


def test_no_ai_call_when_budget_exhausted(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(ai_gate.llm, "complete_json", lambda **k: called.__setitem__("n", called["n"] + 1) or {})
    res = validate_table(_table_with_low_cell(), _hi(), ai_budget=[0])  # no budget
    assert called["n"] == 0 and res.ai_touched is False


# --- AI repair with a mocked LLM (no live API) ----------------------------- #
def test_ai_repair_fixes_cell_and_marks_touched(monkeypatch):
    def fake(**kwargs):
        return {"cells": [{"row": 1, "col": 1, "value": "12500"}],
                "explanation": "OCR read O as zero; corrected from context"}
    monkeypatch.setattr(ai_gate.llm, "complete_json", fake)
    budget = [5]
    res = validate_table(_table_with_low_cell(), _hi(), ai_budget=budget)
    assert res.ai_touched is True
    assert res.grid[1][1] == "12500"           # repaired
    assert res.edits[0].old == "125OO"
    assert budget[0] == 4                       # one call spent


def test_ai_declines_to_guess_leaves_cell(monkeypatch):
    monkeypatch.setattr(ai_gate.llm, "complete_json",
                        lambda **k: {"cells": [{"row": 1, "col": 1, "value": "uncertain"}], "explanation": "illegible"})
    res = validate_table(_table_with_low_cell(), _hi(), ai_budget=[5])
    assert res.ai_touched is False and res.grid[1][1] == "125OO"  # unchanged, stays flagged


# --- G3 schema validation -------------------------------------------------- #
def _row(**kw):
    base = dict(transport_mode=TransportMode.ROAD, source_pattern=PricingPattern.ROUTE_TABLE,
                rate_basis=RateBasis.PER_TRIP, rate_value=100.0, origin="A", destination="B")
    base.update(kw)
    return CanonicalRow(**base)


def test_schema_flags_missing_and_bad_rates():
    rows = [
        _row(),                                   # ok
        _row(rate_value=None),                    # missing
        _row(rate_value=-5),                      # non-positive
        _row(destination=None),                   # lane without destination
        _row(weight_slab_min_kg=100, weight_slab_max_kg=10),  # min>max
    ]
    bad = {v.index for v in validate_rows(rows)}
    assert bad == {1, 2, 3, 4}                    # row 0 clean


def test_schema_flags_unresolved_zone():
    rows = [_row(source_pattern=PricingPattern.ZONE_MATRIX, destination=None,
                 destination_zone="A", destination_state=None)]
    viol = validate_rows(rows)
    assert any(v.field == "destination_zone" for v in viol)
