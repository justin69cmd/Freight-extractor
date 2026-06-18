"""L1 — table extraction for born-digital pages.

Strategy: Camelot first (lattice for ruled tables, stream as fallback), then
pdfplumber as a backstop. Digital text is ground truth, so every cell gets
confidence 1.0 — no OCR uncertainty here.
"""
from __future__ import annotations

from app.core.exceptions import ExtractionError
from app.extraction.raw_table import BBox, RawCell, RawTable


def extract_digital_tables(pdf_path: str, page_number: int) -> list[RawTable]:
    """Extract all tables from a single digital page (1-based page_number)."""
    tables = _camelot_tables(pdf_path, page_number)
    if tables:
        return tables
    return _pdfplumber_tables(pdf_path, page_number)


def _camelot_tables(pdf_path: str, page_number: int) -> list[RawTable]:
    try:
        import camelot  # lazy
    except ImportError:  # pragma: no cover
        return []

    out: list[RawTable] = []
    for flavor in ("lattice", "stream"):
        try:
            found = camelot.read_pdf(pdf_path, pages=str(page_number), flavor=flavor)
        except Exception:  # noqa: BLE001 — camelot raises on no-tables / ghostscript
            continue
        if found and len(found) > 0:
            for t in found:
                out.append(_from_camelot(t, page_number))
            if out:
                return out  # prefer lattice if it produced anything
    return out


def _from_camelot(table, page_number: int) -> RawTable:
    data = table.df.values.tolist()  # type: ignore[attr-defined]
    n_rows = len(data)
    n_cols = len(data[0]) if data else 0
    cells = [
        RawCell(row=r, col=c, text=str(val).strip(), confidence=1.0)
        for r, row in enumerate(data)
        for c, val in enumerate(row)
    ]
    return RawTable(
        page_number=page_number, cells=cells, n_rows=n_rows, n_cols=n_cols, source="digital"
    )


def _pdfplumber_tables(pdf_path: str, page_number: int) -> list[RawTable]:
    try:
        import pdfplumber  # lazy
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("pdfplumber not installed (worker dependency)") from exc

    out: list[RawTable] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_number - 1]
            for tbl in page.find_tables() or []:
                data = tbl.extract()
                if not data:
                    continue
                n_rows = len(data)
                n_cols = max((len(r) for r in data), default=0)
                cells = [
                    RawCell(row=r, col=c, text=(val or "").strip(), confidence=1.0)
                    for r, row in enumerate(data)
                    for c, val in enumerate(row)
                ]
                x0, top, x1, bottom = tbl.bbox
                out.append(
                    RawTable(
                        page_number=page_number,
                        bbox=BBox(x0=x0, y0=top, x1=x1, y1=bottom),
                        cells=cells,
                        n_rows=n_rows,
                        n_cols=n_cols,
                        source="digital",
                    )
                )
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"pdfplumber failed on page {page_number}: {exc}") from exc
    return out
