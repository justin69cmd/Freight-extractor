"""L1 — table extraction for scanned pages (OpenCV + EasyOCR).

Pipeline: render page -> deskew/denoise -> detect cell grid -> OCR each cell.
Numeric cells are OCR'd with a restricted charset to cut O/0, S/5, l/1 misreads,
and every cell carries EasyOCR's confidence so the orchestrator can escalate
low-confidence price cells to the AI gate or human review.
"""
from __future__ import annotations

import re

from app.core.exceptions import ExtractionError
from app.extraction.raw_table import BBox, RawCell, RawTable
from app.extraction.table_detect import deskew, detect_cell_grid

_NUMERIC_ALLOWLIST = "0123456789.,/-"
_NUM_RE = re.compile(r"^[\d.,/\-\s]+$")

# EasyOCR reader is expensive to construct; build once per worker.
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr  # lazy

        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def render_page(pdf_path: str, page_number: int, dpi: int = 300):
    """Rasterize one PDF page to a BGR numpy image for OpenCV."""
    import numpy as np
    import pypdfium2 as pdfium  # lightweight renderer

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        page = pdf[page_number - 1]
        pil = page.render(scale=dpi / 72).to_pil().convert("RGB")
        arr = np.array(pil)[:, :, ::-1]  # RGB -> BGR
        return arr
    finally:
        pdf.close()


def extract_scanned_tables(pdf_path: str, page_number: int) -> list[RawTable]:
    """Extract a table from a scanned page. Returns a single-table list (or [])."""
    try:
        import cv2  # lazy, just to fail fast with a clear message
        _ = cv2
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("opencv not installed (worker dependency)") from exc

    try:
        image = render_page(pdf_path, page_number)
        image = deskew(image)
        boxes = detect_cell_grid(image)
        if not boxes:
            return []

        reader = _get_reader()
        cells: list[RawCell] = []
        for b in boxes:
            crop = image[b.y0:b.y1, b.x0:b.x1]
            if crop.size == 0:
                continue
            text, conf = _ocr_cell(reader, crop)
            cells.append(
                RawCell(
                    row=b.row, col=b.col, text=text, confidence=conf,
                    bbox=BBox(x0=b.x0, y0=b.y0, x1=b.x1, y1=b.y1),
                )
            )

        n_rows = max((c.row for c in cells), default=-1) + 1
        n_cols = max((c.col for c in cells), default=-1) + 1
        return [
            RawTable(
                page_number=page_number, cells=cells,
                n_rows=n_rows, n_cols=n_cols, source="ocr",
            )
        ]
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"OCR failed on page {page_number}: {exc}") from exc


def _ocr_cell(reader, crop) -> tuple[str, float]:
    """OCR a single cell; first pass free-form, refine numerics with allowlist."""
    results = reader.readtext(crop, detail=1, paragraph=False)
    if not results:
        return "", 1.0  # empty cell, not a failure
    text = " ".join(r[1] for r in results).strip()
    conf = sum(r[2] for r in results) / len(results)

    if _NUM_RE.match(text):  # looks numeric -> re-read with restricted charset
        refined = reader.readtext(crop, detail=1, allowlist=_NUMERIC_ALLOWLIST, paragraph=False)
        if refined:
            text = " ".join(r[1] for r in refined).strip()
            conf = sum(r[2] for r in refined) / len(refined)
    return text, float(conf)
