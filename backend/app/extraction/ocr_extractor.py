"""L1 — table extraction for scanned pages (EasyOCR + position clustering).

Strategy
--------
Grid-line detection fails on faint/broken scanned rulings, so instead of trying
to find drawn cell borders we:
  1. OCR the WHOLE page once (EasyOCR reads clean text + per-box positions).
  2. Cluster the detected text boxes by Y (rows) and X (columns) to rebuild the
     table structure from geometry, independent of any visible ruling lines.
  3. Lightly clean each cell (whitespace, obvious OCR junk) and SAFELY normalise
     numbers — without guessing dropped decimals, which would corrupt large
     freight values like 25700.

Optional closed-vocabulary fuzzy matching (e.g. zone names from a vendor
profile) can snap garbled labels to known terms; it is OFF unless a vocabulary
is supplied, so it never overfits an unseen layout.
"""
from __future__ import annotations

import difflib
import re

from app.core.exceptions import ExtractionError
from app.extraction.raw_table import BBox, RawCell, RawTable

# EasyOCR reader is expensive to construct; build once per worker (lazy).
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr  # lazy
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def render_page(pdf_path: str, page_number: int, dpi: int = 300):
    """Rasterize one PDF page to a BGR numpy image for EasyOCR/OpenCV."""
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


# --------------------------------------------------------------------------- #
# Text / number cleaning
# --------------------------------------------------------------------------- #
def _sanitize_text(s: str) -> str:
    """Collapse whitespace and trim. Faithful — does not alter content."""
    return re.sub(r"\s+", " ", (s or "").strip())


def _normalize_number(s: str) -> str:
    """Conservatively clean a numeric-looking cell.

    SAFE rules only:
      * "23,00" -> "23.00"   (comma decimal -> period)
      * strip surrounding junk: "|23.00 " -> "23.00"
    It deliberately does NOT guess dropped decimals (e.g. it leaves "2300" and
    "25700" untouched), because that guessing corrupts large freight rates.
    Number *interpretation* is the normalization layer's job, not extraction's.
    """
    t = (s or "").strip()
    if not t:
        return t
    # comma decimal -> period, only when it looks like a decimal (d,dd)
    t = re.sub(r"(?<=\d),(?=\d{1,2}\b)", ".", t)
    # keep only a leading sign, digits, separators — drop wrapping junk
    m = re.search(r"-?\d[\d.,]*", t)
    return m.group() if m else t


def _looks_numeric(s: str) -> bool:
    """True if the cell is mostly a number (used for the footer cutoff)."""
    t = (s or "").strip()
    if not t or not any(ch.isdigit() for ch in t):
        return False
    digits = sum(ch.isdigit() for ch in t)
    non_space = sum(not ch.isspace() for ch in t)
    return non_space > 0 and digits / non_space >= 0.5


def fuzzy_match(raw_value: str, vocabulary: list[str] | None) -> str:
    """Snap a garbled label to the closest known term, if confident.

    Two-stage: difflib close-match, then normalised alphanumeric ratio. Returns
    the original value unchanged when no vocabulary is given or nothing is close
    enough — so it is a safe no-op on unseen layouts.
    """
    if not raw_value or not vocabulary:
        return raw_value
    matches = difflib.get_close_matches(raw_value, vocabulary, n=1, cutoff=0.6)
    if matches:
        return matches[0]

    def _norm(x: str) -> str:
        return re.sub(r"[^a-z0-9]", "", x.lower())

    raw_norm = _norm(raw_value)
    best, best_ratio = None, 0.0
    for option in vocabulary:
        ratio = difflib.SequenceMatcher(None, raw_norm, _norm(option)).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, option
    return best if best_ratio >= 0.7 and best else raw_value


# --------------------------------------------------------------------------- #
# Position clustering
# --------------------------------------------------------------------------- #
def _cluster_1d(values: list[float], tol: float) -> list[float]:
    """Group nearby 1-D coordinates into cluster centers (sorted)."""
    if not values:
        return []
    vals = sorted(values)
    clusters: list[list[float]] = [[vals[0]]]
    for v in vals[1:]:
        if v - clusters[-1][-1] <= tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _nearest(centers: list[float], v: float) -> int:
    """Index of the closest cluster center to v."""
    best_i, best_d = 0, float("inf")
    for i, c in enumerate(centers):
        d = abs(c - v)
        if d < best_d:
            best_i, best_d = i, d
    return best_i


def extract_scanned_tables(
    pdf_path: str,
    page_number: int,
    *,
    vocabulary: list[str] | None = None,
) -> list[RawTable]:
    """OCR a scanned page and reconstruct a table from text-box positions.

    `vocabulary` (optional): known labels for this vendor (e.g. zone names). When
    supplied, garbled label cells are fuzzy-snapped to it; otherwise untouched.
    """
    try:
        image = render_page(pdf_path, page_number)
        reader = _get_reader()
        results = reader.readtext(image, detail=1, paragraph=False)
        if not results:
            return []

        items = []          # (x0, center_y, text, conf, bx0, by0, bx1, by1)
        heights = []
        for bbox, text, conf in results:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            x0 = min(xs)
            cy = (min(ys) + max(ys)) / 2
            items.append(
                (x0, cy, text, float(conf), min(xs), min(ys), max(xs), max(ys))
            )
            heights.append(max(ys) - min(ys))
        if not items:
            return []

        # Tolerances scale with typical text height so they adapt to DPI.
        med_h = sorted(heights)[len(heights) // 2] or 20
        row_tol = med_h * 0.6
        col_tol = med_h * 2.0  # keeps a single number intact, separates columns

        row_centers = _cluster_1d([it[1] for it in items], row_tol)
        col_centers = _cluster_1d([it[0] for it in items], col_tol)
        if len(row_centers) < 2 or len(col_centers) < 1:
            return []

        # Place each text box into its (row, col); join boxes that share a slot.
        grid: dict[tuple[int, int], tuple[str, float, float, float, float, float]] = {}
        for x0, cy, text, conf, bx0, by0, bx1, by1 in items:
            r = _nearest(row_centers, cy)
            c = _nearest(col_centers, x0)
            key = (r, c)
            if key in grid:
                pt, pc, px0, py0, px1, py1 = grid[key]
                grid[key] = (
                    _sanitize_text(f"{pt} {text}"),
                    min(pc, conf),
                    min(px0, bx0), min(py0, by0), max(px1, bx1), max(py1, by1),
                )
            else:
                grid[key] = (_sanitize_text(text), conf, bx0, by0, bx1, by1)

        # Footer cutoff: keep through the last row that has a numeric value in a
        # rate column (col >= 1). Trailing legend / terms / page-number prose has
        # no numbers in the rate columns, so it gets dropped.
        data_rows = {
            r for (r, c), (text, *_rest) in grid.items()
            if c >= 1 and _looks_numeric(text)
        }
        last_data_row = max(data_rows) if data_rows else len(row_centers) - 1

        cells: list[RawCell] = []
        for (r, c), (text, conf, bx0, by0, bx1, by1) in grid.items():
            if r > last_data_row:
                continue
            value = _normalize_number(text) if _looks_numeric(text) else text
            if c == 0:  # label column — optional vocab snap
                value = fuzzy_match(value, vocabulary)
            cells.append(
                RawCell(
                    row=r, col=c, text=value, confidence=conf,
                    bbox=BBox(x0=int(bx0), y0=int(by0), x1=int(bx1), y1=int(by1)),
                )
            )

        return [
            RawTable(
                page_number=page_number, cells=cells,
                n_rows=last_data_row + 1, n_cols=len(col_centers), source="ocr",
            )
        ]
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"OCR failed on page {page_number}: {exc}") from exc
