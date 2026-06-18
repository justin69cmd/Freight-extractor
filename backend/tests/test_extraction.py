"""Phase 3 — page classification + RawTable fingerprint (no heavy deps needed)."""
from app.core.enums import PageKind
from app.extraction.raw_table import RawCell, RawTable
from app.ingestion.page_classifier import classify_page
from app.ingestion.pdf_loader import PageInfo


def _page(text: str) -> PageInfo:
    return PageInfo(number=1, is_digital=True, text=text, char_count=len(text))


def test_classifies_rate_card():
    p = _page("Freight Rate Card: amount per kg charges 12.50 25.00 40.00")
    assert classify_page(p) is PageKind.RATE_CARD


def test_classifies_zone_map():
    p = _page("State to Zone mapping: Maharashtra Zone A, Kerala Zone C")
    assert classify_page(p) is PageKind.ZONE_MAP


def test_classifies_legal_page():
    p = _page(
        "This Agreement whereas the parties indemnity liability terms and conditions "
        "payment terms insurance penalty fuel surcharge jurisdiction arbitration apply."
    )
    assert classify_page(p) is PageKind.LEGAL


def test_scanned_page_defaults_to_rate_card():
    assert classify_page(PageInfo(number=2, is_digital=False, text="")) is PageKind.RATE_CARD


def _table(headers, source="digital") -> RawTable:
    cells = [RawCell(row=0, col=c, text=h) for c, h in enumerate(headers)]
    return RawTable(page_number=1, cells=cells, n_rows=1, n_cols=len(headers), source=source)


def test_fingerprint_stable_for_same_layout():
    a = _table(["Origin", "Destination", "Rate"])
    b = _table(["origin", "destination", "rate"])  # case-insensitive normalize
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_differs_for_different_layout():
    a = _table(["Origin", "Destination", "Rate"])
    b = _table(["Vehicle", "Zone A", "Zone B"])
    assert a.fingerprint() != b.fingerprint()


def test_low_confidence_numeric_cells_flagged():
    t = RawTable(
        page_number=1, source="ocr", n_rows=1, n_cols=2,
        cells=[
            RawCell(row=0, col=0, text="1250", confidence=0.6),   # low numeric -> flagged
            RawCell(row=0, col=1, text="Mumbai", confidence=0.6),  # low text -> not numeric
        ],
    )
    flagged = t.low_confidence_numeric_cells()
    assert len(flagged) == 1 and flagged[0].text == "1250"
